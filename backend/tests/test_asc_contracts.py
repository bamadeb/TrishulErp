"""ASC master: plans, contracts, the register import, and ASC on service calls (route -> SQL, SQLite)."""

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import Customer, MachineModel, MachineUnit, ServiceContract
from trishul_api.main import create_app
from trishul_api.modules.service.contracts.service import add_months, plan_end_date

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "core.principal",
    "core.customer",
    "core.machine_model",
    "core.machine_unit",
    "core.machine_ownership",
    "core.customer_site",
    "core.employee",
    "core.lookup_type",
    "core.lookup_value",
    "core.number_series",
    "core.app_user",
    "core.audit_log",
    "hr.designation",
    "core.team",
    "core.team_member",
    "svc.service_call",
    "svc.service_visit",
    "trk.trackable_activity_module",
    "trk.trackable_activity",
    "trk.trip_type",
    "trk.trip_status",
    "trk.trip",
    "svc.call_status_log",
    "svc.contract_plan",
    "svc.service_contract",
    "svc.contract_coverage",
    "svc.sla_rule",
    "svc.sla_event",
    "core.alert_rule",
    "core.alert_rule_recipient",
    "core.alert",
    "core.alert_recipient",
]

COMPANY, BRANCH, OTHER_BRANCH, PRINCIPAL = 1, 1, 2, 1
CUSTOMER_ID, MACHINE_ID, PLAN_6M, PLAN_12M, ACTOR_ID = 100, 200, 10, 11, 1
URL = "/api/v1/svc/service-contracts"
PLANS = "/api/v1/svc/contract-plans"
MANAGE = {"svc.contract.view", "svc.contract.manage", "svc.contract.import"}
TODAY = dt.date.today()


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TRISHUL", legal_name="Trishul", trade_name="Trishul")
    insert_row(engine, "core.branch", id=BRANCH, company_id=COMPANY, code="ANGUL", name="Angul")
    insert_row(engine, "core.branch", id=OTHER_BRANCH, company_id=COMPANY, code="JEYPORE", name="Jeypore")
    insert_row(engine, "core.principal", id=PRINCIPAL, code="TATA_HITACHI", name="Tata Hitachi")
    insert_row(engine, "core.customer", id=CUSTOMER_ID, company_id=COMPANY, code="88056", name="Prakash Ch Sahu",
               customer_type="Individual", primary_phone="9000000000")
    insert_row(engine, "core.machine_model", id=1, model_code="EX-200 SUPER", model_name="EX-200 SUPER",
               principal_id=PRINCIPAL, product_line="Excavator")
    insert_row(engine, "core.machine_model", id=2, model_code="EX-210 SUPER+", model_name="EX-210 SUPER+",
               principal_id=PRINCIPAL, product_line="Excavator")
    insert_row(engine, "core.machine_model", id=3, model_code="UNMAPPED", model_name="Model not yet identified",
               principal_id=PRINCIPAL, product_line="Other")
    insert_row(engine, "core.machine_unit", id=MACHINE_ID, serial_number="S200-54828", model_id=1,
               principal_id=PRINCIPAL, customer_id=CUSTOMER_ID, status="Sold")
    insert_row(engine, "svc.contract_plan", id=PLAN_6M, code="ASC6-20T", name="ASC 6 months - 20 Ton",
               principal_id=PRINCIPAL, contract_type="ASC", duration_months=6, visits_included=6,
               price=Decimal(28000), gst_pct=Decimal(18), machine_class="20 Ton", covers_labour=True,
               covers_parts=False, covers_travel=True, parts_discount_pct=Decimal(5), service_priority="High")
    insert_row(engine, "svc.contract_plan", id=PLAN_12M, code="ASC12-20T", name="ASC 12 months - 20 Ton",
               principal_id=PRINCIPAL, contract_type="ASC", duration_months=12, visits_included=12,
               price=Decimal(45000), gst_pct=Decimal(18), machine_class="20 Ton", covers_labour=True,
               covers_parts=False, covers_travel=True, parts_discount_pct=Decimal(5), service_priority="High")
    for branch, code in ((BRANCH, "ANGUL"), (OTHER_BRANCH, "JEYPORE")):
        insert_row(engine, "core.number_series", company_id=COMPANY, document_type="SERVICE_CONTRACT",
                   branch_id=branch, prefix=f"{code}/ASC/", next_number=1, padding=5)
    insert_row(engine, "core.number_series", company_id=COMPANY, document_type="SERVICE_CALL",
               prefix="SC-", next_number=1, padding=4)
    insert_row(engine, "core.lookup_type", id=1, code="CALL_SOURCE", name="Call Source", module="Service")
    insert_row(engine, "core.lookup_value", id=11, lookup_type_id=1, code="PHONE", label="Phone", sort_order=1)
    insert_row(engine, "core.lookup_type", id=2, code="CALL_TYPE", name="Call Type", module="Service")
    insert_row(engine, "core.lookup_value", id=21, lookup_type_id=2, code="BREAKDOWN", label="Breakdown", sort_order=1)
    insert_row(engine, "hr.designation", id=1, code="SERVICE_ENG", name="Service Engineer")
    insert_row(engine, "core.employee", id=300, company_id=COMPANY, branch_id=BRANCH, employee_code="E300",
               first_name="Bidyadhar", last_name="Jena", designation_id=1, employee_type="Permanent", status="Active")
    insert_row(engine, "core.app_user", id=ACTOR_ID, username="admin@trishul.co", cognito_sub="sub-admin")
    return engine


