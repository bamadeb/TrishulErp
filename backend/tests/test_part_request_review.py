"""Parts requests, next step: the alert to reviewers, the office list, reject, and convert to a quotation (SQLite)."""

import json
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import Alert, AlertRecipient, Quotation, QuotationLine
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company", "core.principal", "core.state", "core.branch", "core.uom", "core.hsn_sac", "core.item_category",
    "core.item", "core.customer", "core.customer_site", "core.customer_principal", "core.number_series",
    "core.payment_terms", "core.employee", "core.contact", "core.app_user", "core.audit_log", "core.role",
    "core.user_role", "core.user_principal_access", "core.lookup_type", "core.lookup_value", "core.location",
    "acc.gst_rate", "inv.lot_balance", "inv.stock_lot", "sal.price_list", "sal.price_list_item", "sal.quotation",
    "sal.quotation_version", "sal.quotation_line", "sal.sales_order", "svc.service_call", "svc.call_assignment",
    "svc.call_status_log", "svc.service_visit", "svc.service_part_request", "svc.sla_event", "core.alert_rule",
    "core.alert_rule_recipient", "core.alert", "core.alert_recipient",
]  # fmt: skip
COMPANY, ODISHA, BRAND, OTHER_BRAND, BRANCH = 1, 1, 1, 2, 1
ADMIN_ROLE, ENGINEER_ROLE = 1, 2
ADMIN_USER, ENGINEER_USER = 1, 2
ENGINEER = 300
CUSTOMER, OTHER_CUSTOMER = 51, 52
FILTER, OIL = 41, 42
CALL, OTHER_CALL = 24, 25
REVIEW = {"svc.part_request.review", "sal.quotation.manage", "sal.quotation.view", "svc.call.view"}
ENGINEER_PERMISSIONS = {"svc.call.view.assigned", "svc.part_request.create"}
SVC = "/api/v1/svc"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TREAD", legal_name="Trishul Tread Pvt. Ltd")
    insert_row(engine, "core.principal", id=BRAND, code="TATA_HITACHI", name="Tata Hitachi")
    insert_row(engine, "core.principal", id=OTHER_BRAND, code="BYD", name="BYD")
    insert_row(engine, "core.state", id=ODISHA, gst_state_code="21", name="Odisha")
    insert_row(engine, "core.branch", id=BRANCH, company_id=COMPANY, code="BBSR", name="Bhubaneswar",
               branch_type="Warehouse", state_id=ODISHA)  # fmt: skip
    insert_row(engine, "core.uom", id=1, code="EA", name="Each", decimals=0)
    insert_row(engine, "core.item_category", id=1, code="SP", name="Spare parts", item_nature="Spare part")
    for item_id, code, mrp in ((FILTER, "KF70500", Decimal(1200)), (OIL, "TL07110", None)):
        insert_row(engine, "core.item", id=item_id, company_id=COMPANY, item_code=code, principal_id=BRAND,
                   description=f"{code} item", category_id=1, uom_id=1, item_type="Stock", mrp=mrp)  # fmt: skip
    insert_row(engine, "core.payment_terms", id=3, code="NET30", description="30 days", days_before_due=30)
    for customer_id, code in ((CUSTOMER, "C1"), (OTHER_CUSTOMER, "C2")):
        insert_row(engine, "core.customer", id=customer_id, company_id=COMPANY, code=code, name=f"Customer {code}",
                   customer_type="Contractor", primary_phone="9437000000", billing_state_id=ODISHA,
                   billing_address=f"{code} road", payment_terms_id=3, opening_balance=Decimal(0),
                   gst_registration_type="Regular")  # fmt: skip
    insert_row(engine, "core.number_series", company_id=COMPANY, branch_id=BRANCH, document_type="QUOTATION",
               prefix="QT/", next_number=1, padding=3)  # fmt: skip
    insert_row(engine, "core.employee", id=ENGINEER, company_id=COMPANY, branch_id=BRANCH, employee_code="E300",
               first_name="Jyoti", last_name="Mohanty", employee_type="Permanent", status="Active")  # fmt: skip
    insert_row(engine, "core.role", id=ADMIN_ROLE, code="ADMIN", name="Administrator")
    insert_row(engine, "core.role", id=ENGINEER_ROLE, code="SERVICE_ENGINEER", name="Service Engineer")
    for user_id, username, employee, role in ((ADMIN_USER, "admin", None, ADMIN_ROLE),
                                              (ENGINEER_USER, "jyoti", ENGINEER, ENGINEER_ROLE)):  # fmt: skip
        insert_row(engine, "core.app_user", id=user_id, username=username, cognito_sub=f"sub-{username}",
                   employee_id=employee)  # fmt: skip
        insert_row(engine, "core.user_role", app_user_id=user_id, role_id=role, branch_id=None)
        insert_row(engine, "core.user_principal_access", app_user_id=user_id, principal_id=BRAND)
    insert_row(engine, "core.lookup_type", id=3, code="CALL_TYPE", name="CALL_TYPE", module="Service")
    insert_row(engine, "core.lookup_value", id=30, lookup_type_id=3, code="BREAKDOWN", label="Breakdown", sort_order=1)
    for call_id, customer in ((CALL, CUSTOMER), (OTHER_CALL, OTHER_CUSTOMER)):
        insert_row(engine, "svc.service_call", id=call_id, company_id=COMPANY, branch_id=BRANCH, principal_id=BRAND,
                   call_no=f"BHADRAK/SC/000{call_id}", customer_id=customer, assigned_engineer_id=ENGINEER,
                   call_type_lookup_id=30, current_status="In progress", priority="Normal")  # fmt: skip
    rule = insert_row(engine, "core.alert_rule", company_id=COMPANY, code="PART_REQUEST", name="Parts requested",
                      alert_type="SVC_PART_REQUEST", severity="Warning", parameters=json.dumps({}),
                      reraise_policy="Never", cooldown_minutes=0, is_active=True)  # fmt: skip
    insert_row(engine, "core.alert_rule_recipient", alert_rule_id=rule, recipient_type="Role", role_id=ADMIN_ROLE,
               channel="In-app")  # fmt: skip
    return engine


