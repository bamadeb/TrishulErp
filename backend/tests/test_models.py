"""The generated ORM models: complete, consistent with the SQL, and up to date."""

import subprocess
import sys
from pathlib import Path
from typing import get_args

from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

from trishul_api.db.models import (
    Audited,
    Base,
    CashReconciliation,
    CustomerAllocation,
    EmployeeProfile,
    ServiceCall,
    ServiceCallCurrentStatus,
    Supplier,
)

from .helpers import sql_server_2019

BACKEND = Path(__file__).resolve().parents[1]


def test_every_table_is_mapped() -> None:
    configure_mappers()
    assert len(Base.metadata.tables) == 220  # v3 (219) + core.locality (migration 0002)
    assert {table.schema for table in Base.metadata.tables.values()} == {
        "core", "svc", "inv", "pur", "sal", "pre", "hr", "acc", "int", "rpt",
    }  # fmt: skip


def test_every_foreign_key_points_at_a_mapped_table() -> None:
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.column is not None  # raises if the target table or column is missing


def test_every_table_compiles_for_sql_server() -> None:
    dialect = sql_server_2019()
    for table in Base.metadata.tables.values():
        assert "CREATE TABLE" in str(CreateTable(table).compile(dialect=dialect))


def test_v3_changes_are_applied() -> None:
    # 12_gap_remediation.sql replaced the status CHECK and made allocation targets optional.
    assert "Reopened" in get_args(ServiceCallCurrentStatus)
    assert "reopen_count" in ServiceCall.__table__.c
    assert CustomerAllocation.__table__.c.sales_invoice_id.nullable
    assert CashReconciliation.__table__.c.difference_amount.computed is not None


def test_server_generated_columns_are_left_out_of_inserts() -> None:
    columns = ServiceCall.__table__.c
    for name in ("created_at", "is_active", "row_version", "priority"):
        assert columns[name].server_default is not None, name
    assert ServiceCall.__mapper__.version_id_col is columns.row_version


def test_model_options_are_applied() -> None:
    assert issubclass(ServiceCall, Audited)
    assert EmployeeProfile.__audit_masked__ == frozenset({"pan", "bank_account_no"})
    assert Supplier.__audit_masked__ == frozenset({"bank_account_no"})


def test_generated_models_are_up_to_date() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/generate_models.py", "--check"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