def make_client(settings: Settings, db: Engine, permissions: set[str]) -> TestClient:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(id=ACTOR_ID, employee_id=None, permissions=frozenset(permissions),
                      default_branch_id=BRANCH, branch_ids=None, principal_ids=None)
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=ACTOR_ID, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    calls = {"svc.call.create", "svc.call.view", "svc.call.assign"}
    with make_client(settings, db, MANAGE | calls) as test_client:
        yield test_client


def add_asc(client: TestClient, **changes: Any) -> Any:
    body = {"machineUnitId": MACHINE_ID, "contractPlanId": PLAN_6M, "startDate": str(TODAY)} | changes
    return client.post(URL, json=body)


# ------------------------------------------------------------------------------------------- dates


def test_plan_end_date_is_the_day_before_the_same_date_months_later() -> None:
    assert plan_end_date(dt.date(2026, 4, 5), 6) == dt.date(2026, 10, 4)
    assert plan_end_date(dt.date(2026, 4, 5), 12) == dt.date(2027, 4, 4)
    assert add_months(dt.date(2026, 1, 31), 1) == dt.date(2026, 2, 28)


# ------------------------------------------------------------------------------------------- plans


def test_plans_show_price_with_gst(client: TestClient) -> None:
    plans = {p["code"]: p for p in client.get(PLANS).json()}
    assert Decimal(str(plans["ASC6-20T"]["totalPrice"])) == Decimal(33040)  # 28000 + 18%
    assert Decimal(str(plans["ASC12-20T"]["totalPrice"])) == Decimal(53100)


def test_admin_adds_and_retires_a_plan(client: TestClient) -> None:
    created = client.post(PLANS, json={"code": "ASC12-TWL", "name": "ASC 12 months - TWL", "machineClass": "TWL",
                                       "durationMonths": 12, "visitsIncluded": 12, "price": 36000})
    assert created.status_code == 201, created.text
    assert Decimal(str(created.json()["totalPrice"])) == Decimal(42480)
    duplicate = client.post(PLANS, json={"code": "ASC12-TWL", "name": "x", "durationMonths": 12, "price": 1})
    assert duplicate.status_code == 409
    retired = client.post(f"{PLANS}/{created.json()['id']}/deactivate")
    assert retired.json()["isActive"] is False
    assert "ASC12-TWL" not in {p["code"] for p in client.get(PLANS).json()}


# ---------------------------------------------------------------------------------------- contracts


def test_add_asc_from_plan_fills_period_visits_and_value(client: TestClient) -> None:
    created = add_asc(client)
    assert created.status_code == 201, created.text
    asc = created.json()
    assert asc["contractNo"] == "ANGUL/ASC/00001"
    assert asc["state"] == "Active"
    assert asc["endDate"] == str(plan_end_date(TODAY, 6))
    assert asc["visitsIncluded"] == 6
    assert Decimal(str(asc["contractValue"])) == Decimal(33040)
    assert asc["customerName"] == "Prakash Ch Sahu"
    assert asc["machineSerialNo"] == "S200-54828"

    overlapping = add_asc(client, startDate=str(TODAY + dt.timedelta(days=30)))
    assert overlapping.status_code == 400
    assert "ANGUL/ASC/00001" in overlapping.json()["detail"]


