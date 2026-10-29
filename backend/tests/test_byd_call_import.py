"""BYD service-call import: route -> service -> repository -> SQL (SQLite).

Builds small in-memory .xlsx files shaped like the Tata Hitachi C4C exports and checks the upsert:
new C4C Ticket IDs are inserted, known ones are updated (never duplicated), and rows whose customer
or machine is missing are still imported and flagged for linking.
"""

import datetime as dt
from collections.abc import Iterator
from io import BytesIO
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import BydCallImport, Customer, ServiceCall
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "core.principal",
    "core.customer",
    "core.machine_model",
    "core.machine_unit",
    "core.employee",
    "core.lookup_type",
    "core.lookup_value",
    "core.number_series",
    "core.app_user",
    "core.audit_log",
    "svc.service_call",
    "svc.byd_call_import",
]

COMPANY, BRANCH, PRINCIPAL = 1, 1, 1
CUSTOMER_ID, MACHINE_ID, ENGINEER_ID, ACTOR_ID = 100, 200, 300, 1
CUSTOMER_NAME = "SBB CONSTRUCTIONS PRIVATE LIMITED"
MACHINE_RP = "RP-1"
ENGINEER_NAME = "Satyajit Tung"

PREVIEW = "/api/v1/svc/service-calls/import/preview"
IMPORT = "/api/v1/svc/service-calls/import"

ORDER_HEADERS = [
    "C4C Ticket ID",
    "Service Order ID",
    "Subject",
    "Account",
    "Registered Product ID",
    "Priority",
    "Breakdown",
    "Warranty",
    "Cancellation Status",
    "Type",
    "Engineer Name",
    "Incoming Caller Name",
    "Incoming Phone Number",
    "Malfunction Actual Date & Time",
    "Completion By",
]
REQUEST_HEADERS = [
    "C4C Ticket ID",
    "Service Request ID",
    "Subject",
    "Account",
    "Registered Product ID",
    "breakdown",
    "Warranty",
    "Cancelled Call",
    "Type",
    "Incoming Caller Name",
    "Reported On",
]


def make_xlsx(headers: list[str], rows: list[dict[str, Any]], *, preamble: int = 2) -> bytes:
    """A workbook with a title preamble above the header row, like the real BYD download."""
    workbook = Workbook()
    sheet = workbook.active
    for _ in range(preamble):
        sheet.append(["Service Orders (All Orders)"])
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(header) for header in headers])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def order_rows() -> list[dict[str, Any]]:
    return [
        {
            "C4C Ticket ID": "T1",
            "Service Order ID": "SO1",
            "Subject": "5000 Hrs Service",
            "Account": CUSTOMER_NAME,
            "Registered Product ID": MACHINE_RP,
            "Priority": "High",
            "Breakdown": "No",
            "Warranty": "No",
            "Type": "Z001",
            "Engineer Name": "Satyajit Tung .",  # BYD trailing dot
            "Incoming Caller Name": "Nilamadhab",
            "Incoming Phone Number": 7894435328,
            "Malfunction Actual Date & Time": dt.datetime(2026, 9, 30, 15, 22),
            "Completion By": dt.datetime(2026, 10, 2, 15, 17),
        },
        {
            "C4C Ticket ID": "T2",
            "Service Order ID": "SO2",
            "Subject": "Electrical Problem",
            "Account": "UNKNOWN CORP",
            "Registered Product ID": "RP-X",
            "Priority": "Normal",
            "Breakdown": "Yes",
            "Warranty": "No",
            "Engineer Name": "Ghost Rider",
            "Incoming Phone Number": 9999999999,
        },
        {"C4C Ticket ID": None, "Service Order ID": "SO3", "Subject": "No ticket", "Account": CUSTOMER_NAME},
    ]


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TRISHUL", legal_name="Trishul", trade_name="Trishul")
    insert_row(engine, "core.branch", id=BRANCH, company_id=COMPANY, code="BBSR", name="Bhubaneswar")
    insert_row(engine, "core.principal", id=PRINCIPAL, code="TATA_HITACHI", name="Tata Hitachi")
    insert_row(engine, "core.customer", id=CUSTOMER_ID, company_id=COMPANY, code="C100", name=CUSTOMER_NAME,
               customer_type="Company", primary_phone="9000000000")
    insert_row(engine, "core.machine_model", id=1, model_code="EX200", model_name="EX200", principal_id=PRINCIPAL)
    insert_row(engine, "core.machine_unit", id=MACHINE_ID, serial_number="SN-1", oem_registered_product_id=MACHINE_RP,
               model_id=1, principal_id=PRINCIPAL, status="Sold")
    insert_row(engine, "core.employee", id=ENGINEER_ID, company_id=COMPANY, branch_id=BRANCH, employee_code="E300",
               first_name="Satyajit", last_name="Tung", employee_type="Permanent", status="Active")
    insert_row(engine, "core.lookup_type", id=1, code="CALL_SOURCE", name="Call Source", module="Service")
    insert_row(engine, "core.lookup_value", id=11, lookup_type_id=1, code="OEM_CUSTOMER_CARE_PER_BRAND",
               label="OEM Customer Care", sort_order=1)
    insert_row(engine, "core.lookup_type", id=2, code="CALL_TYPE", name="Call Type", module="Service")
    insert_row(engine, "core.lookup_value", id=21, lookup_type_id=2, code="BREAKDOWN", label="Breakdown", sort_order=1)
    insert_row(engine, "core.lookup_value", id=22, lookup_type_id=2, code="PERIODIC_SERVICE",
               label="Periodic service", sort_order=2)
    insert_row(engine, "core.number_series", id=1, company_id=COMPANY, document_type="SERVICE_CALL",
               prefix="SC-", next_number=1, padding=4)
    insert_row(engine, "core.app_user", id=ACTOR_ID, username="back.office@trishul.co", cognito_sub="sub-bo")
    return engine


