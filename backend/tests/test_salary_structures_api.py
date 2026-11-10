"""Employee salary structures through the API (SQLite)."""

from collections.abc import Iterator

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
    "core.audit_log",
]
URL = "/api/v1/hr/salary-structures"


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


def test_an_employee_starts_without_a_structure_and_saves_component_lines(client: TestClient) -> None:
    basic = client.post(
        "/api/v1/hr/salary-components",
        json={
            "code": "BASIC",
            "name": "Basic Salary",
            "componentType": "Earning",
            "calculationMethod": "Fixed Amount",
            "calculationBasis": "Fixed Monthly Amount",
            "effectiveFrom": "2026-08-01",
        },
    )
    assert basic.status_code == 201, basic.text
    loan = client.post(
        "/api/v1/hr/salary-components",
        json={
            "code": "LOAN",
            "name": "Loan",
            "componentType": "Employee Deduction",
            "calculationMethod": "Manual Entry",
            "includeInGross": False,
            "isTaxable": False,
            "allowManualOverride": True,
            "effectiveFrom": "2026-08-01",
        },
    )
    assert loan.status_code == 201, loan.text

    listed = client.get(URL)
    assert listed.status_code == 200, listed.text
    row = listed.json()["items"][0]
    assert row["employeeCode"] == "EMP0003"
    assert row["fullName"] == "Satyajit Tung"
    assert row["department"] == "Human Resources"
    assert row["structureId"] is None

    counts = client.get(f"{URL}/summary").json()
    assert counts == {"employees": 1, "assigned": 0, "unassigned": 1, "active": 1}

    saved = client.post(
        f"{URL}/5",
        json={
            "effectiveFrom": "2026-08-01",
            "annualCtc": "360000.00",
            "monthlyGross": "30000.00",
            "lines": [
                {"salaryComponentId": basic.json()["id"], "included": True, "monthlyAmount": "18000.00"},
                {"salaryComponentId": loan.json()["id"], "included": True, "monthlyAmount": "500.00"},
            ],
        },
    )
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["annualCtc"] == "360000.00"
    by_code = {line["code"]: line for line in body["lines"]}
    assert by_code["BASIC"]["monthlyAmount"] == "18000.00"
    assert by_code["LOAN"]["monthlyAmount"] is None

    again = client.get(URL, params={"assignment": "assigned"})
    assert again.json()["total"] == 1
    assert again.json()["items"][0]["monthlyGross"] == "30000.00"


def test_a_later_effective_date_keeps_the_previous_structure(client: TestClient, db: Engine) -> None:
    basic = client.post(
        "/api/v1/hr/salary-components",
        json={
            "code": "BASIC",
            "name": "Basic Salary",
            "componentType": "Earning",
            "calculationMethod": "Fixed Amount",
            "calculationBasis": "Fixed Monthly Amount",
            "effectiveFrom": "2026-08-01",
        },
    )
    assert basic.status_code == 201, basic.text
    body = {
        "effectiveFrom": "2026-08-01",
        "annualCtc": "360000.00",
        "monthlyGross": "30000.00",
        "lines": [{"salaryComponentId": basic.json()["id"], "included": True, "monthlyAmount": "18000.00"}],
    }
    first = client.post(f"{URL}/5", json=body)
    assert first.status_code == 201, first.text
    match = {"If-Match": f'"{first.json()["rowVersion"]}"'}

    same = client.patch(f"{URL}/5", headers=match, json={**body, "monthlyGross": "31000.00"})
    assert same.status_code == 200, same.text

    revised = client.patch(
        f"{URL}/5",
        headers={"If-Match": f'"{same.json()["rowVersion"]}"'},
        json={
            "effectiveFrom": "2026-12-01",
            "effectiveTo": "2027-03-31",
            "annualCtc": "420000.00",
            "monthlyGross": "35000.00",
            "lines": [{"salaryComponentId": basic.json()["id"], "included": True, "monthlyAmount": "22000.00"}],
        },
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["effectiveFrom"] == "2026-12-01"
    assert revised.json()["annualCtc"] == "420000.00"

    earlier = client.patch(
        f"{URL}/5",
        headers={"If-Match": f'"{revised.json()["rowVersion"]}"'},
        json={**body, "effectiveFrom": "2026-07-01"},
    )
    assert earlier.status_code == 400, earlier.text

    equal = client.patch(
        f"{URL}/5",
        headers={"If-Match": f'"{revised.json()["rowVersion"]}"'},
        json={
            "effectiveFrom": "2026-12-01",
            "effectiveTo": "2026-12-01",
            "annualCtc": "420000.00",
            "monthlyGross": "35000.00",
            "lines": [{"salaryComponentId": basic.json()["id"], "included": True, "monthlyAmount": "22000.00"}],
        },
    )
    assert equal.status_code == 422, equal.text

    with db.connect() as connection:
        rows = connection.execute(
            text(
                "select effective_from, effective_to, annual_ctc "
                "from hr.salary_structure order by effective_from"
            )
        ).all()
        amounts = connection.execute(
            text(
                "select s.effective_from, l.monthly_amount "
                "from hr.salary_structure s "
                "join hr.salary_structure_line l on l.salary_structure_id = s.id "
                "order by s.effective_from"
            )
        ).all()
    assert [str(row.effective_from)[:10] for row in rows] == ["2026-08-01", "2026-12-01"]
    assert str(rows[0].effective_to)[:10] == "2026-11-30"
    assert str(rows[1].effective_to)[:10] == "2027-03-31"
    assert [f"{float(row.monthly_amount):.2f}" for row in amounts] == ["18000.00", "22000.00"]


def test_a_caller_without_permission_is_rejected(settings: Settings, db: Engine) -> None:
    guest = next(_client(settings, db, frozenset()))
    assert guest.get(URL).status_code == 403
    guest.close()