def test_machine_option_and_new_call_show_the_asc(client: TestClient) -> None:
    add_asc(client)
    options = client.get("/api/v1/svc/service-calls/machine-options", params={"customerId": CUSTOMER_ID}).json()
    assert options[0]["asc"]["state"] == "Active"
    assert options[0]["asc"]["visitsIncluded"] == 6

    call = client.post("/api/v1/svc/service-calls", json={
        "customerId": CUSTOMER_ID, "principalId": PRINCIPAL, "machineUnitId": MACHINE_ID,
        "callTypeLookupId": 21, "callSourceLookupId": 11, "complaintDescription": "Hydraulic leak",
        "callerPhone": "9876543210",
    })
    assert call.status_code == 201, call.text
    assert call.json()["isAscPriority"] is True
    assert call.json()["coverageType"] == "Contract"
    detail = client.get(f"/api/v1/svc/service-calls/{call.json()['id']}").json()
    assert detail["asc"]["contractNo"] == "ANGUL/ASC/00001"


def test_expired_asc_shows_as_expired_and_gives_no_priority(client: TestClient) -> None:
    start = TODAY - dt.timedelta(days=400)
    assert add_asc(client, startDate=str(start)).status_code == 201
    options = client.get("/api/v1/svc/service-calls/machine-options", params={"customerId": CUSTOMER_ID}).json()
    assert options[0]["asc"]["state"] == "Expired"
    assert client.get(URL, params={"status": "expired"}).json()["total"] == 1
    assert client.get(URL).json()["total"] == 0  # "live" by default


def test_renew_starts_the_day_after_and_links_back(client: TestClient) -> None:
    old = add_asc(client, startDate=str(TODAY - dt.timedelta(days=150))).json()
    renewed = client.post(f"{URL}/{old['id']}/renew", json={"receiptNo": "MR/ANG-1/03.11.26"})
    assert renewed.status_code == 200, renewed.text
    new = renewed.json()
    assert new["startDate"] == str(dt.date.fromisoformat(old["endDate"]) + dt.timedelta(days=1))
    assert new["isRenewal"] is True
    assert new["renewedFromContractNo"] == old["contractNo"]
    assert client.get(f"{URL}/{old['id']}").json()["renewedByContractId"] == new["id"]


def test_cancelled_asc_no_longer_counts(client: TestClient) -> None:
    asc = add_asc(client).json()
    cancelled = client.post(f"{URL}/{asc['id']}/cancel").json()
    assert cancelled["state"] == "Cancelled"
    options = client.get("/api/v1/svc/service-calls/machine-options", params={"customerId": CUSTOMER_ID}).json()
    assert options[0]["asc"] is None
    assert add_asc(client).status_code == 201  # the dates are free again


def test_viewing_needs_permission_and_managing_needs_manage(settings: Settings, db: Engine) -> None:
    with make_client(settings, db, set()) as nobody, make_client(settings, db, {"svc.contract.view"}) as viewer:
        assert nobody.get(URL).status_code == 403
        assert viewer.get(URL).status_code == 200
        assert add_asc(viewer).status_code == 403
        assert viewer.post(f"{URL}/import/preview", files={"file": ("a.xlsx", b"x")}).status_code == 403


# ------------------------------------------------------------------------------------------- import

REGISTER_HEADERS = ["Branch", "SE", "Dealer", "Customer", "Cust Code", "Cust Contact no", "Cust.Type", "Model",
                    "M/C Sl No", "DOC", "Cont. Amt.", "MR No.", "Invoice/Date", "Book No", "Enrol ID/Contract ID",
                    "Renew or New", "Start Date", "Exp- Date", "12Month/6Month", "Visit Done", "Visit Due"]