def make_client(settings: Settings, db: Engine, permissions: set[str]) -> TestClient:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(id=ACTOR_ID, permissions=frozenset(permissions), default_branch_id=BRANCH,
                      branch_ids=frozenset({BRANCH}), principal_ids=None)
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=ACTOR_ID, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with make_client(settings, db, {"svc.call.import"}) as test_client:
        yield test_client


def post_file(client: TestClient, url: str, content: bytes, **data: str) -> httpx.Response:
    return client.post(url, files={"file": ("export.xlsx", content, "application/vnd.ms-excel")}, data=data)


def calls(db: Engine) -> list[ServiceCall]:
    with Session(db) as s:
        return list(s.scalars(select(ServiceCall).order_by(ServiceCall.id)))


def test_preview_classifies_rows_without_writing(client: TestClient, db: Engine) -> None:
    response = post_file(client, PREVIEW, make_xlsx(ORDER_HEADERS, order_rows()))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"] == {
        "sourceKind": "Service orders",
        "fileName": "export.xlsx",
        "total": 3,
        "inserts": 2,
        "updates": 0,
        "skips": 1,
        "needsLinking": 1,
    }
    by_ticket = {row["c4CTicketId"]: row for row in body["rows"]}
    assert by_ticket["T1"]["customerMatched"] and by_ticket["T1"]["machineMatched"]
    assert by_ticket["T1"]["engineerMatched"] and not by_ticket["T1"]["needsLinking"]
    assert by_ticket["T2"]["needsLinking"] and not by_ticket["T2"]["customerMatched"]
    assert next(r for r in body["rows"] if r["action"] == "skip")["rowNumber"] == 6
    # Nothing was written.
    with Session(db) as s:
        assert s.scalar(select(func.count()).select_from(ServiceCall)) == 0
        assert s.scalar(select(func.count()).select_from(BydCallImport)) == 0


def test_apply_inserts_and_maps_fields(client: TestClient, db: Engine) -> None:
    response = post_file(client, IMPORT, make_xlsx(ORDER_HEADERS, order_rows()))
    assert response.status_code == 201, response.text
    summary = response.json()["summary"]
    assert (summary["inserts"], summary["updates"], summary["skips"], summary["needsLinking"]) == (2, 0, 1, 1)

    created = {c.oem_call_id: c for c in calls(db)}
    assert set(created) == {"T1", "T2"}
    t1 = created["T1"]
    assert t1.call_no.startswith("SC-") and t1.customer_id == CUSTOMER_ID and t1.machine_unit_id == MACHINE_ID
    assert t1.assigned_engineer_id == ENGINEER_ID and t1.current_status == "Assigned"
    assert t1.priority == "High" and t1.is_machine_down is False and t1.needs_master_linking is False
    assert t1.source_reference == "SO1" and t1.caller_phone == "7894435328"

    t2 = created["T2"]
    assert t2.customer_id != CUSTOMER_ID and t2.machine_unit_id is None  # placeholder customer, no machine
    assert t2.external_account_name == "UNKNOWN CORP" and t2.external_product_id == "RP-X"
    assert t2.needs_master_linking is True and t2.current_status == "Logged" and t2.is_machine_down is True

    with Session(db) as s:
        batch = s.scalars(select(BydCallImport)).one()
        assert (batch.inserted_count, batch.updated_count, batch.failed_count, batch.unlinked_count) == (2, 0, 1, 1)
        assert s.scalar(select(func.count()).where(Customer.code == "BYD-UNLINKED")) == 1


