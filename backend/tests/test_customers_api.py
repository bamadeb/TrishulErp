"""Customer management through the API: route -> service -> repository -> SQL (SQLite)."""

from collections.abc import Iterator
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
    "core.customer",
    "core.company",
    "core.state",
    "core.audit_log",
]
COMPANY = 1
ODISHA, MAHARASHTRA = 1, 2
BLUE = 10  # an existing active customer
ACTOR_ID = 1
URL = "/api/v1/core/customers"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TRISHUL", legal_name="Trishul Pvt Ltd", trade_name="Trishul")
    insert_row(engine, "core.state", id=ODISHA, gst_state_code="21", name="Odisha")
    insert_row(engine, "core.state", id=MAHARASHTRA, gst_state_code="27", name="Maharashtra")
    insert_row(
        engine,
        "core.customer",
        id=BLUE,
        company_id=COMPANY,
        code="C010",
        name="Blue Earth Movers",
        customer_type="Contractor",
        primary_phone="9822000010",
        gst_registration_type="Regular",
        gstin="21AAAAA0000A1Z5",
        billing_state_id=ODISHA,
        priority_tier="Normal",
        is_asc_customer=False,
    )
    return engine


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(
        id=ACTOR_ID,
        permissions=frozenset({"core.customer.view", "core.customer.manage"}),
        branch_ids=None,
        principal_ids=None,
    )
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=ACTOR_ID, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def create(client: TestClient, **changes: Any) -> httpx.Response:
    body = {
        "code": "C100",
        "name": "Acme Constructions",
        "customerType": "Company",
        "companyId": COMPANY,
        "primaryPhone": "9876500100",
        "email": "acme@example.com",
        "gstin": "27BBBBB1111B1Z5",
        "billingStateId": MAHARASHTRA,
    } | changes
    return client.post(URL, json=body)


def if_match(customer: dict[str, Any]) -> dict[str, str]:
    return {"If-Match": f'"{customer["rowVersion"]}"'}


def test_create_resolves_names_and_defaults(client: TestClient) -> None:
    response = create(client)
    assert response.status_code == 201, response.text
    customer = response.json()
    assert response.headers["location"] == f"customers/{customer['id']}"
    assert (customer["code"], customer["name"]) == ("C100", "Acme Constructions")
    assert customer["customerType"] == "Company"
    assert customer["billingStateName"] == "Maharashtra"
    assert customer["companyName"] == "Trishul"
    assert customer["gstRegistrationType"] == "Unregistered"  # default applied
    assert customer["priorityTier"] == "Normal"  # default applied
    assert customer["isAscCustomer"] is False
    assert customer["isActive"] is True


def test_duplicate_code_is_rejected(client: TestClient) -> None:
    assert create(client).status_code == 201
    assert create(client).status_code == 409  # same code again
    assert create(client, code="C010").status_code == 409  # BLUE's code


def test_unknown_references_are_rejected_with_field_errors(client: TestClient) -> None:
    assert create(client, companyId=99).status_code == 400
    assert "companyId" in create(client, companyId=99).json()["errors"]
    assert create(client, billingStateId=99).status_code == 400
    assert "billingStateId" in create(client, billingStateId=99).json()["errors"]


def test_invalid_input_is_rejected(client: TestClient) -> None:
    assert create(client, primaryPhone="!!!").status_code == 422
    assert create(client, customerType="Ghost").status_code == 422
    assert create(client, name="").status_code == 422
    assert create(client, isActive=True).status_code == 422  # unknown field


def test_list_filters_by_status_type_and_search(client: TestClient) -> None:
    create(client)  # C100, Company
    create(client, code="C101", name="Ravi Kumar", customerType="Individual", primaryPhone="9876500101")
    everyone = client.get(URL).json()
    assert everyone["total"] == 3  # BLUE + two created
    companies = client.get(URL, params={"customerType": "Company"}).json()["items"]
    assert {c["code"] for c in companies} == {"C100"}
    found = client.get(URL, params={"search": "ravi"}).json()["items"]
    assert [c["name"] for c in found] == ["Ravi Kumar"]
    assert client.get(URL, params={"status": "inactive"}).json()["total"] == 0


def test_get_one_and_unknown_is_404(client: TestClient) -> None:
    assert client.get(f"{URL}/{BLUE}").json()["code"] == "C010"
    assert client.get(f"{URL}/999").status_code == 404


def test_update_changes_fields_with_a_row_version_check(client: TestClient) -> None:
    customer = client.get(f"{URL}/{BLUE}").json()
    url = f"{URL}/{BLUE}"
    change = {"name": "Blue Earth Movers LLP", "billingStateId": MAHARASHTRA}

    assert client.patch(url, json=change).status_code == 428  # If-Match missing
    assert client.patch(url, json=change, headers={"If-Match": '"AAAAAAAAAAA="'}).status_code == 409

    updated = client.patch(url, json=change, headers=if_match(customer))
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["name"] == "Blue Earth Movers LLP"
    assert body["billingStateName"] == "Maharashtra"
    assert body["code"] == "C010"  # not sent, unchanged


def test_update_rejects_duplicate_code(client: TestClient) -> None:
    created = create(client).json()
    url = f"{URL}/{created['id']}"
    assert client.patch(url, json={"code": "C010"}, headers=if_match(created)).status_code == 409


def test_deactivate_and_activate(client: TestClient) -> None:
    deactivated = client.post(f"{URL}/{BLUE}/deactivate").json()
    assert deactivated["isActive"] is False
    assert BLUE not in [c["id"] for c in client.get(URL).json()["items"]]  # default filter is active
    activated = client.post(f"{URL}/{BLUE}/activate").json()
    assert activated["isActive"] is True


def test_form_options(client: TestClient) -> None:
    options = client.get(f"{URL}/form-options").json()
    assert [c["name"] for c in options["companies"]] == ["Trishul"]
    assert {s["name"] for s in options["states"]} == {"Odisha", "Maharashtra"}
