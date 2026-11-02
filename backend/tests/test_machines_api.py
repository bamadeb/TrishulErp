"""Machine management with customer mapping: route -> service -> repository -> SQL (SQLite)."""

from collections.abc import Iterator
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import MachineOwnership
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.principal",
    "core.customer",
    "core.machine_model",
    "core.machine_unit",
    "core.machine_ownership",
    "core.audit_log",
]
COMPANY, HITACHI, BYD = 1, 1, 2
BLUE, ACME = 10, 11  # customers
EX200, BYD_MODEL = 1, 2  # machine models
EXISTING = 100  # a machine of BLUE
ACTOR_ID = 1
URL = "/api/v1/svc/machines"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TRISHUL", legal_name="Trishul", trade_name="Trishul")
    insert_row(engine, "core.principal", id=HITACHI, code="TATA_HITACHI", name="Tata Hitachi")
    insert_row(engine, "core.principal", id=BYD, code="BYD", name="BYD")
    for cid, code, name in ((BLUE, "C010", "Blue Earth Movers"), (ACME, "C011", "Acme Constructions")):
        insert_row(
            engine,
            "core.customer",
            id=cid,
            company_id=COMPANY,
            code=code,
            name=name,
            customer_type="Company",
            primary_phone="9000000000",
        )
    insert_row(
        engine,
        "core.machine_model",
        id=EX200,
        model_code="EX200",
        model_name="EX 200LC",
        product_line="Excavator",
        principal_id=HITACHI,
    )
    insert_row(
        engine,
        "core.machine_model",
        id=BYD_MODEL,
        model_code="E6",
        model_name="BYD E6",
        product_line="Other",
        principal_id=BYD,
    )
    insert_row(
        engine,
        "core.machine_unit",
        id=EXISTING,
        serial_number="SN-100",
        model_id=EX200,
        principal_id=HITACHI,
        customer_id=BLUE,
        status="Sold",
    )
    return engine


def make_client(
    settings: Settings, db: Engine, permissions: set[str], principal_ids: set[int] | None = None
) -> TestClient:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(
        id=ACTOR_ID,
        permissions=frozenset(permissions),
        branch_ids=None,
        principal_ids=frozenset(principal_ids) if principal_ids else None,
    )
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=ACTOR_ID, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with make_client(settings, db, {"core.machine.view", "core.machine.manage"}) as test_client:
        yield test_client


def create(client: TestClient, **changes: Any) -> httpx.Response:
    body = {"serialNumber": "SN-200", "modelId": EX200, "customerId": ACME, "engineNumber": "ENG-1"} | changes
    return client.post(URL, json=body)


def if_match(machine: dict[str, Any]) -> dict[str, str]:
    return {"If-Match": f'"{machine["rowVersion"]}"'}


def owners(db: Engine, machine_id: int) -> list[tuple[int, bool]]:
    """(customer id, still current) of each ownership row, oldest first."""
    with Session(db) as s:
        rows = s.scalars(
            select(MachineOwnership).where(MachineOwnership.machine_unit_id == machine_id).order_by(MachineOwnership.id)
        )
        return [(r.customer_id, r.to_date is None) for r in rows]


def test_create_links_the_customer_and_takes_the_brand_from_the_model(client: TestClient, db: Engine) -> None:
    response = create(client)
    assert response.status_code == 201, response.text
    machine = response.json()
    assert response.headers["location"] == f"machines/{machine['id']}"
    assert (machine["serialNumber"], machine["modelName"], machine["productLine"]) == (
        "SN-200",
        "EX 200LC",
        "Excavator",
    )
    assert (machine["customerId"], machine["customerName"]) == (ACME, "Acme Constructions")
    assert machine["principalCode"] == "TATA_HITACHI"
    assert machine["status"] == "Sold" and machine["isActive"] is True
    assert owners(db, machine["id"]) == [(ACME, True)]


def test_create_requires_a_customer_and_valid_references(client: TestClient) -> None:
    body = {"serialNumber": "SN-300", "modelId": EX200}
    assert client.post(URL, json=body).status_code == 422  # no customer
    assert "customerId" in create(client, customerId=999).json()["errors"]
    assert "modelId" in create(client, modelId=999).json()["errors"]


