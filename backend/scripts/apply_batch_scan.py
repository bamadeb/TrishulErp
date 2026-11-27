"""Item ageing by barcode: a scanned GRN batch number is logged as a Lot scan: migration 0055_batch_scan,
applied directly.

The database's alembic_version table is not in step with this repo (it names revisions from other branches),
so `alembic upgrade heads` cannot run. This runs the migration's own upgrade() in one transaction and leaves
alembic_version alone, like the other apply_* scripts. It does nothing if the scan log already allows Lot, and
refuses every database except TrishulDev.

    uv run --no-sync python -m scripts.apply_batch_scan
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

MIGRATION = BACKEND / "migrations" / "versions" / "20261127_0055_batch_scan.py"
CHECK = """
    SELECT definition FROM sys.check_constraints WHERE name = N'CK_inv_scan_log_resolved_type'
"""


def main() -> None:
    spec = importlib.util.spec_from_file_location("migration_0055", MIGRATION)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = _engine()
    with engine.begin() as connection:
        name = connection.execute(text("SELECT DB_NAME()")).scalar()
        print(f"database {name}", flush=True)
        if name != "TrishulDev":
            raise SystemExit("Refusing to change the schema because this is not TrishulDev.")
        if connection.execute(text("SELECT OBJECT_ID(N'inv.stock_count_bin')")).scalar() is None:
            raise SystemExit("Apply 0054 first: scripts.apply_stock_counts.")
        if "Lot" in (connection.execute(text(CHECK)).scalar() or ""):
            print("inv.scan_log already allows Lot; nothing to do.")
            return
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        print("resolved_type check:", connection.execute(text(CHECK)).scalar())
    engine.dispose()


if __name__ == "__main__":
    main()
