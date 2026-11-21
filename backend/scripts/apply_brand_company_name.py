"""Add core.principal.company_id (a company of core.company) and the core.brand.manage permission (ADMIN).

Same SQL as migration 0043_brand_company_name, applied directly (the Alembic chain has two heads).
Idempotent. The script refuses every database except TrishulDev.

    uv run --no-sync python scripts/apply_brand_company_name.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))

from scripts.apply_reporting_assignment_close import _engine  # noqa: E402

STEPS = [
    """
    IF COL_LENGTH(N'core.principal', N'company_name') IS NOT NULL
        ALTER TABLE core.principal DROP COLUMN company_name
    """,
    """
    IF COL_LENGTH(N'core.principal', N'company_id') IS NULL
        ALTER TABLE core.principal ADD company_id BIGINT NULL
            CONSTRAINT FK_core_principal_company_id FOREIGN KEY REFERENCES core.company (id)
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.extended_properties
                   WHERE major_id = OBJECT_ID(N'core.principal') AND name = N'MS_Description'
                     AND minor_id = COLUMNPROPERTY(OBJECT_ID(N'core.principal'), N'company_id', 'ColumnId'))
        EXEC sys.sp_addextendedproperty N'MS_Description',
            N'Company behind the brand, shown beside the brand name',
            N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'company_id'
    """,
    """
    INSERT INTO core.permission (code, module, description)
    SELECT N'core.brand.manage', N'Admin', N'Add and change companies and brands, mark them active or inactive'
    WHERE NOT EXISTS (SELECT 1 FROM core.permission WHERE code = N'core.brand.manage')
    """,
    """
    INSERT INTO core.role_permission (role_id, permission_id)
    SELECT r.id, p.id FROM core.role r JOIN core.permission p ON p.code = N'core.brand.manage'
    WHERE r.code = N'ADMIN'
      AND NOT EXISTS (SELECT 1 FROM core.role_permission rp WHERE rp.role_id = r.id AND rp.permission_id = p.id)
    """,
]


def main() -> None:
    with Session(_engine()) as db:
        name = db.execute(text("SELECT DB_NAME()")).scalar()
        print(f"database {name}", flush=True)
        if name != "TrishulDev":
            raise SystemExit("Refusing to alter brands because this is not TrishulDev.")
        for step in STEPS:
            db.execute(text(step))
        db.commit()
        row = db.execute(
            text("SELECT COUNT(*), COUNT(company_id) FROM core.principal")
        ).one()
        print(f"brands: {row[0]}, with a company: {row[1]}", flush=True)
    print("brand company name applied", flush=True)


if __name__ == "__main__":
    main()
