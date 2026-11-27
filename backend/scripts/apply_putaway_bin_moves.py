"""Warehouse storage phase 3: receiving bins, put-away and bin moves, item storage rules: migration
0053_putaway_bin_moves, applied directly.

The database's alembic_version table is not in step with this repo (it names revisions from other branches),
so `alembic upgrade heads` cannot run. This runs the migration's own upgrade() in one transaction and leaves
alembic_version alone, like the other apply_* scripts. It does nothing if inv.bin_move already exists, and
refuses every database except TrishulDev.

    uv run --no-sync python -m scripts.apply_putaway_bin_moves
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

MIGRATION = BACKEND / "migrations" / "versions" / "20261127_0053_putaway_bin_moves.py"


def main() -> None:
    spec = importlib.util.spec_from_file_location("migration_0053", MIGRATION)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = _engine()
    with engine.begin() as connection:
        name = connection.execute(text("SELECT DB_NAME()")).scalar()
        print(f"database {name}", flush=True)
        if name != "TrishulDev":
            raise SystemExit("Refusing to change the schema because this is not TrishulDev.")
        if connection.execute(text("SELECT OBJECT_ID(N'inv.scan_log')")).scalar() is None:
            raise SystemExit("Apply 0052 first: scripts.apply_barcodes_scan.")
        if connection.execute(text("SELECT OBJECT_ID(N'inv.bin_move')")).scalar() is not None:
            print("inv.bin_move already exists; nothing to do.")
            return
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        columns = connection.execute(
            text("""
                SELECT name FROM sys.columns
                WHERE (object_id = OBJECT_ID(N'inv.bin') AND name = N'is_receiving')
                   OR (object_id = OBJECT_ID(N'core.item') AND name = N'storage_type')
                ORDER BY name
            """)
        ).scalars()
        print("new columns:", list(columns))
        tables = ("inv.item_storage_rule", "inv.bin_move", "inv.bin_move_line")
        print("tables:", [t for t in tables if connection.execute(text("SELECT OBJECT_ID(:t)"), {"t": t}).scalar()])
        codes = connection.execute(
            text("SELECT code FROM inv.movement_type WHERE code IN (N'BIN_OUT', N'BIN_IN') ORDER BY code")
        ).scalars()
        print("movement types:", list(codes))
        grants = connection.execute(
            text("""
                SELECT p.code, STRING_AGG(r.code, ', ') WITHIN GROUP (ORDER BY r.code)
                FROM core.permission p
                LEFT JOIN core.role_permission rp ON rp.permission_id = p.id
                LEFT JOIN core.role r ON r.id = rp.role_id
                WHERE p.code = N'inv.binmove.manage'
                GROUP BY p.code ORDER BY p.code
            """)
        ).all()
        for code, roles in grants:
            print(f"{code}: {roles or '(no roles)'}")
    engine.dispose()


if __name__ == "__main__":
    main()