def test_reimporting_the_same_file_updates_and_never_duplicates(client: TestClient, db: Engine) -> None:
    content = make_xlsx(ORDER_HEADERS, order_rows())
    assert post_file(client, IMPORT, content).status_code == 201
    second = post_file(client, IMPORT, content)
    assert second.status_code == 201
    summary = second.json()["summary"]
    assert (summary["inserts"], summary["updates"]) == (0, 2)
    assert len(calls(db)) == 2  # still two calls, not four


def test_order_updates_the_call_a_request_created(client: TestClient, db: Engine) -> None:
    request_file = make_xlsx(
        REQUEST_HEADERS,
        [{
            "C4C Ticket ID": "T9",
            "Service Request ID": "SR9",
            "Subject": "New complaint",
            "Account": CUSTOMER_NAME,
            "Registered Product ID": MACHINE_RP,
            "breakdown": "No",
            "Warranty": "No",
            "Type": "Z007",
            "Incoming Caller Name": "Caller",
            "Reported On": dt.datetime(2026, 10, 1, 6, 44),
        }],
    )
    assert post_file(client, IMPORT, request_file).status_code == 201
    logged = calls(db)
    assert len(logged) == 1 and logged[0].current_status == "Logged" and logged[0].assigned_engineer_id is None

    order_file = make_xlsx(
        ORDER_HEADERS,
        [{
            "C4C Ticket ID": "T9",
            "Service Order ID": "SO9",
            "Subject": "New complaint",
            "Account": CUSTOMER_NAME,
            "Registered Product ID": MACHINE_RP,
            "Priority": "High",
            "Breakdown": "No",
            "Engineer Name": "Satyajit Tung .",
        }],
    )
    response = post_file(client, IMPORT, order_file)
    assert response.json()["summary"]["updates"] == 1
    assigned = calls(db)
    assert len(assigned) == 1  # same call, not a new one
    assert assigned[0].current_status == "Assigned" and assigned[0].assigned_engineer_id == ENGINEER_ID


def test_update_keeps_an_existing_link_and_is_not_flagged(client: TestClient, db: Engine) -> None:
    # A call already linked to a real customer and machine, with a BYD ticket.
    insert_row(db, "svc.service_call", company_id=COMPANY, branch_id=BRANCH, principal_id=PRINCIPAL,
               call_no="SC-0005", customer_id=CUSTOMER_ID, machine_unit_id=MACHINE_ID, oem_call_id="T5",
               current_status="Logged")
    # The export names the account differently (won't match), but the call is already linked.
    order = make_xlsx(ORDER_HEADERS, [{
        "C4C Ticket ID": "T5",
        "Service Order ID": "SO5",
        "Subject": "Follow up",
        "Account": "A DIFFERENT NAME THAT WONT MATCH",
        "Registered Product ID": MACHINE_RP,
        "Priority": "Normal",
        "Breakdown": "No",
    }])
    preview = post_file(client, PREVIEW, order).json()
    row = next(r for r in preview["rows"] if r["c4CTicketId"] == "T5")
    assert row["action"] == "update"
    assert row["customerMatched"] is False  # the name didn't match...
    assert row["needsLinking"] is False  # ...but the call is already linked, so not flagged
    assert preview["summary"]["needsLinking"] == 0


def test_customer_matches_despite_legal_form_and_punctuation(client: TestClient, db: Engine) -> None:
    # Master name differs only by suffix wording / punctuation / case from the BYD account.
    insert_row(db, "core.customer", id=101, company_id=COMPANY, code="C101",
               name="Deccan Fabricators Pvt. Ltd.", customer_type="Company", primary_phone="9000000101")
    order = make_xlsx(ORDER_HEADERS, [{
        "C4C Ticket ID": "T7",
        "Service Order ID": "SO7",
        "Subject": "Service",
        "Account": "DECCAN FABRICATORS PRIVATE LIMITED",
        "Priority": "Normal",
        "Breakdown": "No",
    }])
    preview = post_file(client, PREVIEW, order).json()
    row = next(r for r in preview["rows"] if r["c4CTicketId"] == "T7")
    assert row["customerMatched"] is True


def test_an_unrecognized_file_is_rejected(client: TestClient) -> None:
    junk = make_xlsx(["Foo", "Bar"], [{"Foo": 1, "Bar": 2}])
    response = post_file(client, PREVIEW, junk)
    assert response.status_code == 400
    assert "BYD" in response.json()["detail"]


def test_import_requires_the_permission(settings: Settings, db: Engine) -> None:
    with make_client(settings, db, set()) as client:
        response = post_file(client, IMPORT, make_xlsx(ORDER_HEADERS, order_rows()))
    assert response.status_code == 403
