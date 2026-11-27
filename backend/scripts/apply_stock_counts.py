"""Warehouse storage phase 5: physical stock counts (count scope, blind counts, count bins, the count
permissions): migration 0054_stock_counts, applied directly.

The database's alembic_version table is not in step with this repo (it names revisions from other branches),
so `alembic upgrade heads` cannot run. This runs the migration's own upgrade() in one transaction and leaves
alembic_version alone, like the other apply_* scripts. It does nothing if inv.stock_count_bin already exists, and
refuses every database except TrishulDev.

    uv run --no-sync python -m scripts.apply_stock_counts
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

MIGRATION = BACKEND / "migrations" / "versions" / "20261127_0054_stock_counts.py"


def main() -> None:
    spec = importlib.util.spec_from_file_location("migration_0054", MIGRATION)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = _engine()
    with engine.begin() as connection:
        name = connection.execute(text("SELECT DB_NAME()")).scalar()
        print(f"database {name}", flush=True)
        if name != "TrishulDev":
            raise SystemExit("Refusing to change the schema because this is not TrishulDev.")
        if connection.execute(text("SELECT OBJECT_ID(N'inv.bin_move')")).scalar() is None:
            raise SystemExit("Apply 0053 first: scripts.apply_putaway_bin_moves.")
        if connection.execute(text("SELECT OBJECT_ID(N'inv.stock_count_bin')")).scalar() is not None:
            print("inv.stock_count_bin already exists; nothing to do.")
            return
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        columns = connection.execute(
            text("""
                SELECT OBJECT_NAME(object_id) + N'.' + name FROM sys.columns
                WHERE object_id IN (OBJECT_ID(N'inv.stock_count'), OBJECT_ID(N'inv.stock_count_line'))
                  AND name IN (N'scope', N'storage_rack_id', N'is_blind', N'remarks', N'closed_at',
                               N'closed_by_user_id', N'posted_at', N'posted_by_user_id', N'counted_at', N'is_expected')
                ORDER BY 1
            """)
        ).scalars()
        print("new columns:", list(columns))
        print(
            "table inv.stock_count_bin:",
            bool(connection.execute(text("SELECT OBJECT_ID(N'inv.stock_count_bin')")).scalar()),
        )
        grants = connection.execute(
            text("""
                SELECT p.code, STRING_AGG(r.code, ', ') WITHIN GROUP (ORDER BY r.code)
                FROM core.permission p
                LEFT JOIN core.role_permission rp ON rp.permission_id = p.id
                LEFT JOIN core.role r ON r.id = rp.role_id
                WHERE p.code IN (N'inv.count.manage', N'inv.count.approve')
                GROUP BY p.code ORDER BY p.code
            """)
        ).all()
        for code, roles in grants:
            print(f"{code}: {roles or '(no roles)'}")
    engine.dispose()


if __name__ == "__main__":
    main()
