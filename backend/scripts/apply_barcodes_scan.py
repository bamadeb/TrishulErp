"""Warehouse storage phase 2: optional item barcodes, the scan log and the barcode permissions: migration
0052_barcodes_scan, applied directly.

The database's alembic_version table is not in step with this repo (it names revisions from other branches),
so `alembic upgrade heads` cannot run. This runs the migration's own upgrade() in one transaction and leaves
alembic_version alone, like the other apply_* scripts. It does nothing if inv.scan_log already exists, and
refuses every database except TrishulDev.

    uv run --no-sync python -m scripts.apply_barcodes_scan
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))

from scripts.apply_reporting_assignment_close import _engine  # noqa: E402

MIGRATION = BACKEND / "migrations" / "versions" / "20261127_0052_barcodes_scan.py"


def main() -> None:
    spec = importlib.util.spec_from_file_location("migration_0052", MIGRATION)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = _engine()
    with engine.begin() as connection:
        name = connection.execute(text("SELECT DB_NAME()")).scalar()
        print(f"database {name}", flush=True)
        if name != "TrishulDev":
            raise SystemExit("Refusing to change the schema because this is not TrishulDev.")
        if connection.execute(text("SELECT OBJECT_ID(N'inv.storage_rack')")).scalar() is None:
            raise SystemExit("Apply 0051 first: scripts.apply_storage_racks.")
        if connection.execute(text("SELECT OBJECT_ID(N'inv.scan_log')")).scalar() is not None:
            print("inv.scan_log already exists; nothing to do.")
            return
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        columns = connection.execute(
            text("""
                SELECT name FROM sys.columns
                WHERE object_id = OBJECT_ID(N'inv.item_barcode') AND name IN (N'source', N'is_primary')
                ORDER BY name
            """)
        ).scalars()
        print("new item_barcode columns:", list(columns))
        print("inv.scan_log:", connection.execute(text("SELECT OBJECT_ID(N'inv.scan_log')")).scalar() is not None)
        grants = connection.execute(
            text("""
                SELECT p.code, STRING_AGG(r.code, ', ') WITHIN GROUP (ORDER BY r.code)
                FROM core.permission p
                LEFT JOIN core.role_permission rp ON rp.permission_id = p.id
                LEFT JOIN core.role r ON r.id = rp.role_id
                WHERE p.code LIKE N'inv.barcode.%'
                GROUP BY p.code ORDER BY p.code
            """)
        ).all()
        for code, roles in grants:
            print(f"{code}: {roles or '(no roles)'}")
    engine.dispose()


if __name__ == "__main__":
    main()
