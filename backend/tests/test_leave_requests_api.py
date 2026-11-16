"""Leave request queue reads core.employee and approves against hr.leave_request."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import LeaveBalance
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "core.region",
    "core.employee",
    "core.app_user",
    "core.status_history",
    "hr.department",
    "hr.designation",
    "hr.leave_type",
    "hr.leave_type_setting",
    "hr.leave_policy",
    "hr.leave_policy_line",
    "hr.leave_policy_assignment",
    "hr.leave_balance",
    "hr.leave_request",
    "hr.employment_history",
    "hr.employee_shift",
    "hr.holiday",
]
ROOT = "/api/v1/hr/leave/requests"


@pytest.fixture
def db() -> Engine:
    return sqlite_engine(TABLES)


def test_queue_lists_real_employees_and_approval_deducts_balance(settings: Settings, db: Engine) -> None:
    monday = _next_monday(date.today())
    year = monday.year if monday.month >= 4 else monday.year - 1
    _seed(db, monday, year)
    with _client(settings, db) as (client, sign_in):
        sign_in(12, frozenset({"hr.leave.view", "hr.leave.manage"}))
        listed = client.get(ROOT, params={"fromDate": monday.isoformat(), "toDate": monday.isoformat()})
        assert listed.status_code == 200, listed.text
        body = listed.json()
        assert body["total"] == 1
        assert body["items"][0]["employee"]["code"] == "EMP0010"
        assert body["items"][0]["employee"]["department"] == "Service"
        assert body["items"][0]["displayId"] == "LV-0090"

        summary = client.get(f"{ROOT}/summary", params={"fromDate": monday.isoformat(), "toDate": monday.isoformat()})
        assert summary.status_code == 200, summary.text
        assert summary.json()["pending"] == 1
        assert summary.json()["approved"] == 0
        assert any(item["name"] == "Service" for item in summary.json()["departments"])

        searched = client.get(ROOT, params={"search": "EMP0010", "status": "Pending"})
        assert searched.status_code == 200
        assert searched.json()["total"] == 2

        sign_in(10, frozenset({"hr.leave.manage"}))
        refused = client.post(f"{ROOT}/90/approve")
        assert refused.status_code == 400
        assert refused.json()["detail"] == "You cannot decide your own leave."

        sign_in(12, frozenset({"hr.leave.view"}))
        blocked = client.post(f"{ROOT}/90/approve")
        assert blocked.status_code == 403

        sign_in(12, frozenset({"hr.leave.approve"}))
        approved = client.post(f"{ROOT}/90/approve")
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "Approved"
        assert Decimal(approved.json()["days"]) == Decimal("1.0")
        closing, availed = _balance(db, 10, 1, year)
        assert availed == Decimal("1.0")
        assert closing == Decimal("4.0")
        again = client.post(f"{ROOT}/90/approve")
        assert again.status_code == 400
        rejected = client.post(f"{ROOT}/91/reject", json={"remarks": "Choose another date"})
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "Rejected"
        closing, availed = _balance(db, 10, 1, year)
        assert availed == Decimal("1.0")
        assert closing == Decimal("4.0")
        sign_in(12, frozenset({"hr.leave.view", "hr.leave.approve"}))
        history = client.get(f"{ROOT}/91/history")
        assert history.status_code == 200
        assert history.json()[-1]["action"] == "Rejected"
        assert history.json()[-1]["remarks"] == "Choose another date"


def _seed(engine: Engine, monday: date, year: int) -> None:
    insert_row(engine, "core.company", id=1, code="TT", legal_name="Trishul")
    insert_row(engine, "core.region", id=1, code="OD", name="Odisha", warehouse_id=1)
    insert_row(engine, "core.branch", id=1, company_id=1, code="BAM", name="Berhampur", region_id=1, state_id=1)
    insert_row(engine, "hr.department", id=1, code="SVC", name="Service")
    insert_row(engine, "hr.designation", id=1, code="SE", name="Service Engineer", department_id=1)
    insert_row(engine, "hr.leave_type", id=1, code="CL", name="Casual Leave", is_paid=True, is_active=True)
    insert_row(
        engine, "hr.leave_policy", id=1, name="Staff", applies_during_probation=True, is_active=True,
        effective_from=date(year, 4, 1),
    )
    insert_row(
        engine, "hr.leave_policy_line", leave_policy_id=1, leave_type_id=1, annual_entitlement="12.0",
        accrual_frequency="Yearly", is_active=True,
    )
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
        engine, "hr.leave_balance", employee_id=10, leave_type_id=1, leave_year=year,
        opening="5.0", accrued="0", availed="0", encashed="0", closing="5.0", is_active=True,
    )
    created = datetime.now(UTC).replace(tzinfo=None)
    insert_row(
        engine, "hr.leave_request", id=90, employee_id=10, leave_type_id=1,
        from_date=monday, to_date=monday, is_half_day=False, days="1.0", reason="Personal work",
        status="Pending", is_active=True, created_at=created, created_by_user_id=1,
    )
    insert_row(
        engine, "hr.leave_request", id=91, employee_id=10, leave_type_id=1,
        from_date=monday + timedelta(days=1), to_date=monday + timedelta(days=1), is_half_day=False, days="1.0",
        reason="Errand", status="Pending", is_active=True, created_at=created, created_by_user_id=1,
    )


def _next_monday(today: date) -> date:
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def _balance(engine: Engine, employee_id: int, leave_type_id: int, year: int) -> tuple[Decimal, Decimal]:
    with Session(engine) as session:
        row = session.scalar(
            select(LeaveBalance).where(
                LeaveBalance.employee_id == employee_id,
                LeaveBalance.leave_type_id == leave_type_id,
                LeaveBalance.leave_year == year,
            )
        )
        assert row is not None
        return row.closing, row.availed


@contextmanager
def _client(settings: Settings, db: Engine) -> Iterator[tuple[TestClient, object]]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    current = {"user": make_user(id=1, employee_id=12, permissions=frozenset({"hr.leave.view"}))}
    api.dependency_overrides[get_current_user] = lambda: current["user"]

    def sign_in(employee_id: int, permissions: frozenset[str]) -> None:
        current["user"] = make_user(id=1, employee_id=employee_id, permissions=permissions, display_name="Mina Rao")

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current_session:
            set_audit_context(current_session, user_id=1, source="Web", ip_address="127.0.0.1")
            yield current_session

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client, sign_in
