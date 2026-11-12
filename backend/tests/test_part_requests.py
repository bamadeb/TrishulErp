"""Parts requests against a service call: route -> service -> SQL (SQLite)."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.config import Settings
from trishul_api.db.models import ServicePartRequest

from .sqlite_db import insert_row, sqlite_engine
from .test_manual_travel import BRANCH, COMPANY, CUSTOMER, ENGINEER, OTHER_ENGINEER, PRINCIPAL, client_for

TABLES = [
    "core.company",
    "core.branch",
    "core.principal",
    "core.customer",
    "core.employee",
    "core.app_user",
    "core.audit_log",
    "core.lookup_type",
    "core.lookup_value",
    "core.uom",
    "core.item_category",
    "core.item",
    "svc.service_call",
    "svc.call_assignment",
    "svc.service_visit",
    "svc.service_part_request",
]
CALL, VISIT, OTHER_CALL_VISIT = 24, 500, 501
NOS, LTR = 1, 2
FILTER, OIL, BYD_PART, OLD_PART = 11, 12, 13, 14
URL = f"/api/v1/svc/service-calls/{CALL}/part-requests"
ENGINEER_PERMISSIONS = {"svc.call.view.assigned", "svc.part_request.create"}


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TRISHUL", legal_name="Trishul", trade_name="Trishul")
    insert_row(engine, "core.branch", id=BRANCH, company_id=COMPANY, code="BBSR", name="Bhubaneswar")
    insert_row(engine, "core.principal", id=PRINCIPAL, code="TATA_HITACHI", name="Tata Hitachi")
    insert_row(engine, "core.principal", id=2, code="BYD", name="BYD")
    insert_row(
        engine,
        "core.customer",
        id=CUSTOMER,
        company_id=COMPANY,
        code="C100",
        name="Blue Earth",
        customer_type="Company",
        primary_phone="9000000000",
    )
    for emp in (ENGINEER, OTHER_ENGINEER):
        insert_row(
            engine,
            "core.employee",
            id=emp,
            company_id=COMPANY,
            branch_id=BRANCH,
            employee_code=f"E{emp}",
            first_name="Eng",
            last_name="Das",
            employee_type="Permanent",
            status="Active",
        )
    for user_id, emp in ((1, ENGINEER), (2, OTHER_ENGINEER)):
        insert_row(
            engine, "core.app_user", id=user_id, username=f"u{user_id}", cognito_sub=f"s{user_id}", employee_id=emp
        )
    insert_row(engine, "core.lookup_type", id=3, code="CALL_TYPE", name="CALL_TYPE", module="Service")
    insert_row(engine, "core.lookup_value", id=30, lookup_type_id=3, code="BREAKDOWN", label="Breakdown", sort_order=1)
    insert_row(engine, "core.uom", id=NOS, code="NOS", name="Numbers")
    insert_row(engine, "core.uom", id=LTR, code="LTR", name="Litre")
    insert_row(engine, "core.item_category", id=1, code="SPARES", name="Spares", item_nature="Spare part")
    for item_id, code, principal, uom, active in (
        (FILTER, "KF70500", PRINCIPAL, NOS, True),
        (OIL, "TL064005", None, LTR, True),
        (BYD_PART, "BYD-01", 2, NOS, True),
        (OLD_PART, "OLD-01", PRINCIPAL, NOS, False),
    ):
        insert_row(
            engine,
            "core.item",
            id=item_id,
            company_id=COMPANY,
            item_code=code,
            principal_id=principal,
            oem_part_number=f"OEM-{code}",
            description=f"{code} description",
            category_id=1,
            uom_id=uom,
            item_type="Stock",
            is_active=active,
        )
    for call_id, status in ((CALL, "In progress"), (25, "Closed"), (26, "In progress")):
        insert_row(
            engine,
            "svc.service_call",
            id=call_id,
            company_id=COMPANY,
            branch_id=BRANCH,
            principal_id=PRINCIPAL,
            call_no=f"BHADRAK/SC/000{call_id}",
            customer_id=CUSTOMER,
            assigned_engineer_id=ENGINEER,
            call_type_lookup_id=30,
            current_status=status,
        )
    for visit_id, call_id in ((VISIT, CALL), (OTHER_CALL_VISIT, 26)):
        insert_row(
            engine,
            "svc.service_visit",
            id=visit_id,
            service_call_id=call_id,
            visit_no=1,
            visit_purpose="Inspection",
            engineer_employee_id=ENGINEER,
            status="On site",
        )
    return engine


@pytest.fixture
def engineer(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, 1, ENGINEER, ENGINEER_PERMISSIONS) as c:
        yield c


@pytest.fixture
def other(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, 2, OTHER_ENGINEER, ENGINEER_PERMISSIONS) as c:
        yield c


def test_engineer_requests_parts_on_their_call(engineer: TestClient, db: Engine) -> None:
    response = engineer.post(
        URL,
        json={
            "serviceVisitId": VISIT,
            "requiredByDate": "2026-11-20",
            "parts": [
                {"itemId": FILTER, "quantity": 2},
                {"itemId": OIL, "quantity": "7.5", "isChargeable": False},
                {"partDescription": "Hydraulic hose 1/2in x 2m", "quantity": 1, "uomId": NOS},
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [(p["itemCode"], Decimal(p["quantity"]), p["uomCode"], p["isChargeable"]) for p in body] == [
        ("KF70500", Decimal(2), "NOS", True),
        ("TL064005", Decimal("7.5"), "LTR", False),
        (None, Decimal(1), "NOS", True),
    ]
    assert body[0]["partDescription"] == "KF70500 description"
    assert body[2]["partDescription"] == "Hydraulic hose 1/2in x 2m"
    assert {p["status"] for p in body} == {"Requested"}
    assert {p["requestChannel"] for p in body} == {"App"}
    assert {p["requestedByEmployeeId"] for p in body} == {ENGINEER}
    assert {p["callNo"] for p in body} == {"BHADRAK/SC/00024"}
    with Session(db) as s:
        rows = s.scalars(select(ServicePartRequest).order_by(ServicePartRequest.id)).all()
        assert [(r.service_call_id, r.service_visit_id, r.created_by_user_id) for r in rows] == [(CALL, VISIT, 1)] * 3


def test_engineer_not_on_the_call_gets_404(other: TestClient) -> None:
    response = other.post(URL, json={"parts": [{"itemId": FILTER, "quantity": 1}]})
    assert response.status_code == 404


def test_each_part_needs_an_item_or_a_description(engineer: TestClient) -> None:
    assert engineer.post(URL, json={"parts": [{"quantity": 1}]}).status_code in (400, 422)
    assert engineer.post(URL, json={"parts": []}).status_code in (400, 422)
    assert engineer.post(URL, json={"parts": [{"itemId": FILTER, "quantity": 0}]}).status_code in (400, 422)


def test_parts_of_another_brand_or_inactive_are_refused(engineer: TestClient, db: Engine) -> None:
    response = engineer.post(
        URL, json={"parts": [{"itemId": BYD_PART, "quantity": 1}, {"itemId": OLD_PART, "quantity": 1}]}
    )
    assert response.status_code == 400
    assert set(response.json()["errors"]) == {"parts[0].itemId", "parts[1].itemId"}
    with Session(db) as s:
        assert s.scalars(select(ServicePartRequest)).all() == []


def test_visit_must_belong_to_the_call(engineer: TestClient) -> None:
    response = engineer.post(URL, json={"serviceVisitId": OTHER_CALL_VISIT, "parts": [{"itemId": OIL, "quantity": 1}]})
    assert response.status_code == 400
    assert "serviceVisitId" in response.json()["errors"]


def test_no_requests_on_a_finished_call(engineer: TestClient) -> None:
    response = engineer.post(
        "/api/v1/svc/service-calls/25/part-requests", json={"parts": [{"itemId": OIL, "quantity": 1}]}
    )
    assert response.status_code == 400


def test_permission_is_required(settings: Settings, db: Engine) -> None:
    with client_for(settings, db, 1, ENGINEER, {"svc.call.view.assigned"}) as c:
        assert c.post(URL, json={"parts": [{"itemId": OIL, "quantity": 1}]}).status_code == 403
