"""Saving a reporting manager updates the employee and keeps the assignment."""

from collections.abc import Iterator
from datetime import date, timedelta

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import Employee, ReportingAssignment
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "hr.department",
    "hr.designation",
    "core.employee",
    "core.app_user",
    "hr.reporting_assignment",
]
LEAD, MID, STAFF, INACTIVE = 10, 11, 12, 13
URL = "/api/v1/hr/reporting/assignments"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=1, code="TRISHUL", legal_name="Trishul Pvt Ltd")
    insert_row(engine, "core.branch", id=1, company_id=1, code="HO", name="Head office")
    insert_row(engine, "hr.department", id=1, code="SVC", name="Service")
    insert_row(engine, "hr.designation", id=1, code="TL", name="Team Lead", grade="L4", department_id=1)
    _employee(engine, LEAD, "E010", "Padma", manager_id=None)
    _employee(engine, MID, "E011", "Jyoti", manager_id=LEAD)
    _employee(engine, STAFF, "E012", "Satya", manager_id=MID)
    _employee(engine, INACTIVE, "E013", "Old", manager_id=None, is_active=False)
    return engine


def _employee(
    engine: Engine, row_id: int, code: str, first_name: str, *, manager_id: int | None, is_active: bool = True
) -> None:
    insert_row(
        engine,
        "core.employee",
        id=row_id,
        company_id=1,
        branch_id=1,
        department_id=1,
        designation_id=1,
        employee_code=code,
        first_name=first_name,
        employee_type="Permanent",
        status="Active",
        reporting_manager_id=manager_id,
        is_active=is_active,
    )


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(id=1, permissions=frozenset({"core.employee.view", "core.employee.manage"}))
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current:
            set_audit_context(current, user_id=1, source="Web", ip_address="127.0.0.1")
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _save(client: TestClient, employee_id: int, manager_id: int) -> httpx.Response:
    return client.post(
        URL,
        json={
            "employeeId": employee_id,
            "reportingManagerId": manager_id,
            "effectiveFrom": "2026-11-16",
            "remarks": " Team change ",
        },
    )


def test_save_updates_the_manager_and_keeps_the_previous_one(client: TestClient, db: Engine) -> None:
    response = _save(client, STAFF, LEAD)
    assert response.status_code == 201
    body = response.json()
    assert body["employeeId"] == STAFF
    assert body["previousManagerId"] == MID
    assert body["managerId"] == LEAD
    assert body["effectiveFrom"] == "2026-11-16"
    assert body["remarks"] == "Team change"
    with Session(db) as session:
        employee = session.get(Employee, STAFF)
        assert employee is not None
        assert employee.reporting_manager_id == LEAD
        history = session.scalars(select(ReportingAssignment).where(ReportingAssignment.employee_id == STAFF)).one()
        assert history.previous_manager_id == MID
        assert history.manager_id == LEAD
        assert history.created_by_user_id == 1


def test_save_rejects_self_assignment_and_a_cycle(client: TestClient) -> None:
    self_assigned = _save(client, STAFF, STAFF)
    assert self_assigned.status_code == 400
    assert "themselves" in self_assigned.json()["detail"]
    cycle = _save(client, LEAD, STAFF)
    assert cycle.status_code == 400
    assert "through this employee" in cycle.json()["detail"]


def test_save_rejects_an_unknown_employee_and_an_inactive_manager(client: TestClient) -> None:
    missing = _save(client, 999, LEAD)
    assert missing.status_code == 404
    inactive = _save(client, STAFF, INACTIVE)
    assert inactive.status_code == 400
    assert "active manager" in inactive.json()["detail"]


def test_list_reads_the_saved_manager(client: TestClient) -> None:
    assert _save(client, STAFF, LEAD).status_code == 201
    response = client.get("/api/v1/hr/reporting/employees")
    assert response.status_code == 200
    staff = next(row for row in response.json() if row["id"] == STAFF)
    assert staff["managerId"] == LEAD
    assert staff["code"] == "E012"
    assert staff["department"] == "Service"
    assert staff["level"] == "L4"
    assert staff["status"] == "Active"