def client_for(settings: Settings, db: Engine, user_id: int, employee_id: int | None, perms: set[str]) -> TestClient:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(id=user_id, employee_id=employee_id, permissions=frozenset(perms), branch_ids=None,
                      principal_ids=None, default_branch_id=BRANCH)  # fmt: skip
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=user_id, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def engineer(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, ENGINEER_USER, ENGINEER, ENGINEER_PERMISSIONS) as c:
        yield c


@pytest.fixture
def admin(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, ADMIN_USER, None, REVIEW) as c:
        yield c


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def request_parts(client: TestClient, call: int = CALL, parts: list[dict[str, Any]] | None = None) -> list[Any]:
    body = {"parts": parts or [{"itemId": FILTER, "quantity": 2}, {"partDescription": "Seal kit", "quantity": 1}]}
    result: list[Any] = ok(client.post(f"{SVC}/service-calls/{call}/part-requests", json=body))
    return result


def open_alerts(db: Engine) -> list[tuple[int, str, str, list[int]]]:
    with Session(db) as s:
        alerts = s.scalars(select(Alert).where(Alert.status != "Resolved").order_by(Alert.id)).all()
        return [
            (a.entity_id, a.title, a.message,
             sorted(s.scalars(select(AlertRecipient.app_user_id).where(AlertRecipient.alert_id == a.id))))
            for a in alerts
        ]  # fmt: skip


def test_a_request_raises_an_alert_for_the_reviewers(engineer: TestClient, db: Engine) -> None:
    request_parts(engineer)
    assert open_alerts(db) == [
        (CALL, "Parts requested on BHADRAK/SC/00024",
         "2 parts requested on BHADRAK/SC/00024 for Customer C1: KF70500 x 2, Seal kit x 1.", [ADMIN_USER]),
    ]  # fmt: skip
    # A second request on the same call is a new alert (only its own parts).
    request_parts(engineer, parts=[{"itemId": OIL, "quantity": "7.5"}])
    assert [a[2] for a in open_alerts(db)][1] == "1 part requested on BHADRAK/SC/00024 for Customer C1: TL07110 x 7.5."


