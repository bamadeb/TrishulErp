from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import URL, Engine, create_engine, event, text
from sqlalchemy.orm import Session

from trishul_api.config import Settings


def create_db_engine(settings: Settings) -> Engine:
    url = URL.create(
        "mssql+pyodbc",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        query={
            "driver": settings.odbc_driver,
            "Encrypt": "yes" if settings.db_encrypt else "no",
            "TrustServerCertificate": "yes" if settings.db_trust_server_certificate else "no",
            "APP": "trishul-api",
        },
    )
    engine = create_engine(
        url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
        # Replaced by the reset handler below.
        pool_reset_on_return=None,
    )

    @event.listens_for(engine, "reset")
    def _reset_connection(dbapi_connection: Any, _record: Any, reset_state: Any) -> None:
        # sp_reset_connection clears SESSION_CONTEXT, so a pooled connection never carries
        # the previous request's user into the next one. It is also required because
        # app_user_id is set read-only and could not be overwritten otherwise.
        if not reset_state.terminate_only:
            dbapi_connection.execute("{call sys.sp_reset_connection}")
        dbapi_connection.rollback()

    return engine


@contextmanager
def user_session(engine: Engine, app_user_id: int) -> Iterator[Session]:
    """A session whose connection is tagged with the signed-in user for row-level security.

    The session is bound to one connection for its whole life, so every statement (also
    after a commit) runs with the same SESSION_CONTEXT.
    """
    with engine.connect() as connection:
        connection.execute(
            text("EXEC sys.sp_set_session_context @key = N'app_user_id', @value = :id, @read_only = 1"),
            {"id": app_user_id},
        )
        connection.commit()
        with Session(bind=connection, expire_on_commit=False) as session:
            yield session