def test_list_shows_a_change_that_starts_in_the_future(client: TestClient) -> None:
    today = date.today()
    future = (today + timedelta(days=14)).isoformat()
    scheduled = client.post(
        URL,
        json={"employeeId": STAFF, "reportingManagerId": LEAD, "effectiveFrom": future, "remarks": "Later"},
    )
    assert scheduled.status_code == 201
    listed = client.get("/api/v1/hr/reporting/employees")
    staff = next(row for row in listed.json() if row["id"] == STAFF)
    assert staff["managerId"] == LEAD
    assert staff["managerEffectiveFrom"] == future
    current = client.post(
        URL,
        json={
            "employeeId": STAFF,
            "reportingManagerId": LEAD,
            "effectiveFrom": today.isoformat(),
            "remarks": "Now",
        },
    )
    assert current.status_code == 201
    listed = client.get("/api/v1/hr/reporting/employees")
    staff = next(row for row in listed.json() if row["id"] == STAFF)
    assert staff["managerEffectiveFrom"] is None


def test_history_lists_the_saved_change(client: TestClient) -> None:
    assert _save(client, STAFF, LEAD).status_code == 201
    response = client.get(f"/api/v1/hr/reporting/employees/{STAFF}/history")
    assert response.status_code == 200
    row = response.json()[0]
    assert row["previousManagerName"] == "Jyoti"
    assert row["managerName"] == "Padma"
    assert row["effectiveFrom"] == "2026-11-16"
    missing = client.get("/api/v1/hr/reporting/employees/999/history")
    assert missing.status_code == 404


def test_a_later_change_closes_the_previous_assignment(client: TestClient, db: Engine) -> None:
    assert _save(client, STAFF, LEAD).status_code == 201
    second = client.post(
        URL,
        json={"employeeId": STAFF, "reportingManagerId": LEAD, "effectiveFrom": "2026-11-20", "remarks": "Same lead"},
    )
    assert second.status_code == 201
    with Session(db) as session:
        rows = session.scalars(
            select(ReportingAssignment).where(ReportingAssignment.employee_id == STAFF).order_by(ReportingAssignment.id)
        ).all()
    assert rows[0].effective_to is not None
    assert rows[0].effective_to.isoformat() == "2026-11-19"
    assert rows[0].manager_id == LEAD
    assert rows[1].effective_to is None


def test_remove_clears_the_manager_and_keeps_the_employee(client: TestClient, db: Engine) -> None:
    response = client.post(
        "/api/v1/hr/reporting/removals",
        json={"employeeId": STAFF, "effectiveFrom": "2026-11-17", "remarks": "Moved team"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["previousManagerId"] == MID
    assert body["managerId"] is None
    with Session(db) as session:
        employee = session.get(Employee, STAFF)
        assert employee is not None
        assert employee.reporting_manager_id is None
        assert employee.is_active is True
        assert employee.status == "Active"
        history = session.scalars(select(ReportingAssignment).where(ReportingAssignment.employee_id == STAFF)).one()
        assert history.previous_manager_id == MID
        assert history.manager_id is None
        assert history.remarks == "Moved team"
    listed = client.get("/api/v1/hr/reporting/employees")
    staff = next(row for row in listed.json() if row["id"] == STAFF)
    assert staff["managerId"] is None
    assert staff["status"] == "Active"


def test_remove_rejects_an_employee_who_has_no_manager(client: TestClient) -> None:
    response = client.post(
        "/api/v1/hr/reporting/removals",
        json={"employeeId": LEAD, "effectiveFrom": "2026-11-17", "remarks": "None"},
    )
    assert response.status_code == 400
    assert "no reporting manager" in response.json()["detail"]


def test_view_permission_cannot_save(settings: Settings, db: Engine) -> None:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset({"core.employee.view"}))

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current:
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = _save(test_client, STAFF, LEAD)
        removed = test_client.post(
            "/api/v1/hr/reporting/removals",
            json={"employeeId": STAFF, "effectiveFrom": "2026-11-17", "remarks": "No"},
        )
    assert response.status_code == 403
    assert removed.status_code == 403