def test_office_lists_all_requests_and_the_engineer_sees_their_call(engineer: TestClient, admin: TestClient) -> None:
    request_parts(engineer)
    request_parts(engineer, call=OTHER_CALL, parts=[{"itemId": OIL, "quantity": 3}])
    page = ok(admin.get(f"{SVC}/part-requests"))
    assert page["total"] == 3
    first = page["items"][0]  # newest first
    assert (first["callNo"], first["customerName"], first["itemCode"], first["requestedByName"], first["status"]) == (
        "BHADRAK/SC/00025", "Customer C2", "TL07110", "Jyoti Mohanty", "Requested",
    )  # fmt: skip
    assert ok(admin.get(f"{SVC}/part-requests", params={"search": "seal"}))["total"] == 1
    assert ok(admin.get(f"{SVC}/part-requests", params={"status": "Quoted"}))["total"] == 0
    mine = ok(engineer.get(f"{SVC}/service-calls/{CALL}/part-requests"))
    assert [p["partDescription"] for p in mine] == ["KF70500 item", "Seal kit"]
    # The office list is for reviewers only.
    assert engineer.get(f"{SVC}/part-requests").status_code == 403


def test_convert_to_a_draft_quotation_and_resolve_the_alert(
    engineer: TestClient, admin: TestClient, db: Engine
) -> None:
    parts = request_parts(engineer)
    result = ok(admin.post(f"{SVC}/part-request-quotations", json={"partRequestIds": [p["id"] for p in parts]}), 201)
    assert result["quotationNo"] == "QT/001"
    assert {(p["status"], p["quotationNo"]) for p in result["parts"]} == {("Quoted", "QT/001")}
    with Session(db) as s:
        quotation = s.get(Quotation, result["quotationId"])
        assert quotation is not None
        assert (quotation.status, quotation.customer_id, quotation.principal_id) == ("Draft", CUSTOMER, BRAND)
        assert quotation.remarks == "Parts requested on service call BHADRAK/SC/00024"
        lines = s.scalars(select(QuotationLine).order_by(QuotationLine.line_no)).all()
        # The filter at its MRP (no price list); the unknown seal kit as a text line at 0 for the office to price.
        assert [(ln.item_id, ln.description, Decimal(ln.quantity), Decimal(ln.unit_price)) for ln in lines] == [
            (FILTER, "KF70500 item", Decimal(2), Decimal(1200)),
            (None, "Seal kit", Decimal(1), Decimal(0)),
        ]
    assert open_alerts(db) == []
    # Quoting the same parts again is refused.
    again = admin.post(f"{SVC}/part-request-quotations", json={"partRequestIds": [parts[0]["id"]]})
    assert again.status_code == 409


def test_alert_stays_open_until_every_part_is_reviewed(engineer: TestClient, admin: TestClient, db: Engine) -> None:
    filter_part, seal = request_parts(engineer)
    rejected = ok(admin.post(f"{SVC}/part-requests/{seal['id']}/reject", json={"note": "Not stocked"}))
    assert (rejected["status"], rejected["reviewNote"], rejected["reviewedBy"]) == ("Rejected", "Not stocked", "admin")
    assert len(open_alerts(db)) == 1  # the filter is still waiting
    ok(admin.post(f"{SVC}/part-request-quotations", json={"partRequestIds": [filter_part["id"]]}), 201)
    assert open_alerts(db) == []


def test_one_quotation_is_for_one_customer(engineer: TestClient, admin: TestClient) -> None:
    first = request_parts(engineer, parts=[{"itemId": FILTER, "quantity": 1}])
    other = request_parts(engineer, call=OTHER_CALL, parts=[{"itemId": OIL, "quantity": 1}])
    response = admin.post(f"{SVC}/part-request-quotations", json={"partRequestIds": [first[0]["id"], other[0]["id"]]})
    assert response.status_code == 400
    assert "partRequestIds" in response.json()["errors"]


def test_converting_needs_the_quotation_permission(settings: Settings, db: Engine, engineer: TestClient) -> None:
    parts = request_parts(engineer)
    with client_for(settings, db, ADMIN_USER, None, {"svc.part_request.review"}) as reviewer:
        response = reviewer.post(f"{SVC}/part-request-quotations", json={"partRequestIds": [parts[0]["id"]]})
        assert response.status_code == 403
