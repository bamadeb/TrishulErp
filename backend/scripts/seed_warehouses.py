"""Seed the warehouses and map each branch to the warehouse that supplies it (proposal, geography-based).

    uv run python scripts/seed_warehouses.py            show what would change (nothing is written)
    uv run python scripts/seed_warehouses.py --apply    write it

A warehouse is a core.branch row of type Warehouse, and a branch points at its warehouse through
parent_warehouse_id. A warehouse can itself be a branch: Jharsuguda and Barbil are existing branches that
become warehouses; Bhubaneswar is added. Idempotent. Edit MAPPING below and run again to move a branch.
Branches not listed (e.g. the head office) are never touched. Admin can also change the mapping on the
Administration > Warehouses screen.
"""

import sys

from sqlalchemy import text

from trishul_api.config import get_settings
from trishul_api.db.engine import create_db_engine
from trishul_api.secrets import create_secret_provider

WAREHOUSES = {"BBSR": "Bhubaneswar", "JHARSUGUDA": "Jharsuguda", "BARBIL": "Barbil"}

# warehouse code -> branch codes it supplies
MAPPING: dict[str, list[str]] = {
    "BBSR": [
        "BHADRAK", "BALASORE", "JAJPUR", "PARADEEP", "BARIPADA",
        "ANGUL", "ANGULMCL", "NAYAGARH", "WORKSHOP",
        "BERHAMPUR", "GUNUPUR", "RAYAGADA", "JEYPORE", "DAMANJODI", "MALKANGIRI", "BHPT",
    ],  # fmt: skip
    "JHARSUGUDA": ["SAMBALPUR", "BOLANGIR", "ROURKELA"],
    "BARBIL": ["KEONJHAR", "KOIRA"],
}


def main(apply: bool) -> None:
    settings = get_settings()
    engine = create_db_engine(settings, create_secret_provider(settings))
    with engine.begin() as db:
        for code, name in WAREHOUSES.items():
            if db.execute(text("SELECT 1 FROM core.branch WHERE code = :c"), {"c": code}).first() is None:
                print(f"+ warehouse {code} ({name})")
                db.execute(
                    text(
                        "INSERT INTO core.branch (company_id, code, name, branch_type, state_id) "
                        "SELECT TOP 1 company_id, :c, :n, N'Warehouse', state_id FROM core.branch "
                        "WHERE branch_type = N'Head office' ORDER BY id"
                    ),
                    {"c": code, "n": name},
                )
            elif db.execute(
                text(
                    "UPDATE core.branch SET branch_type = N'Warehouse', parent_warehouse_id = NULL, region_id = NULL, "
                    "updated_at = SYSUTCDATETIME() WHERE code = :c AND branch_type <> N'Warehouse'"
                ),
                {"c": code},
            ).rowcount:
                print(f"~ {code} becomes a warehouse")
        ids = {code: bid for bid, code in db.execute(text("SELECT id, code FROM core.branch"))}
        missing = [c for w, codes in MAPPING.items() for c in [w, *codes] if c not in ids]
        if missing:
            raise SystemExit(f"Not found in core.branch: {', '.join(missing)}")
        for warehouse, codes in MAPPING.items():
            for code in codes:
                changed = db.execute(
                    text(
                        "UPDATE core.branch SET parent_warehouse_id = :w, updated_at = SYSUTCDATETIME() "
                        "WHERE id = :b AND (parent_warehouse_id IS NULL OR parent_warehouse_id <> :w)"
                    ),
                    {"w": ids[warehouse], "b": ids[code]},
                ).rowcount
                print(f"  {'map ' if changed else 'ok  '} {code} -> {warehouse}")
        if not apply:
            db.rollback()
            print("\nDry run: nothing written. Re-run with --apply.")


if __name__ == "__main__":
    main("--apply" in sys.argv)
