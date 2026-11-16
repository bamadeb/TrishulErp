"""Salary templates are saved packages. Editing one does not rewrite an assigned structure."""

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.app_user",
    "core.employee",
    "hr.department",
    "hr.designation",
    "hr.salary_component",
    "hr.salary_component_revision",
    "hr.salary_structure",
    "hr.salary_structure_line",
    "hr.payroll_run",
    "hr.payslip",
    "hr.payslip_line",
    "hr.salary_template",
    "hr.salary_template_line",
    "hr.salary_template_assignment",
    "hr.salary_template_designation",
    "hr.salary_template_grade",
    "core.audit_log",
]
TEMPLATES = "/api/v1/hr/salary-templates"
STRUCTURES = "/api/v1/hr/salary-structures"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.app_user", id=1, username="hr@trishul.co", cognito_sub="sub-hr")
    insert_row(engine, "hr.department", id=1, code="HR", name="Human Resources")
    insert_row(engine, "hr.designation", id=1, code="EXE", name="Executive", department_id=1)
    insert_row(
        engine,
        "core.employee",
        id=5,
        employee_code="EMP0003",
        first_name="Satyajit",
        last_name="Tung",
        employee_type="Permanent",
        status="Active",
        company_id=1,
        branch_id=1,
        department_id=1,
        designation_id=1,
        date_of_joining=date(2023, 1, 10),
    )
    return engine


def _client(settings: Settings, db: Engine, permissions: frozenset[str]) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    api.dependency_overrides[get_current_user] = lambda: make_user(
        id=1, permissions=permissions, branch_ids=None, principal_ids=None
    )

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current:
            set_audit_context(current, user_id=1, source="Web", ip_address="127.0.0.1")
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    yield from _client(settings, db, frozenset({"hr.salary_component.view", "hr.salary_component.manage"}))


def _component(client: TestClient) -> int:
    saved = client.post(
        "/api/v1/hr/salary-components",
        json={
            "code": "BASIC",
            "name": "Basic Salary",
            "componentType": "Earning",
            "calculationMethod": "Fixed Amount",
            "calculationBasis": "Attendance / Effective Workdays",
            "isProrated": False,
            "includeInGross": True,
            "effectiveFrom": "2026-04-01",
        },
    )
    assert saved.status_code == 201, saved.text
    return int(saved.json()["id"])


def test_a_template_is_saved_and_does_not_rewrite_an_assigned_structure(client: TestClient, db: Engine) -> None:
    component_id = _component(client)
    created = client.post(
        TEMPLATES,
        json={
            "code": "se-a",
            "name": "Service package",
            "description": "Reusable package",
            "templateType": "Monthly",
            "employeeCategory": "Permanent",
            "departmentId": 1,
            "designationId": 1,
            "effectiveFrom": "2026-11-01",
            "lines": [{"salaryComponentId": component_id, "monthlyAmount": "1000.00", "displayOrder": 1}],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["code"] == "SE-A"
    assert body["monthlyGross"] == "1000.00"
    assert body["annualCtc"] == "12000.00"
    assert body["assignedEmployees"] == 0
    template_id = body["id"]

    listed = client.get(TEMPLATES)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["department"] == "Human Resources"

    structure = client.post(
        f"{STRUCTURES}/5",
        json={
            "effectiveFrom": "2026-11-01",
            "annualCtc": "12000.00",
            "monthlyGross": "1000.00",
            "applyTemplate": True,
            "salaryTemplateId": template_id,
            "lines": [{"salaryComponentId": component_id, "included": True, "monthlyAmount": "1000.00"}],
        },
    )
    assert structure.status_code == 201, structure.text

    changed = client.patch(
        f"{TEMPLATES}/{template_id}",
        headers={"If-Match": f'"{body["rowVersion"]}"'},
        json={
            "code": "SE-A",
            "name": "Service package",
            "templateType": "Monthly",
            "effectiveFrom": "2026-11-01",
            "lines": [{"salaryComponentId": component_id, "monthlyAmount": "2000.00", "displayOrder": 1}],
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["monthlyGross"] == "2000.00"

    with db.connect() as connection:
        amount = connection.execute(text("SELECT monthly_amount FROM hr.salary_structure_line")).scalar()
    assert f"{amount:.2f}" == "1000.00"
    detail = client.get(f"{TEMPLATES}/{template_id}")
    assert detail.json()["assignedEmployees"] == 1
    assert detail.json()["employees"][0]["employeeCode"] == "EMP0003"
    assert detail.json()["employees"][0]["monthlyGross"] == "1000.00"

    duplicate = client.post(
        TEMPLATES,
        json={
            "code": "SE-A",
            "name": "Again",
            "templateType": "Monthly",
            "effectiveFrom": "2026-11-01",
            "lines": [{"salaryComponentId": component_id, "monthlyAmount": "1.00"}],
        },
    )
    assert duplicate.status_code == 400


def test_a_caller_without_permission_is_rejected(settings: Settings, db: Engine) -> None:
    guest = next(_client(settings, db, frozenset()))
    assert guest.get(TEMPLATES).status_code == 403
    guest.close()
