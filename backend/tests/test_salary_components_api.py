"""Salary component master through the API (SQLite)."""

from collections.abc import Iterator
from datetime import date
from typing import Any

import httpx2 as httpx
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
    "hr.salary_component",
    "hr.salary_component_revision",
    "hr.salary_structure",
    "hr.salary_structure_line",
    "hr.payroll_run",
    "hr.payslip",
    "hr.payslip_line",
    "core.app_user",
    "core.audit_log",
]
ACTOR_ID = 1
URL = "/api/v1/hr/salary-components"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.app_user", id=ACTOR_ID, username="hr@trishul.co", cognito_sub="sub-hr")
    return engine


def _client(settings: Settings, db: Engine, permissions: frozenset[str]) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    api.dependency_overrides[get_current_user] = lambda: make_user(
        id=ACTOR_ID,
        permissions=permissions,
        branch_ids=None,
        principal_ids=None,
    )

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current:
            set_audit_context(current, user_id=ACTOR_ID, source="Web", ip_address="127.0.0.1")
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    yield from _client(settings, db, frozenset({"hr.salary_component.view", "hr.salary_component.manage"}))


@pytest.fixture
def guest(settings: Settings, db: Engine) -> Iterator[TestClient]:
    yield from _client(settings, db, frozenset())


def body(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": "BASIC",
        "name": "Basic Salary",
        "componentType": "Earning",
        "description": "Monthly basic pay.",
        "displayOrder": 10,
        "calculationMethod": "Fixed Amount",
        "calculationBasis": "Attendance / Effective Workdays",
        "isProrated": True,
        "includeInGross": True,
        "isTaxable": True,
        "isPfApplicable": True,
        "includeInNetPay": True,
        "allowReversal": True,
        "displayInStatement": True,
        "displayInPayslip": True,
        "effectiveFrom": "2026-08-01",
    }
    payload.update(changes)
    return payload


def create(client: TestClient, **changes: Any) -> httpx.Response:
    return client.post(URL, json=body(**changes))


def match(row: dict[str, Any]) -> dict[str, str]:
    return {"If-Match": f'"{row["rowVersion"]}"'}


