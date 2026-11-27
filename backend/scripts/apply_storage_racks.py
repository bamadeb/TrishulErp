"""Warehouse storage phase 1: racks with generated bins, flexible bins and locations: migration 0051_storage_racks,
applied directly.

The database's alembic_version table is not in step with this repo (it names revisions from other branches),
so `alembic upgrade heads` cannot run. This runs the migration's own upgrade() in one transaction and leaves
alembic_version alone, like the other apply_* scripts. It does nothing if inv.storage_rack already exists, and
refuses every database except TrishulDev.

    uv run --no-sync python -m scripts.apply_storage_racks
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

MIGRATION = BACKEND / "migrations" / "versions" / "20261127_0051_storage_racks.py"


def main() -> None:
    spec = importlib.util.spec_from_file_location("migration_0051", MIGRATION)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = _engine()
    with engine.begin() as connection:
        name = connection.execute(text("SELECT DB_NAME()")).scalar()
        print(f"database {name}", flush=True)
        if name != "TrishulDev":
            raise SystemExit("Refusing to change the schema because this is not TrishulDev.")
        if connection.execute(text("SELECT OBJECT_ID(N'inv.price_import')")).scalar() is None:
            raise SystemExit("Apply 0050 first: scripts.apply_price_import.")
        if connection.execute(text("SELECT OBJECT_ID(N'inv.storage_rack')")).scalar() is not None:
            print("inv.storage_rack already exists; nothing to do.")
            return
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        print("tables:", [
            t for t in ("inv.storage_rack",)
            if connection.execute(text("SELECT OBJECT_ID(:t)"), {"t": t}).scalar() is not None
        ])  # fmt: skip
        columns = (
            connection.execute(
                text("""
                SELECT CONCAT(OBJECT_NAME(object_id), '.', name) FROM sys.columns
                WHERE (object_id = OBJECT_ID(N'inv.bin') AND name IN (N'storage_rack_id', N'bin_type', N'is_blocked'))
                   OR (object_id = OBJECT_ID(N'core.location') AND name = N'requires_bin')
                ORDER BY 1
            """)
            )
            .scalars()
            .all()
        )
        print("new columns:", list(columns))
        width = connection.execute(
            text("SELECT max_length / 2 FROM sys.columns WHERE object_id = OBJECT_ID(N'inv.bin') AND name = N'code'")
        ).scalar()
        print(f"inv.bin.code length: {width}")
    engine.dispose()


if __name__ == "__main__":
    main()
