import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import URL, Engine, create_engine, event, text
from sqlalchemy.orm import Session

from trishul_api.config import Settings
from trishul_api.db.credentials import DbCredentials, db_credentials
from trishul_api.secrets import SecretProvider

logger = logging.getLogger(__name__)


def create_db_engine(settings: Settings, secrets: SecretProvider | None = None) -> Engine:
    """The application's SQLAlchemy engine for SQL Server.

    When ``settings.db_secret_id`` is set and a secret provider is given, the connection is taken from AWS
    Secrets Manager: the host, port and database name are read once (TRISHUL_DB_HOST/PORT/NAME are used only
    as a fallback for any field the secret omits), and the username and password are injected on each new
    physical connection, so a rotated password is used by new connections without a restart. Without a
    secret, the connection comes from TRISHUL_DB_* entirely, which is how local development and tests run.
    """
    use_secret = bool(settings.db_secret_id) and secrets is not None
    host, port, database = settings.db_host, settings.db_port, settings.db_name
    if use_secret:
        assert secrets is not None  # narrowed by use_secret
        secret_id = settings.db_secret_id
        assert secret_id is not None
        info = secrets.get_json(secret_id)  # RDS-format secret; cached and reused for the login below
        host = str(info.get("host") or host)
        port = int(info.get("port") or port)
        database = str(info.get("dbname") or database)

    query = {
        "driver": settings.odbc_driver,
        "Encrypt": "yes" if settings.db_encrypt else "no",
        "TrustServerCertificate": "yes" if settings.db_trust_server_certificate else "no",
        "APP": "trishul-api",
    }
    # With a secret, build the connection string without a login and add UID/PWD at connect time below.
    url = URL.create(
        "mssql+pyodbc",
        username=None if use_secret else settings.db_user,
        password=None if use_secret else settings.db_password.get_secret_value(),
        host=host,
        port=port,
        database=database,
        query=query,
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

    if use_secret:
        assert secrets is not None  # narrowed by use_secret
        assert settings.db_secret_id is not None
        _attach_rotating_credentials(engine, secrets, settings.db_secret_id)

    @event.listens_for(engine, "reset")
    def _reset_connection(dbapi_connection: Any, _record: Any, reset_state: Any) -> None:
        # sp_reset_connection clears SESSION_CONTEXT, so a pooled connection never carries
        # the previous request's user into the next one. It is also required because
        # app_user_id is set read-only and could not be overwritten otherwise.
        if not reset_state.terminate_only:
            dbapi_connection.execute("{call sys.sp_reset_connection}")
        dbapi_connection.rollback()

    return engine


def _odbc_value(value: str) -> str:
    """Brace-wrap an ODBC connection-string value so ``;`` ``{`` ``}`` in a password can't break it."""
    return "{" + value.replace("}", "}}") + "}"


def _login_suffix(creds: DbCredentials) -> str:
    """The ``;UID=...;PWD=...`` appended to the ODBC connection string for a connection."""
    return f";UID={_odbc_value(creds.username)};PWD={_odbc_value(creds.password)}"


def _strip_trusted_connection(odbc: str) -> str:
    """Remove ``Trusted_Connection=...``.

    With no login in the URL, the pyodbc dialect adds ``Trusted_Connection=Yes``, which forces Windows
    integrated auth and ignores the UID/PWD we supply at connect time. The tokens before the login are
    plain ``key=value`` pairs (no password yet), so splitting on ``;`` is safe here.
    """
    kept = [part for part in odbc.split(";") if part and not part.lower().startswith("trusted_connection=")]
    return ";".join(kept)


# SQLSTATE 28000 / SQL Server error 18456: the login was rejected -- the likely symptom of a rotated password.
_AUTH_FAILURE_MARKERS = ("28000", "18456", "login failed")


def _is_auth_failure(original: BaseException | None) -> bool:
    return original is not None and any(marker in str(original).lower() for marker in _AUTH_FAILURE_MARKERS)


def _attach_rotating_credentials(engine: Engine, secrets: SecretProvider, secret_id: str) -> None:
    """Inject the current secret's login on every new connection, and refresh it after an auth failure."""

    @event.listens_for(engine, "do_connect")
    def _supply_login(_dialect: Any, _rec: Any, cargs: list[Any], _cparams: dict[str, Any]) -> None:
        creds = db_credentials(secrets, secret_id)  # cached within the TTL; a dict lookup in the common case
        cargs[0] = f"{_strip_trusted_connection(cargs[0])}{_login_suffix(creds)}"

    @event.listens_for(engine, "handle_error")
    def _refresh_on_auth_failure(context: Any) -> None:
        if _is_auth_failure(context.original_exception):
            # Drop the cached secret so the next connection re-reads the (rotated) password at once,
            # rather than waiting for the cache TTL to lapse.
            logger.warning("Database login was rejected; refreshing credentials from Secrets Manager")
            secrets.invalidate(secret_id)


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