def test_create_list_and_reject_a_duplicate_code(client: TestClient) -> None:
    created = create(client)
    assert created.status_code == 201, created.text
    basic = created.json()
    assert basic["code"] == "BASIC"
    assert basic["allowReversal"] is True
    assert basic["isProrated"] is True
    assert basic["percentage"] is None

    listed = client.get(URL, params={"search": "basic", "componentType": "Earning"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["calculationMethod"] == "Fixed Amount"
    assert listed.json()["items"][0]["effectiveFrom"] == "2026-08-01"

    counts = client.get(f"{URL}/summary").json()
    assert counts == {"total": 1, "earning": 1, "deduction": 0, "active": 1}

    duplicate = create(client, name="Basic again")
    assert duplicate.status_code == 409

    fetched = client.get(f"{URL}/{basic['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["rulesLocked"] is False
    assert fetched.json()["revisions"] == []
    assert fetched.json()["createdBy"] == "hr@trishul.co"
    assert fetched.json()["audit"][0]["action"] == "Insert"


def test_a_rule_change_is_kept_and_a_processed_payroll_blocks_the_next_one(client: TestClient, db: Engine) -> None:
    basic = create(client).json()
    revised = client.patch(
        f"{URL}/{basic['id']}",
        json={"isProrated": False},
        headers=match(basic),
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["isProrated"] is False
    assert revised.json()["revisions"][0]["calculationMethod"] == "Fixed Amount"

    insert_row(
        db,
        "hr.payroll_run",
        id=1,
        company_id=1,
        period_month=date(2026, 8, 1),
        run_date=date(2026, 8, 31),
        status="Processed",
    )
    insert_row(
        db,
        "hr.payslip",
        id=1,
        payroll_run_id=1,
        employee_id=1,
        paid_days=26,
        gross=1000,
        total_deductions=0,
        net_pay=1000,
    )
    insert_row(db, "hr.payslip_line", payslip_id=1, salary_component_id=basic["id"], amount=1000)

    blocked = client.patch(
        f"{URL}/{basic['id']}",
        json={"calculationBasis": "Fixed Monthly Amount"},
        headers=match(revised.json()),
    )
    assert blocked.status_code == 409

    renamed = client.patch(
        f"{URL}/{basic['id']}",
        json={"name": "Basic pay"},
        headers=match(revised.json()),
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Basic pay"
    assert renamed.json()["calculationBasis"] == "Attendance / Effective Workdays"


def test_deactivate_and_reject_callers_without_permission(client: TestClient, guest: TestClient) -> None:
    basic = create(client).json()
    assert guest.get(URL).status_code == 403
    inactive = client.patch(f"{URL}/{basic['id']}/status", json={"isActive": False}, headers=match(basic))
    assert inactive.status_code == 200
    assert inactive.json()["isActive"] is False
    assert client.delete(f"{URL}/{basic['id']}").status_code == 405


def test_manual_entry_and_date_order(client: TestClient) -> None:
    loan = create(
        client,
        code="LOAN",
        name="Loan",
        componentType="Employee Deduction",
        calculationMethod="Manual Entry",
        calculationBasis=None,
        includeInGross=False,
        isTaxable=False,
        isPfApplicable=False,
        allowReversal=False,
        allowManualOverride=True,
    )
    assert loan.status_code == 201, loan.text
    assert loan.json()["calculationBasis"] is None
    assert loan.json()["allowManualOverride"] is True

    dated = create(client, code="HRA", name="House Rent Allowance", effectiveTo="2026-07-01")
    assert dated.status_code == 422


def test_every_category_and_the_summary_count_the_saved_rows(client: TestClient) -> None:
    create(client, code="BASIC", name="Basic", componentType="Earning")
    create(
        client,
        code="PF",
        name="Provident Fund",
        componentType="Employee Deduction",
        calculationMethod="Formula",
        calculationBasis="Eligible PF Wages",
        formula="MIN(PF_WAGES, PF_WAGE_CEILING) * PF_RATE / 100",
        includeInGross=False,
        isTaxable=False,
        isPfApplicable=False,
        allowReversal=False,
    )
    employer = create(
        client,
        code="PF_ER",
        name="Employer PF",
        componentType="Employer Contribution",
        calculationMethod="Formula",
        calculationBasis="Eligible PF Wages",
        formula="PF_WAGES * ER_RATE / 100",
        includeInGross=False,
        includeInNetPay=True,
        isTaxable=False,
        allowReversal=False,
    )
    info = create(
        client,
        code="DAYS",
        name="Paid days",
        componentType="Informational",
        calculationMethod="Manual Entry",
        calculationBasis=None,
        includeInGross=True,
        includeInNetPay=True,
        isTaxable=False,
        allowReversal=False,
        allowManualOverride=True,
    )
    create(
        client,
        code="MED",
        name="Medical",
        componentType="Reimbursement",
        calculationMethod="Fixed Amount",
        calculationBasis="Fixed Monthly Amount",
        allowReversal=False,
    )
    assert employer.status_code == 201, employer.text
    assert employer.json()["includeInNetPay"] is False
    assert info.status_code == 201, info.text
    assert info.json()["includeInGross"] is False
    assert info.json()["includeInNetPay"] is False

    counts = client.get(f"{URL}/summary").json()
    assert counts == {"total": 5, "earning": 1, "deduction": 1, "active": 5}

    unsafe = create(
        client,
        code="BAD",
        name="Unsafe",
        calculationMethod="Formula",
        calculationBasis="Custom Formula",
        formula="__import__('os')",
    )
    assert unsafe.status_code == 400
