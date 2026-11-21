"""Add core.principal.inspection_report_required (Tata Hitachi = 0, every other brand = 1).

Same SQL as migration 0044_brand_inspection_report, applied directly (the Alembic chain has two heads).
Idempotent. The script refuses every database except TrishulDev.

    uv run --no-sync python -m scripts.apply_brand_inspection_report
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))

from scripts.apply_reporting_assignment_close import _engine  # noqa: E402

ADD_COLUMN = """
IF COL_LENGTH(N'core.principal', N'inspection_report_required') IS NULL
BEGIN
    ALTER TABLE core.principal ADD inspection_report_required BIT NOT NULL
        CONSTRAINT DF_core_principal_inspection_report_required DEFAULT (1)
    EXEC sys.sp_addextendedproperty N'MS_Description',
        N'Service reports of this brand need the full inspection report; when off, a note or a file is enough',
        N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'inspection_report_required'
    EXEC (N'UPDATE core.principal SET inspection_report_required = 0 WHERE code = N''TATA_HITACHI''')
END
"""


def main() -> None:
    with Session(_engine()) as db:
        name = db.execute(text("SELECT DB_NAME()")).scalar()
        print(f"database {name}", flush=True)
        if name != "TrishulDev":
            raise SystemExit("Refusing to alter brands because this is not TrishulDev.")
        db.execute(text(ADD_COLUMN))
        db.commit()
        for code, flag in db.execute(text("SELECT code, inspection_report_required FROM core.principal")):
            print(f"  {code}: inspection report required = {flag}", flush=True)


if __name__ == "__main__":
    main()
