"""Payroll runs calculate saved salary structures and skip everyone else."""

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
    "hr.attendance",
    "hr.payroll_run",
    "hr.payslip",
    "hr.payslip_line",
    "core.audit_log",
]
URL = "/api/v1/hr/payroll-runs"


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
    insert_row(
        engine,
        "core.employee",
        id=6,
        employee_code="EMP0004",
        first_name="Second",
        last_name="Person",
        employee_type="Permanent",
        status="Active",
        company_id=1,
        branch_id=1,
        department_id=1,
        designation_id=1,
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


def test_a_month_uses_the_structure_and_leaves_everyone_else_out(client: TestClient, db: Engine) -> None:
    basic = client.post(
        "/api/v1/hr/salary-components",
        json={
            "code": "BASIC",
            "name": "Basic Salary",
            "componentType": "Earning",
            "calculationMethod": "Fixed Amount",
            "calculationBasis": "Attendance / Effective Workdays",
            "isProrated": True,
            "includeInGross": True,
            "effectiveFrom": "2026-04-01",
        },
    )
    assert basic.status_code == 201, basic.text
    hra = client.post(
        "/api/v1/hr/salary-components",
        json={
            "code": "HRA",
            "name": "House Rent Allowance",
            "componentType": "Earning",
            "calculationMethod": "Percentage",
            "calculationBasis": "Basic Salary",
            "includeInGross": True,
            "effectiveFrom": "2026-04-01",
        },
    )
    assert hra.status_code == 201, hra.text
    saved = client.post(
        "/api/v1/hr/salary-structures/5",
        json={
            "effectiveFrom": "2026-11-09",
            "effectiveTo": "2026-11-30",
            "annualCtc": "72000.00",
            "monthlyGross": "6000.00",
            "lines": [
                {"salaryComponentId": basic.json()["id"], "included": True, "monthlyAmount": "6000.00"},
                {"salaryComponentId": hra.json()["id"], "included": True, "percentage": "30.00"},
            ],
        },
    )
    assert saved.status_code == 201, saved.text

    processed = client.post(URL, json={"month": "2026-11-01"})
    assert processed.status_code == 201, processed.text
    run = processed.json()[0]
    assert run["employees"] == 1
    assert run["status"] == "Processed"
    assert run["gross"] == "5720.00"
    assert run["deductions"] == "0.00"
    assert run["netPay"] == "5720.00"

    with db.connect() as connection:
        lines = connection.execute(
            text(
                """
                SELECT c.code, l.amount
                FROM hr.payslip_line l
                JOIN hr.salary_component c ON c.id = l.salary_component_id
                ORDER BY c.code
                """
            )
        ).all()
    assert [(code, f"{amount:.2f}") for code, amount in lines] == [("BASIC", "4400.00"), ("HRA", "1320.00")]
    again = client.post(URL, json={"month": "2026-11-15"})
    assert again.status_code == 400
    assert again.json()["detail"] == "Payroll for this month is already processed."


def test_a_month_with_no_structure_is_rejected(client: TestClient) -> None:
    rejected = client.post(URL, json={"month": "2026-10-01"})
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "No employee has a salary structure for this month."


def test_a_caller_without_permission_is_rejected(settings: Settings, db: Engine) -> None:
    guest = next(_client(settings, db, frozenset()))
    assert guest.get(URL).status_code == 403
    assert guest.post(URL, json={"month": "2026-11-01"}).status_code == 403
    guest.close()
