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

from trishul_api.config import get_settings
from trishul_api.db.engine import create_db_engine


def run_offline() -> None:
    context.configure(url=URL.create("mssql+pyodbc"), literal_binds=True, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    settings = get_settings()
    if settings.migration_db_user:
        settings = settings.model_copy(
            update={"db_user": settings.migration_db_user, "db_password": settings.migration_db_password}
        )
    engine = create_db_engine(settings)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
