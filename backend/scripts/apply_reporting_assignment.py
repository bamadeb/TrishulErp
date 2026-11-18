"""Create hr.reporting_assignment on TrishulDev.

The live reporting manager stays on core.employee. Existing employees are not changed.
The script refuses every database except TrishulDev.

    uv run --no-sync python scripts/apply_reporting_assignment.py
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
            raise SystemExit("Refusing to create the reporting assignment table because this is not TrishulDev.")
        db.execute(
            text(
                """
                IF OBJECT_ID(N'hr.reporting_assignment', N'U') IS NULL
                BEGIN
                    CREATE TABLE hr.reporting_assignment (
                        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_hr_reporting_assignment PRIMARY KEY,
                        employee_id BIGINT NOT NULL,
                        previous_manager_id BIGINT NULL,
                        manager_id BIGINT NOT NULL,
                        effective_from DATE NOT NULL,
                        remarks NVARCHAR(300) NULL,
                        created_at DATETIME2(0) NOT NULL
                            CONSTRAINT DF_hr_reporting_assignment_created_at DEFAULT (SYSUTCDATETIME()),
                        created_by_user_id BIGINT NULL,
                        is_active BIT NOT NULL CONSTRAINT DF_hr_reporting_assignment_is_active DEFAULT (1),
                        CONSTRAINT FK_hr_reporting_assignment_employee
                            FOREIGN KEY (employee_id) REFERENCES core.employee(id),
                        CONSTRAINT FK_hr_reporting_assignment_previous_manager
                            FOREIGN KEY (previous_manager_id) REFERENCES core.employee(id),
                        CONSTRAINT FK_hr_reporting_assignment_manager
                            FOREIGN KEY (manager_id) REFERENCES core.employee(id)
                    );
                    CREATE INDEX IX_hr_reporting_assignment_employee ON hr.reporting_assignment(employee_id);
                END
                """
            )
        )
        db.execute(
            text(
                """
                IF NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num = N'0038_reporting_assignment')
                    INSERT INTO alembic_version (version_num) VALUES (N'0038_reporting_assignment')
                """
            )
        )
        present = db.execute(
            text("SELECT OBJECT_ID(N'hr.reporting_assignment', N'U')")
        ).scalar()
        db.commit()
    print(f"hr.reporting_assignment {present}", flush=True)


if __name__ == "__main__":
    main()
