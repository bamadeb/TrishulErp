"""Add the SERVICE_MAX_PENDING_CALLS setting (default 3) and the svc.config.manage permission (Admin role).

Same SQL as migration 0045_max_pending_calls, applied directly (the Alembic chain has two heads).
Idempotent. The script refuses every database except TrishulDev.

    uv run --no-sync python -m scripts.apply_max_pending_calls
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))

from scripts.apply_reporting_assignment_close import _engine  # noqa: E402

STATEMENTS = [
    """
IF NOT EXISTS (SELECT 1 FROM core.system_setting
               WHERE setting_key = N'SERVICE_MAX_PENDING_CALLS' AND company_id IS NULL)
    INSERT INTO core.system_setting (company_id, setting_key, setting_value, data_type, description)
    VALUES (NULL, N'SERVICE_MAX_PENDING_CALLS', N'3', N'Number',
            N'An engineer with more pending calls than this cannot be given another')
""",
    """
IF NOT EXISTS (SELECT 1 FROM core.permission WHERE code = N'svc.config.manage')
    INSERT INTO core.permission (code, module, description)
    VALUES (N'svc.config.manage', N'Service', N'Change service settings, such as the pending-call limit per engineer')
""",
    """
INSERT INTO core.role_permission (role_id, permission_id)
SELECT r.id, p.id FROM core.role r
JOIN core.permission p ON p.code = N'svc.config.manage'
WHERE r.code = N'ADMIN'
  AND NOT EXISTS (SELECT 1 FROM core.role_permission rp WHERE rp.role_id = r.id AND rp.permission_id = p.id)
""",
]


def main() -> None:
    with Session(_engine()) as db:
        name = db.execute(text("SELECT DB_NAME()")).scalar()
        print(f"database {name}", flush=True)
        if name != "TrishulDev":
            raise SystemExit("Refusing to change settings because this is not TrishulDev.")
        for statement in STATEMENTS:
            db.execute(text(statement))
        db.commit()
        print("max pending calls =", db.execute(text(
            "SELECT setting_value FROM core.system_setting WHERE setting_key = N'SERVICE_MAX_PENDING_CALLS'")).scalar())


if __name__ == "__main__":
    main()
