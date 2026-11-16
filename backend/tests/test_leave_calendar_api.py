"""Leave calendar reads active employees, leave requests and holidays."""

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
    "hr.leave_request",
    "hr.holiday",
]
ROOT = "/api/v1/hr/leave/calendar"


@pytest.fixture
def db() -> Engine:
    return sqlite_engine(TABLES)


def test_calendar_uses_active_employees_and_existing_leave(settings: Settings, db: Engine) -> None:
    today = date.today()
    _seed(db, today)
    with _client(settings, db) as (client, sign_in):
        sign_in(12, frozenset({"hr.leave.view", "hr.leave.manage"}))
        params = {"year": today.year, "month": today.month}
        board = client.get(ROOT, params=params)
        assert board.status_code == 200, board.text
        body = board.json()
        assert body["summary"]["totalEmployees"] == 3
        assert body["summary"]["onLeaveToday"] == 1
        assert Decimal(body["summary"]["onLeavePercent"]) == (Decimal(100) / Decimal(3)).quantize(Decimal("0.01"))
        assert body["summary"]["pendingApproval"] == 1
        assert body["summary"]["upcomingLeaves"] == 1
        assert body["summary"]["rejectedMtd"] == 1
        assert any(item["displayId"] == "LV-0004" and item["status"] == "Approved" for item in body["entries"])
        assert any(item["name"] == "Office holiday" for item in body["holidays"])
        assert any(item["name"] == "Service" for item in body["departments"])
        assert any(item["code"] == "CL" for item in body["leaveTypes"])

        summary = client.get(f"{ROOT}/summary", params=params)
        assert summary.status_code == 200, summary.text
        assert summary.json()["onLeaveToday"] == 1

        narrowed = client.get(ROOT, params={**params, "search": "EMP0099"})
        assert narrowed.json()["summary"]["totalEmployees"] == 1
        assert narrowed.json()["summary"]["onLeaveToday"] == 0
        assert narrowed.json()["entries"] == []

        sign_in(12, frozenset({"hr.leave.view"}))
        scoped = client.get(f"{ROOT}/summary", params=params)
        assert scoped.json()["totalEmployees"] == 2
        assert scoped.json()["onLeaveToday"] == 1


def _seed(engine: Engine, today: date) -> None:
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
        status="Active", is_active=True,
    )
    insert_row(
        engine, "core.employee", id=99, company_id=1, employee_code="EMP0099", first_name="Other", last_name="Person",
        branch_id=1, department_id=1, designation_id=1, employee_type="Permanent", status="Active", is_active=True,
    )
    insert_row(
        engine, "core.employee", id=98, company_id=1, employee_code="EMP0098", first_name="Former", last_name="Staff",
        branch_id=1, department_id=1, designation_id=1, employee_type="Permanent", status="Exited", is_active=True,
    )
    yesterday, tomorrow = today - timedelta(days=1), today + timedelta(days=1)
    _request(engine, 1, yesterday, "Approved")
    _request(engine, 2, tomorrow, "Approved")
    _request(engine, 3, today, "Pending")
    _request(engine, 4, today, "Approved")
    _request(engine, 5, date(today.year, today.month, 1), "Rejected")
    insert_row(
        engine, "hr.holiday", branch_id=1, holiday_date=date(today.year, today.month, min(today.day, 28)),
        name="Office holiday", holiday_type="National", is_active=True,
    )


def _request(engine: Engine, request_id: int, day: date, status: str) -> None:
    insert_row(
        engine, "hr.leave_request", id=request_id, employee_id=10, leave_type_id=1,
        from_date=day, to_date=day, is_half_day=False, days="1.0", reason="Sample",
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