def register(rows: list[dict[str, Any]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "ASC-26-27 "
    sheet.append(REGISTER_HEADERS)
    sheet.append(["LIVE ASC", 0])  # a section row: skipped silently
    for row in rows:
        sheet.append([row.get(header) for header in REGISTER_HEADERS])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def register_rows() -> list[dict[str, Any]]:
    start = TODAY - dt.timedelta(days=10)
    return [
        {  # the machine already in Trishul
            "Branch": "Angul", "SE": "Bidyadhar Jena", "Customer": "Prakash Ch Sahu", "Cust Code": 88056,
            "Model": "EX-200S", "M/C Sl No": "S200-54828", "Cont. Amt.": 33040, "MR No.": "MR/ANG-60/02.05.26",
            "Book No": "1199", "Renew or New": "Renew", "Start Date": dt.datetime.combine(start, dt.time()),
            "Exp- Date": dt.datetime.combine(plan_end_date(start, 6), dt.time()), "12Month/6Month": 6,
            "Visit Done": 2, "Visit Due": 4,
        },
        {  # a new customer and machine; the model is a short form of a master model
            "Branch": "Jeypore", "SE": "Ranjit Ojha", "Customer": "Shree Vinayak Enterprises", "Cust Code": 134250,
            "Cust Contact no": "8637232421", "Cust.Type": "KA", "Model": "EX-210SP", "M/C Sl No": "SP21-63379",
            "DOC": dt.datetime(2023, 5, 3), "Cont. Amt.": 53100, "Renew or New": "New",
            "Start Date": "22-11-2026", "12Month/6Month": "12months",
        },
        {  # a model not in the master, and a branch Trishul doesn't have
            "Branch": "Bhubaneswar", "Customer": "Mamata Rout", "Cust Code": 175008, "Model": "ZX-33U",
            "M/C Sl No": "ZX33-00092", "Start Date": dt.datetime.combine(start, dt.time()), "12Month/6Month": 6,
        },
        {"Branch": "Angul", "Customer": "No serial", "Start Date": dt.datetime(2026, 1, 1)},
    ]


def upload(client: TestClient, path: str, content: bytes) -> Any:
    files = {"file": ("ASC DETAILS.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    return client.post(f"{URL}/{path}", files=files, data={"branchId": str(BRANCH)})


def count(db: Engine, model: Any) -> int:
    with Session(db) as s:
        return s.scalar(select(func.count()).select_from(model)) or 0


def test_import_preview_writes_nothing(client: TestClient, db: Engine) -> None:
    response = upload(client, "import/preview", register(register_rows()))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["applied"] is False
    assert result["summary"]["sheetName"] == "ASC-26-27"
    assert (result["summary"]["inserts"], result["summary"]["skips"]) == (3, 1)
    assert (result["summary"]["newMachines"], result["summary"]["newCustomers"], result["summary"]["newModels"]) == (
        2, 2, 1)
    assert count(db, ServiceContract) == 0
    assert count(db, MachineUnit) == 1


def test_import_creates_masters_and_contracts_and_reupload_updates(client: TestClient, db: Engine) -> None:
    applied = upload(client, "import", register(register_rows()))
    assert applied.status_code == 201, applied.text
    rows = {r["serialNumber"]: r for r in applied.json()["rows"]}
    assert rows["S200-54828"]["action"] == "insert" and not rows["S200-54828"]["newMachine"]
    assert rows["SP21-63379"]["newMachine"] and rows["SP21-63379"]["newCustomer"]
    assert not rows["SP21-63379"]["newModel"]  # EX-210SP = EX-210 SUPER+
    assert rows["ZX33-00092"]["newModel"]
    assert any("Bhubaneswar" in m for m in rows["ZX33-00092"]["messages"])
    assert rows["SP21-63379"]["contractNo"] == "JEYPORE/ASC/00001"

    with Session(db) as s:
        machine = s.scalars(select(MachineUnit).where(MachineUnit.serial_number == "SP21-63379")).one()
        assert s.get(MachineModel, machine.model_id).model_code == "EX-210 SUPER+"
        assert machine.commissioning_date == dt.date(2023, 5, 3)
        customer = s.get(Customer, machine.customer_id)
        assert (customer.code, customer.primary_phone, customer.priority_tier) == ("134250", "8637232421", "Key")
        assert customer.is_asc_customer
        mini = s.scalars(select(MachineModel).where(MachineModel.model_code == "ZX-33U")).one()
        assert mini.product_line == "Mini excavator"
        existing = s.scalars(
            select(ServiceContract).where(ServiceContract.customer_id == CUSTOMER_ID)
        ).one()
        assert (existing.visits_included, existing.visits_used, existing.contract_plan_id) == (6, 2, PLAN_6M)
        assert existing.engineer_employee_id == 300
        assert existing.is_renewal
        new = s.scalars(select(ServiceContract).where(ServiceContract.contract_no == "JEYPORE/ASC/00001")).one()
        assert new.end_date == dt.date(2027, 11, 21)
        assert new.contract_plan_id == PLAN_12M

    again = upload(client, "import", register(register_rows()))
    assert (again.json()["summary"]["inserts"], again.json()["summary"]["updates"]) == (0, 3)
    assert count(db, ServiceContract) == 3
    assert count(db, MachineUnit) == 3


def test_import_rejects_a_sheet_that_is_not_the_register(client: TestClient) -> None:
    workbook = Workbook()
    workbook.active.append(["C4C Ticket ID", "Subject"])
    buffer = BytesIO()
    workbook.save(buffer)
    response = upload(client, "import/preview", buffer.getvalue())
    assert response.status_code == 400
    assert "ASC register" in response.json()["detail"]
