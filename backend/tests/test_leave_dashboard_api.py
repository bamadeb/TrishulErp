"""Leave dashboard figures come from existing leave, employee and balance rows."""

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
    "hr.department",
    "hr.designation",
    "hr.leave_type",
    "hr.leave_balance",
    "hr.leave_request",
]
DASHBOARD = "/api/v1/hr/leave/dashboard"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    today = date.today()
    insert_row(engine, "core.company", id=1, code="TT", legal_name="Trishul")
    insert_row(engine, "core.region", id=1, code="OD", name="Odisha", warehouse_id=1)
    insert_row(engine, "core.branch", id=1, company_id=1, code="BAM", name="Berhampur", region_id=1, state_id=1)
    insert_row(engine, "hr.department", id=1, code="SVC", name="Service")
    insert_row(engine, "hr.department", id=2, code="ADM", name="Admin")
    insert_row(engine, "hr.leave_type", id=1, code="CL", name="Casual Leave", is_paid=True)
    insert_row(engine, "hr.leave_type", id=2, code="SL", name="Sick Leave", is_paid=True)
    employee = {"company_id": 1, "employee_type": "Permanent", "status": "Active", "is_active": True, "branch_id": 1}
    insert_row(
        engine, "core.employee", id=10, employee_code="EMP0010", first_name="Asha", last_name="Das",
        department_id=1, **employee,
    )
    insert_row(
        engine, "core.employee", id=11, employee_code="EMP0011", first_name="Bikash", last_name="Naik",
        department_id=2, reporting_manager_id=10, **employee,
    )
    insert_row(
        engine, "core.employee", id=12, employee_code="EMP0012", first_name="Old", last_name="Hand",
        department_id=1, status="Exited", is_active=False, employee_type="Permanent", company_id=1, branch_id=1,
    )
    insert_row(
        engine, "hr.leave_request", employee_id=10, leave_type_id=1, from_date=today, to_date=today,
        days="1.0", status="Approved", reason="Personal",
    )
    insert_row(
        engine, "hr.leave_request", employee_id=11, leave_type_id=2, from_date=today, to_date=today,
        days="1.0", status="Pending", reason="Fever",
    )
    insert_row(
        engine, "hr.leave_request", employee_id=10, leave_type_id=1, from_date=today, to_date=today,
        days="2.0", status="Rejected", reason="Overlap",
    )
    later = today + timedelta(days=5)
    if later.month == today.month:
        insert_row(
            engine, "hr.leave_request", employee_id=10, leave_type_id=1, from_date=later, to_date=later,
            days="1.0", status="Approved", reason="Later",
        )
    insert_row(
        engine, "hr.leave_balance", employee_id=10, leave_type_id=1, leave_year=today.year,
        opening="3.0", accrued="0", availed="0", encashed="0", closing="3.0",
    )
    insert_row(
        engine, "hr.leave_balance", employee_id=10, leave_type_id=1, leave_year=today.year,
        opening="8.0", accrued="0", availed="1.0", encashed="0", closing="8.0",
    )
    insert_row(
        engine, "hr.leave_balance", employee_id=11, leave_type_id=2, leave_year=today.year,
        opening="4.0", accrued="0", availed="0", encashed="0", closing="4.0",
    )
    return engine


@contextmanager
def _client(
    settings: Settings, db: Engine, permissions: frozenset[str], employee_id: int | None
) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    api.dependency_overrides[get_current_user] = lambda: make_user(
        id=1, employee_id=employee_id, permissions=permissions
    )

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current:
            set_audit_context(current, user_id=1, source="Web", ip_address="127.0.0.1")
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_dashboard_uses_live_rows_and_does_not_double_count(settings: Settings, db: Engine) -> None:
    today = date.today()
    with _client(settings, db, frozenset({"hr.leave.manage"}), 10) as client:
        response = client.get(DASHBOARD)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["activeEmployees"] == 2
        assert body["onLeaveToday"] == 1
        assert body["pendingRequests"] == 1
        assert body["approvedRequests"] >= 1
        assert body["rejectedRequests"] == 1
        assert body["overview"]["onLeave"] == 1
        assert body["overview"]["pending"] == 1
        assert body["overview"]["working"] == 0
        casual = next(row for row in body["balances"] if row["code"] == "CL")
        sick = next(row for row in body["balances"] if row["code"] == "SL")
        assert Decimal(casual["closing"]) == Decimal("8.0")
        assert Decimal(casual["entitlement"]) == Decimal("8.0")
        assert Decimal(casual["used"]) == Decimal("1.0")
        assert Decimal(sick["closing"]) == Decimal("4.0")
        assert body["requests"]["total"] >= 3
        assert body["mine"]["requests"] == []
        assert {row["status"] for row in body["mine"]["history"]} >= {"Approved", "Rejected"}
        assert len(body["trend"]) == 6
        assert body["trend"][-1]["month"].startswith(today.strftime("%b"))

        service = client.get(DASHBOARD, params={"departmentId": 1})
        assert service.status_code == 200, service.text
        assert service.json()["activeEmployees"] == 2
        assert all(row["department"] == "Service" for row in service.json()["requests"]["items"])

        pending = client.get(DASHBOARD, params={"status": "Pending", "pageSize": 1})
        assert pending.json()["requests"]["total"] == 1
        assert len(pending.json()["requests"]["items"]) == 1
        assert pending.json()["requests"]["items"][0]["employeeCode"] == "EMP0011"


def test_a_manager_without_org_permission_sees_only_their_team(settings: Settings, db: Engine) -> None:
    with _client(settings, db, frozenset({"hr.leave.view"}), 10) as client:
        assert client.get(DASHBOARD).json()["activeEmployees"] == 2
        client.app.state.api_v1.dependency_overrides[get_current_user] = lambda: make_user(
            id=1, employee_id=99, permissions=frozenset({"hr.leave.view"})
        )
        response = client.get(DASHBOARD)
        assert response.status_code == 200, response.text
        assert response.json()["activeEmployees"] == 0


def test_an_empty_database_returns_zeros(settings: Settings) -> None:
    engine = sqlite_engine(TABLES)
    with _client(settings, engine, frozenset({"hr.leave.manage"}), None) as client:
        response = client.get(DASHBOARD)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["activeEmployees"] == 0
        assert body["onLeaveToday"] == 0
        assert body["requests"]["items"] == []
        assert body["mine"]["balances"] == []


def test_a_caller_without_permission_is_rejected(settings: Settings, db: Engine) -> None:
    with _client(settings, db, frozenset(), 10) as guest:
        assert guest.get(DASHBOARD).status_code == 403
