"""Add retrospective leave limits on TrishulDev.

Adds the policy-line columns when they are missing and fills the current Odisha lines
only where the limit is still empty. Existing leave requests are not changed.
The script refuses every database except TrishulDev.

    uv run --no-sync python scripts/apply_leave_backdate.py
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
            raise SystemExit("Refusing to change leave policy lines because this is not TrishulDev.")
        for statement in (
            """
            IF COL_LENGTH(N'hr.leave_policy_line', N'max_backdate_days') IS NULL
                ALTER TABLE hr.leave_policy_line ADD max_backdate_days SMALLINT NULL
            """,
            """
            IF COL_LENGTH(N'hr.leave_policy_line', N'backdate_requires_authorization') IS NULL
                ALTER TABLE hr.leave_policy_line ADD backdate_requires_authorization BIT NOT NULL
                    CONSTRAINT DF_hr_leave_policy_line_backdate_hr DEFAULT 0
            """,
            """
            UPDATE line
            SET max_backdate_days = CASE type.code
                    WHEN N'CL' THEN 2
                    WHEN N'SL' THEN 3
                    WHEN N'EL' THEN 0
                    WHEN N'CO' THEN 0
                    WHEN N'WR' THEN 0
                    WHEN N'LWP' THEN 0
                END,
                backdate_requires_authorization = CASE
                    WHEN type.code = N'LWP' THEN 1
                    ELSE line.backdate_requires_authorization
                END
            FROM hr.leave_policy_line AS line
            INNER JOIN hr.leave_type AS type ON type.id = line.leave_type_id
            WHERE line.max_backdate_days IS NULL
              AND type.code IN (N'CL', N'SL', N'EL', N'CO', N'WR', N'LWP')
            """,
            """
            INSERT INTO hr.leave_policy_line (
                leave_policy_id, leave_type_id, annual_entitlement, accrual_frequency,
                max_backdate_days, backdate_requires_authorization
            )
            SELECT policy.id, type.id, 0, N'None', 0, 1
            FROM hr.leave_policy AS policy
            CROSS JOIN hr.leave_type AS type
            WHERE policy.name = N'Odisha Private Company Leave Policy'
              AND type.code = N'LWP'
              AND NOT EXISTS (
                  SELECT 1 FROM hr.leave_policy_line AS existing
                  WHERE existing.leave_policy_id = policy.id AND existing.leave_type_id = type.id
              )
            """,
            """
            IF NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num = N'0037_leave_backdate')
                INSERT INTO alembic_version (version_num) VALUES (N'0037_leave_backdate')
            """,
        ):
            db.execute(text(statement))
        rows = db.execute(
            text(
                """
                SELECT type.code, line.max_backdate_days, line.backdate_requires_authorization
                FROM hr.leave_policy_line AS line
                INNER JOIN hr.leave_type AS type ON type.id = line.leave_type_id
                WHERE line.is_active = 1
                ORDER BY type.code
                """
            )
        ).all()
        db.commit()
    for code, days, authorized in rows:
        print(f"{code} days={days} authorization={authorized}", flush=True)


if __name__ == "__main__":
    main()
