"""Employee leave register reads core.employee and the stored leave balances."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "core.region",
    "core.employee",
    "core.app_user",
    "hr.department",
    "hr.designation",
    "hr.leave_type",
    "hr.leave_balance",
    "hr.leave_balance_transaction",
    "hr.leave_request",
]
ROOT = "/api/v1/hr/leave/employees"


@pytest.fixture
def db() -> Engine:
    return sqlite_engine(TABLES)


def test_register_uses_stored_balances_and_approved_leave_only(settings: Settings, db: Engine) -> None:
    today = date.today()
    year = today.year if today.month >= 4 else today.year - 1
    _seed(db, today, year)
    with _client(settings, db) as (client, sign_in):
        sign_in(12, frozenset({"hr.leave.view", "hr.leave.manage"}))
        params = {"financialYear": year}
        summary = client.get(f"{ROOT}/summary", params=params)
        assert summary.status_code == 200, summary.text
        assert summary.json()["employees"] == 3
        assert summary.json()["onLeave"] == 1
        assert summary.json()["upcoming"] == 1
        assert Decimal(summary.json()["taken"]) == Decimal("2.0")
        assert any(item["name"] == "Service" for item in summary.json()["departments"])

        listed = client.get(ROOT, params={**params, "search": "EMP0010"})
        assert listed.status_code == 200, listed.text
        body = listed.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["code"] == "EMP0010"
        assert item["department"] == "Service"
        assert item["location"] == "Berhampur"
        assert Decimal(item["cl"]) == Decimal("5.0")
        assert Decimal(item["taken"]) == Decimal("2.0")
        assert item["onLeaveToday"] is True
        assert item["upcoming"]["fromDate"] == (today + timedelta(days=1)).isoformat()

        sign_in(12, frozenset({"hr.leave.view"}))
        scoped = client.get(f"{ROOT}/summary", params=params)
        assert scoped.json()["employees"] == 2

        sign_in(12, frozenset({"hr.leave.view", "hr.leave.manage"}))
        detail = client.get(f"{ROOT}/10", params=params)
        assert detail.status_code == 200, detail.text
        history = detail.json()["history"]
        assert {row["status"] for row in history} == {"Approved", "Pending", "Rejected"}
        assert Decimal(detail.json()["balances"]["CL"]["closing"]) == Decimal("5.0")
        assert Decimal(detail.json()["taken"]) == Decimal("2.0")
        assert detail.json()["lastLeave"]["toDate"] == (today - timedelta(days=1)).isoformat()


def _seed(engine: Engine, today: date, year: int) -> None:
    insert_row(engine, "core.company", id=1, code="TT", legal_name="Trishul")
    insert_row(engine, "core.region", id=1, code="OD", name="Odisha", warehouse_id=1)
    insert_row(engine, "core.branch", id=1, company_id=1, code="BAM", name="Berhampur", region_id=1, state_id=1)
    insert_row(engine, "hr.department", id=1, code="SVC", name="Service")
    insert_row(engine, "hr.designation", id=1, code="SE", name="Service Engineer", department_id=1)
    insert_row(engine, "hr.leave_type", id=1, code="CL", name="Casual Leave", is_paid=True, is_active=True)
    insert_row(
        engine, "core.employee", id=12, company_id=1, employee_code="EMP0012", first_name="Mina", last_name="Rao",
        branch_id=1, department_id=1, designation_id=1, employee_type="Permanent", status="Active", is_active=True,
    )
    insert_row(
        engine, "core.employee", id=10, company_id=1, employee_code="EMP0010", first_name="Asha", last_name="Das",
        branch_id=1, department_id=1, designation_id=1, reporting_manager_id=12, employee_type="Permanent",
        status="Active", is_active=True, date_of_joining=date(2019, 4, 15),
    )
    insert_row(
        engine, "core.employee", id=99, company_id=1, employee_code="EMP0099", first_name="Other", last_name="Person",
        branch_id=1, department_id=1, designation_id=1, employee_type="Permanent", status="Active", is_active=True,
    )
    insert_row(
        engine, "core.employee", id=98, company_id=1, employee_code="EMP0098", first_name="Former", last_name="Staff",
        branch_id=1, department_id=1, designation_id=1, employee_type="Permanent", status="Exited", is_active=True,
    )
    insert_row(
        engine, "hr.leave_balance", employee_id=10, leave_type_id=1, leave_year=year,
        opening="0.0", accrued="5.0", availed="0.0", encashed="0.0", closing="5.0", is_active=True,
    )
    yesterday, tomorrow = today - timedelta(days=1), today + timedelta(days=1)
    _request(engine, 1, yesterday, "1.0", "Approved")
    _request(engine, 2, tomorrow, "1.0", "Approved")
    _request(engine, 3, today, "1.0", "Pending")
    _request(engine, 4, today, "1.0", "Approved")
    _request(engine, 5, yesterday - timedelta(days=3), "5.0", "Rejected")


def _request(engine: Engine, request_id: int, day: date, days: str, status: str) -> None:
    insert_row(
        engine, "hr.leave_request", id=request_id, employee_id=10, leave_type_id=1,
        from_date=day, to_date=day, is_half_day=False, days=days, reason="Sample",
        status=status, is_active=True,
    )


@contextmanager
def _client(settings: Settings, db: Engine) -> Iterator[tuple[TestClient, object]]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    current = {"user": make_user(id=1, employee_id=12, permissions=frozenset({"hr.leave.view"}))}
    api.dependency_overrides[get_current_user] = lambda: current["user"]

    def sign_in(employee_id: int, permissions: frozenset[str]) -> None:
        current["user"] = make_user(id=1, employee_id=employee_id, permissions=permissions)

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current_session:
            set_audit_context(current_session, user_id=1, source="Web", ip_address="127.0.0.1")
            yield current_session

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client, sign_in
