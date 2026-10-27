"""Alembic environment for Trishul ERP.

Revisions are hand-written SQL (op.execute) and must be idempotent: check the catalog first, as
database/12 and 13 do. Never autogenerate from the ORM models: it works the other way round. After a
revision that changes tables, run scripts/generate_models.py; it reads the SQL in these revisions.

    uv run alembic upgrade head            # apply, using the TRISHUL_MIGRATION_DB_* login
    uv run alembic upgrade head --sql      # print the SQL for review instead
    uv run alembic stamp v3_baseline       # once, on a database built from database/00..13
"""

from alembic import context
from sqlalchemy import URL

from trishul_api.config import Settings, get_settings
from trishul_api.db.engine import create_db_engine
from trishul_api.secrets import SecretProvider, create_secret_provider


def run_offline() -> None:
    context.configure(url=URL.create("mssql+pyodbc"), literal_binds=True, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


def _migration_engine(settings: Settings) -> tuple[Settings, SecretProvider | None]:
    """Pick the DDL login for migrations and how to source it.

    Order of preference: a dedicated migration secret, then an explicit env migration login, then the
    application's own DB secret or env login. When a secret is used, the host and the login all come from
    it (so no DB details are needed in the environment).
    """
    if settings.migration_db_secret_id:
        settings = settings.model_copy(update={"db_secret_id": settings.migration_db_secret_id})
        return settings, create_secret_provider(settings)
    if settings.migration_db_user:
        settings = settings.model_copy(
            update={
                "db_user": settings.migration_db_user,
                "db_password": settings.migration_db_password,
                "db_secret_id": None,
            }
        )
        return settings, None
    # No dedicated migration login: reuse the application's DB credentials (secret or env).
    secrets = create_secret_provider(settings) if settings.db_secret_id else None
    return settings, secrets


def run_online() -> None:
    settings, secrets = _migration_engine(get_settings())
    engine = create_db_engine(settings, secrets)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
