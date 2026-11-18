"""Add the close date on hr.reporting_assignment and allow a removal row.

The live reporting manager stays on core.employee. Existing employees are not changed.
The script refuses every database except TrishulDev.

    uv run --no-sync python scripts/apply_reporting_assignment_close.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))

from trishul_api.config import get_settings  # noqa: E402
from trishul_api.db.engine import create_db_engine  # noqa: E402
from trishul_api.secrets import create_secret_provider  # noqa: E402


def _engine():
    settings = get_settings()
    if settings.migration_db_secret_id:
        settings = settings.model_copy(update={"db_secret_id": settings.migration_db_secret_id})
        return create_db_engine(settings, create_secret_provider(settings))
    if settings.migration_db_user:
        settings = settings.model_copy(
            update={
                "db_user": settings.migration_db_user,
                "db_password": settings.migration_db_password,
                "db_secret_id": None,
            }
        )
        return create_db_engine(settings, None)
    secrets = create_secret_provider(settings) if settings.db_secret_id else None
    return create_db_engine(settings, secrets)


def main() -> None:
    engine = _engine()
    with Session(engine) as db:
        name = db.execute(text("SELECT DB_NAME()")).scalar()
        print(f"database {name}", flush=True)
        if name != "TrishulDev":
            raise SystemExit("Refusing to alter reporting assignment because this is not TrishulDev.")
        present = db.execute(text("SELECT OBJECT_ID(N'hr.reporting_assignment', N'U')")).scalar()
        if present is None:
            raise SystemExit("hr.reporting_assignment does not exist. Apply that table first.")
        db.execute(
            text(
                """
                IF COL_LENGTH(N'hr.reporting_assignment', N'effective_to') IS NULL
                    ALTER TABLE hr.reporting_assignment ADD effective_to DATE NULL
                """
            )
        )
        db.execute(text("ALTER TABLE hr.reporting_assignment ALTER COLUMN manager_id BIGINT NULL"))
        db.execute(
            text(
                """
                IF NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num = N'0039_reporting_close')
                    INSERT INTO alembic_version (version_num) VALUES (N'0039_reporting_close')
                """
            )
        )
        db.commit()
    print("hr.reporting_assignment close date applied", flush=True)


if __name__ == "__main__":
    main()