def test_inactive_customer_cannot_own_a_new_machine(client: TestClient, db: Engine) -> None:
    insert_row(
        db,
        "core.customer",
        id=12,
        company_id=COMPANY,
        code="C012",
        name="Gone Ltd",
        customer_type="Company",
        primary_phone="9000000000",
        is_active=False,
    )
    assert "customerId" in create(client, customerId=12).json()["errors"]


def test_duplicate_serial_is_rejected(client: TestClient) -> None:
    assert create(client).status_code == 201
    assert create(client).status_code == 409
    assert create(client, serialNumber="SN-100").status_code == 409  # EXISTING's serial


def test_model_of_a_brand_the_user_cannot_use_is_rejected(settings: Settings, db: Engine) -> None:
    with make_client(settings, db, {"core.machine.manage"}, principal_ids={HITACHI}) as client:
        assert "modelId" in create(client, modelId=BYD_MODEL).json()["errors"]
        assert create(client).status_code == 201


def test_list_filters_by_customer_status_and_search(client: TestClient) -> None:
    create(client)  # SN-200 for ACME
    assert client.get(URL).json()["total"] == 2
    acme = client.get(URL, params={"customerId": ACME}).json()["items"]
    assert [m["serialNumber"] for m in acme] == ["SN-200"]
    found = client.get(URL, params={"search": "blue earth"}).json()["items"]
    assert [m["serialNumber"] for m in found] == ["SN-100"]  # search covers the owner's name


def test_list_is_narrowed_to_the_selected_brand(client: TestClient) -> None:
    create(client, serialNumber="BYD-1", modelId=BYD_MODEL)
    hitachi = client.get(URL, headers={"X-Principal-Id": str(HITACHI)}).json()["items"]
    assert {m["serialNumber"] for m in hitachi} == {"SN-100"}


def test_update_changes_owner_with_row_version_check_and_keeps_history(client: TestClient, db: Engine) -> None:
    url = f"{URL}/{EXISTING}"
    machine = client.get(url).json()
    change = {"customerId": ACME, "registrationNumber": "OD02AB1234"}

    assert client.patch(url, json=change).status_code == 428  # If-Match missing
    assert client.patch(url, json=change, headers={"If-Match": '"AAAAAAAAAAA="'}).status_code == 409

    updated = client.patch(url, json=change, headers=if_match(machine))
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert (body["customerId"], body["registrationNumber"]) == (ACME, "OD02AB1234")
    assert body["serialNumber"] == "SN-100"  # not sent, unchanged
    assert owners(db, EXISTING) == [(ACME, True)]  # no earlier ownership row for this machine

    again = client.patch(url, json={"customerId": BLUE}, headers=if_match(body)).json()
    assert again["customerId"] == BLUE
    assert owners(db, EXISTING) == [(ACME, False), (BLUE, True)]  # previous owner closed


def test_update_cannot_unlink_the_customer(client: TestClient) -> None:
    machine = client.get(f"{URL}/{EXISTING}").json()
    response = client.patch(f"{URL}/{EXISTING}", json={"customerId": None}, headers=if_match(machine))
    assert response.status_code == 400
    assert "customerId" in response.json()["errors"]


def test_deactivate_and_activate(client: TestClient) -> None:
    deactivated = client.post(f"{URL}/{EXISTING}/deactivate").json()
    assert deactivated["isActive"] is False
    assert client.get(URL).json()["total"] == 0  # default filter is active
    assert client.get(URL, params={"status": "inactive"}).json()["total"] == 1
    assert client.post(f"{URL}/{EXISTING}/activate").json()["isActive"] is True


def test_unknown_machine_is_404(client: TestClient) -> None:
    assert client.get(f"{URL}/999").status_code == 404
    assert client.post(f"{URL}/999/deactivate").status_code == 404


def test_form_options_list_the_models_of_the_selected_brand(client: TestClient) -> None:
    options = client.get(f"{URL}/form-options", headers={"X-Principal-Id": str(HITACHI)}).json()
    assert [m["modelCode"] for m in options["models"]] == ["EX200"]


def test_view_only_user_cannot_change_machines(settings: Settings, db: Engine) -> None:
    with make_client(settings, db, {"core.machine.view"}) as client:
        assert client.get(URL).status_code == 200
        assert create(client).status_code == 403
        assert client.post(f"{URL}/{EXISTING}/deactivate").status_code == 403
        assert client.get(f"{URL}/form-options").status_code == 403
