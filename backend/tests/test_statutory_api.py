"""Statutory rules and the compliance summary (SQLite). Rates come from the request."""

import json
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
    "core.company",
    "core.state",
    "core.branch",
    "core.employee",
    "hr.department",
    "hr.employee_profile",
    "hr.salary_structure",
    "hr.salary_component",
    "hr.payroll_run",
    "hr.payslip",
    "hr.payslip_line",
    "hr.statutory_config",
]
URL = "/api/v1/hr/statutory"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.app_user", id=1, username="hr@trishul.co", cognito_sub="sub-hr")
    insert_row(engine, "core.state", id=1, gst_state_code="21", name="Odisha")
    insert_row(engine, "core.company", id=1, code="TRI", legal_name="Trishul", fiscal_year_start_month=4)
    insert_row(
        engine,
        "core.branch",
        id=1,
        company_id=1,
        code="HO",
        name="Head office",
        branch_type="Head office",
        state_id=1,
    )
    insert_row(engine, "hr.department", id=1, code="HR", name="Human Resources")
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
    )
    insert_row(
        engine,
        "hr.salary_structure",
        id=1,
        employee_id=5,
        effective_from=date(2026, 8, 1),
        annual_ctc=360000,
        monthly_gross=30000,
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


def test_summary_uses_saved_rules_and_does_not_invent_amounts(client: TestClient, db: Engine) -> None:
    before = client.get(f"{URL}/summary", params={"month": "2026-11-01"})
    assert before.status_code == 200, before.text
    body = before.json()
    assert body["eligibleEmployees"] == 1
    assert body["employeeContribution"] is None
    assert body["employerContribution"] is None
    assert body["totalLiability"] is None
    assert body["calculationStatus"] == "Not calculated"
    assert body["filingStatus"] == "Not filed"
    assert body["configurationStatus"] == "Not configured"
    assert {item["scheme"]: item["filingStatus"] for item in body["schemes"]} == {
        "PF": "Not filed",
        "ESI": "Not filed",
        "PT": "Not filed",
        "TDS": "Not filed",
    }

    saved = client.post(
        f"{URL}/rules",
        json={"configType": "PF", "effectiveFrom": "2026-08-01", "employeeRate": "12.00", "employerRate": "12.00"},
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["employeeRate"] == "12.00"

    later = client.post(
        f"{URL}/rules",
        json={
            "configType": "PF",
            "effectiveFrom": "2026-12-01",
            "employeeRate": "10.00",
            "wageCeiling": "15000.00",
        },
    )
    assert later.status_code == 201, later.text

    with db.connect() as connection:
        rates = connection.execute(
            text("select effective_from, employee_rate from hr.statutory_config order by effective_from")
        ).all()
    assert [str(row.effective_from)[:10] for row in rates] == ["2026-08-01", "2026-12-01"]
    assert f"{float(rates[0].employee_rate):.2f}" == "12.00"

    listed = client.get(f"{URL}/rules", params={"scheme": "PF"})
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["effectiveTo"] is None
    assert listed.json()[1]["effectiveTo"] == "2026-11-30"

    month = client.get(f"{URL}/summary", params={"month": "2026-11-01"})
    pf = next(item for item in month.json()["schemes"] if item["scheme"] == "PF")
    assert pf["configurationStatus"] == "Configured"
    assert pf["calculationStatus"] == "Not calculated"
    assert pf["filingStatus"] == "Not filed"
    assert month.json()["configurationStatus"] == "Partial"

    people = client.get(f"{URL}/contributions", params={"month": "2026-11-01", "scheme": "PF"})
    assert people.status_code == 200, people.text
    row = people.json()["items"][0]
    assert row["employeeCode"] == "EMP0003"
    assert row["location"] == "Head office"
    assert row["employeeContribution"] is None
    assert row["calculationStatus"] == "Not calculated"

    missing = client.post(f"{URL}/rules", json={"configType": "ESI", "effectiveFrom": "2026-08-01"})
    assert missing.status_code == 400, missing.text


def test_odisha_professional_tax_stops_in_april_2026_and_other_states_use_slabs(
    client: TestClient, db: Engine
) -> None:
    with db.begin() as connection:
        connection.execute(text("update core.branch set name = 'Bhubaneswar' where id = 1"))

    november = client.get(
        f"{URL}/contributions",
        params={"month": "2026-11-01", "scheme": "PT", "search": "Bhubaneswar"},
    )
    assert november.status_code == 200, november.text
    row = november.json()["items"][0]
    assert row["location"] == "Odisha"
    assert row["calculationStatus"] == "Not applicable"
    assert row["employeeContribution"] == "0.00"
    assert row["totalContribution"] == "0.00"
    assert "repealed" in row["reason"]

    summary = client.get(f"{URL}/summary", params={"month": "2026-11-01", "scheme": "PT"})
    assert summary.status_code == 200, summary.text
    assert summary.json()["eligibleEmployees"] == 0
    assert summary.json()["employeeContribution"] == "0.00"
    assert summary.json()["totalLiability"] == "0.00"
    professional_tax = next(item for item in summary.json()["schemes"] if item["scheme"] == "PT")
    assert professional_tax["calculationStatus"] == "Not applicable"
    assert professional_tax["filingStatus"] == "Not filed"

    march = client.get(f"{URL}/contributions", params={"month": "2026-03-01", "scheme": "PT"})
    earlier = march.json()["items"][0]
    assert earlier["calculationStatus"] == "Not calculated"
    assert earlier["employeeContribution"] is None
    march_summary = client.get(f"{URL}/summary", params={"month": "2026-03-01", "scheme": "PT"})
    assert march_summary.json()["eligibleEmployees"] == 1

    insert_row(db, "core.state", id=2, gst_state_code="29", name="Karnataka")
    insert_row(
        db,
        "core.branch",
        id=2,
        company_id=1,
        code="BLR",
        name="Bengaluru",
        branch_type="Branch",
        state_id=2,
    )
    insert_row(
        db,
        "core.employee",
        id=6,
        employee_code="EMP0004",
        first_name="Asha",
        last_name="Rao",
        employee_type="Permanent",
        status="Active",
        company_id=1,
        branch_id=2,
        department_id=1,
    )
    insert_row(
        db,
        "hr.payroll_run",
        id=1,
        company_id=1,
        period_month=date(2026, 11, 1),
        run_date=date(2026, 11, 30),
        status="Processed",
    )
    insert_row(
        db,
        "hr.payslip",
        id=1,
        payroll_run_id=1,
        employee_id=6,
        paid_days=30,
        gross=25000,
        total_deductions=0,
        net_pay=25000,
    )
    slabs = [
        {"min": 0, "max": 15000, "amount": 0},
        {"min": 15000.01, "max": None, "amount": 200},
    ]
    saved = client.post(
        f"{URL}/rules",
        json={
            "configType": "PT",
            "stateId": 2,
            "effectiveFrom": "2026-04-01",
            "slabJson": json.dumps(slabs),
        },
    )
    assert saved.status_code == 201, saved.text

    both = client.get(f"{URL}/contributions", params={"month": "2026-11-01", "scheme": "PT"})
    by_code = {item["employeeCode"]: item for item in both.json()["items"]}
    assert by_code["EMP0003"]["employeeContribution"] == "0.00"
    assert by_code["EMP0003"]["calculationStatus"] == "Not applicable"
    assert by_code["EMP0004"]["location"] == "Karnataka"
    assert by_code["EMP0004"]["applicableWages"] == "25000.00"
    assert by_code["EMP0004"]["employeeContribution"] == "200.00"
    assert by_code["EMP0004"]["calculationStatus"] == "Calculated"

    counted = client.get(f"{URL}/summary", params={"month": "2026-11-01", "scheme": "PT"})
    assert counted.json()["eligibleEmployees"] == 1
    assert counted.json()["employeeContribution"] == "200.00"

    only_odisha = client.get(f"{URL}/contributions", params={"month": "2026-11-01", "scheme": "PT", "stateId": 1})
    assert [item["employeeCode"] for item in only_odisha.json()["items"]] == ["EMP0003"]


def test_a_caller_without_permission_is_rejected(settings: Settings, db: Engine) -> None:
    guest = next(_client(settings, db, frozenset()))
    assert guest.get(f"{URL}/summary", params={"month": "2026-11-01"}).status_code == 403
    guest.close()
