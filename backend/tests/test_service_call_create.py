"""Logging a service call: route -> service -> repository -> SQL (SQLite)."""

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
    "core.company",
    "core.branch",
    "core.principal",
    "core.customer",
    "core.machine_model",
    "core.machine_unit",
    "core.customer_site",
    "core.employee",
    "core.lookup_type",
    "core.lookup_value",
    "core.number_series",
    "core.app_user",
    "core.audit_log",
    "hr.designation",
    "svc.service_call",
    "svc.call_status_log",
]

COMPANY, BRANCH, PRINCIPAL = 1, 1, 1
CUSTOMER_ID, MACHINE_ID, ENGINEER_ID, ACTOR_ID = 100, 200, 300, 1
CUSTOMER_NAME = "Blue Earth Movers"
CALL_SOURCE_ID, CALL_TYPE_BREAKDOWN, CALL_TYPE_PERIODIC = 11, 21, 22
URL = "/api/v1/svc/service-calls"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TRISHUL", legal_name="Trishul", trade_name="Trishul")
    insert_row(engine, "core.branch", id=BRANCH, company_id=COMPANY, code="BBSR", name="Bhubaneswar")
    insert_row(engine, "core.principal", id=PRINCIPAL, code="TATA_HITACHI", name="Tata Hitachi")
    insert_row(engine, "core.customer", id=CUSTOMER_ID, company_id=COMPANY, code="C100", name=CUSTOMER_NAME,
               customer_type="Company", primary_phone="9000000000")
    insert_row(engine, "core.customer", id=101, company_id=COMPANY, code="C101", name="Real Customer Ltd",
               customer_type="Company", primary_phone="9111111111")
    insert_row(engine, "core.machine_model", id=1, model_code="EX200", model_name="EX200", principal_id=PRINCIPAL)
    insert_row(engine, "core.machine_unit", id=MACHINE_ID, serial_number="SN-1", oem_registered_product_id="RP-1",
               model_id=1, principal_id=PRINCIPAL, customer_id=CUSTOMER_ID, status="Sold")
    insert_row(engine, "hr.designation", id=1, code="SERVICE_ENG", name="Service Engineer")
    insert_row(engine, "hr.designation", id=2, code="BACK_OFFICE", name="Back office")
    insert_row(engine, "core.employee", id=ENGINEER_ID, company_id=COMPANY, branch_id=BRANCH, employee_code="E300",
               first_name="Satyajit", last_name="Tung", designation_id=1,
               employee_type="Permanent", status="Active")
    # A non-engineer in the same branch: must NOT appear in the assign picker.
    insert_row(engine, "core.employee", id=301, company_id=COMPANY, branch_id=BRANCH, employee_code="E301",
               first_name="Office", last_name="Clerk", designation_id=2,
               employee_type="Permanent", status="Active")
    insert_row(engine, "core.lookup_type", id=1, code="CALL_SOURCE", name="Call Source", module="Service")
    insert_row(engine, "core.lookup_value", id=CALL_SOURCE_ID, lookup_type_id=1, code="PHONE",
               label="Phone", sort_order=1)
    insert_row(engine, "core.lookup_type", id=2, code="CALL_TYPE", name="Call Type", module="Service")
    insert_row(engine, "core.lookup_value", id=CALL_TYPE_BREAKDOWN, lookup_type_id=2, code="BREAKDOWN",
               label="Breakdown", sort_order=1)
    insert_row(engine, "core.lookup_value", id=CALL_TYPE_PERIODIC, lookup_type_id=2, code="PERIODIC_SERVICE",
               label="Periodic service", sort_order=2)
    insert_row(engine, "core.number_series", id=1, company_id=COMPANY, document_type="SERVICE_CALL",
               prefix="SC-", next_number=1, padding=4)
    insert_row(engine, "core.app_user", id=ACTOR_ID, username="back.office@trishul.co", cognito_sub="sub-bo")
    return engine


def make_client(settings: Settings, db: Engine, permissions: set[str], employee_id: int | None = 7) -> TestClient:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(id=ACTOR_ID, employee_id=employee_id, permissions=frozenset(permissions),
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
    with make_client(settings, db, {"svc.call.create", "svc.call.view", "svc.call.assign"}) as test_client:
        yield test_client


def if_match(item: dict[str, Any]) -> dict[str, str]:
    return {"If-Match": f'"{item["rowVersion"]}"'}


def create(client: TestClient, **changes: Any) -> httpx.Response:
    body = {
        "customerId": CUSTOMER_ID,
        "principalId": PRINCIPAL,
        "machineUnitId": MACHINE_ID,
        "callTypeLookupId": CALL_TYPE_BREAKDOWN,
        "callSourceLookupId": CALL_SOURCE_ID,
        "priority": "High",
        "complaintDescription": "Engine not starting, battery OK",
        "callerName": "Ramesh",
        "callerPhone": "9876543210",
        "isMachineDown": True,
    } | changes
    return client.post(URL, json=body)


def test_create_logs_a_call(client: TestClient) -> None:
    response = create(client)
    assert response.status_code == 201, response.text
    call = response.json()
    assert call["callNo"].startswith("SC-")
    assert call["customerName"] == CUSTOMER_NAME
    assert call["principalCode"] == "TATA_HITACHI"
    assert call["currentStatus"] == "Logged"
    assert call["priority"] == "High"
    assert call["isMachineDown"] is True
    assert (call["machineModel"], call["machineSerialNo"]) == ("EX200", "SN-1")
    assert call["assignedEngineerName"] is None  # essentials: not assigned at creation


def test_create_without_machine(client: TestClient) -> None:
    created = create(client, machineUnitId=None)
    assert created.status_code == 201, created.text
    assert created.json()["machineSerialNo"] is None


def test_unknown_references_are_rejected(client: TestClient) -> None:
    assert create(client, customerId=999).status_code == 400
    assert "customerId" in create(client, customerId=999).json()["errors"]
    assert "machineUnitId" in create(client, machineUnitId=999).json()["errors"]
    # A CALL_SOURCE value is not a valid call type, and vice-versa.
    assert "callTypeLookupId" in create(client, callTypeLookupId=CALL_SOURCE_ID).json()["errors"]
    assert "callSourceLookupId" in create(client, callSourceLookupId=CALL_TYPE_BREAKDOWN).json()["errors"]


def test_invalid_input_is_rejected(client: TestClient) -> None:
    assert create(client, callerPhone="nope").status_code == 422
    assert create(client, complaintDescription="").status_code == 422
    assert create(client, priority="Urgent").status_code == 422
    assert create(client, foo=True).status_code == 422  # unknown field


def test_get_call_detail(client: TestClient) -> None:
    call = create(client, callerName="Ramesh").json()
    detail = client.get(f"{URL}/{call['id']}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["callNo"] == call["callNo"]
    assert body["customerName"] == CUSTOMER_NAME
    assert (body["callerName"], body["callerPhone"]) == ("Ramesh", "9876543210")
    assert body["callType"] == "Breakdown" and body["callSource"] == "Phone"
    assert body["currentStatus"] == "Logged"
    assert body["machineSerialNo"] == "SN-1" and body["machineModel"] == "EX200"


def test_get_call_detail_unknown_is_404(client: TestClient) -> None:
    assert client.get(f"{URL}/999999").status_code == 404


# ------------------------------------------------------------------ status change + history

TEAM_LEAD = {"svc.call.view", "svc.call.create", "svc.call.assign"}
ENGINEER = {"svc.call.view.assigned", "svc.call.status.update"}


def change_status(client: TestClient, call: dict[str, Any], status: str, **body: Any) -> httpx.Response:
    return client.post(f"{URL}/{call['id']}/status", json={"status": status} | body, headers=if_match(call))


def history(client: TestClient, call_id: int) -> list[dict[str, Any]]:
    response = client.get(f"{URL}/{call_id}/status-history")
    assert response.status_code == 200, response.text
    rows: list[dict[str, Any]] = response.json()
    return rows


def assigned_call(client: TestClient) -> dict[str, Any]:
    """A call assigned to the engineer, with its fresh row version."""
    call = create(client).json()
    return client.patch(f"{URL}/{call['id']}", json={"engineerId": ENGINEER_ID}, headers=if_match(call)).json()


def test_new_call_starts_its_history(client: TestClient) -> None:
    call = create(client).json()
    rows = history(client, call["id"])
    assert [(r["fromStatus"], r["toStatus"]) for r in rows] == [(None, "Logged")]


def test_team_lead_changes_status_and_it_is_recorded(client: TestClient) -> None:
    call = create(client).json()
    detail = client.get(f"{URL}/{call['id']}").json()
    assert "Logged" not in detail["allowedStatuses"] and "In progress" in detail["allowedStatuses"]
    assert "Closed" not in detail["allowedStatuses"]  # needs svc.call.close

    changed = change_status(client, detail, "In progress", remarks="Started work")
    assert changed.status_code == 200, changed.text
    assert changed.json()["currentStatus"] == "In progress"
    rows = history(client, call["id"])
    assert [(r["fromStatus"], r["toStatus"]) for r in rows] == [("Logged", "In progress"), (None, "Logged")]
    assert rows[0]["remarks"] == "Started work"
    assert rows[0]["changedByName"] == "back.office@trishul.co"  # no linked employee -> username


def test_assigning_an_engineer_is_recorded(client: TestClient) -> None:
    call = create(client).json()
    client.patch(f"{URL}/{call['id']}", json={"engineerId": ENGINEER_ID}, headers=if_match(call))
    rows = history(client, call["id"])
    assert (rows[0]["fromStatus"], rows[0]["toStatus"]) == ("Logged", "Assigned")


def test_closing_needs_the_close_permission(settings: Settings, db: Engine, client: TestClient) -> None:
    call = create(client).json()
    detail = client.get(f"{URL}/{call['id']}").json()
    assert change_status(client, detail, "Closed").status_code == 403
    with make_client(settings, db, TEAM_LEAD | {"svc.call.close"}) as closer:
        allowed = closer.get(f"{URL}/{call['id']}").json()
        closed = change_status(closer, allowed, "Closed", remarks="Done")
        assert closed.status_code == 200, closed.text
        assert closed.json()["closedAt"] is not None


def test_reopen_only_after_a_call_is_finished(settings: Settings, db: Engine, client: TestClient) -> None:
    call = create(client).json()
    perms = TEAM_LEAD | {"svc.call.close", "svc.call.reopen"}
    with make_client(settings, db, perms) as lead:
        detail = lead.get(f"{URL}/{call['id']}").json()
        assert change_status(lead, detail, "Reopened").status_code == 403  # still open
        closed = change_status(lead, detail, "Closed").json()
        reopened = change_status(lead, closed, "Reopened")
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()["closedAt"] is None


def test_same_status_and_stale_version_are_rejected(client: TestClient) -> None:
    call = create(client).json()
    detail = client.get(f"{URL}/{call['id']}").json()
    assert change_status(client, detail, "Logged").status_code == 400  # already Logged
    stale = client.post(
        f"{URL}/{call['id']}/status", json={"status": "In progress"}, headers={"If-Match": '"AAAAAAAAAAA="'}
    )
    assert stale.status_code == 409
    assert client.post(f"{URL}/{call['id']}/status", json={"status": "In progress"}).status_code == 428


def test_engineer_updates_only_their_own_call(settings: Settings, db: Engine, client: TestClient) -> None:
    mine = assigned_call(client)
    not_mine = create(client).json()  # unassigned
    with make_client(settings, db, ENGINEER, employee_id=ENGINEER_ID) as engineer:
        detail = engineer.get(f"{URL}/{mine['id']}").json()
        assert "Trip started" in detail["allowedStatuses"]
        assert "Closed" not in detail["allowedStatuses"] and "Assigned" not in detail["allowedStatuses"]

        moved = change_status(engineer, detail, "Trip started", remarks="On the way")
        assert moved.status_code == 200, moved.text
        assert moved.json()["currentStatus"] == "Trip started"
        assert history(engineer, mine["id"])[0]["changedByName"] == "back.office@trishul.co"

        assert change_status(engineer, moved.json(), "Closed").status_code == 403  # not theirs to close
        assert engineer.get(f"{URL}/{not_mine['id']}").status_code == 404  # another call
        assert engineer.get(f"{URL}/{not_mine['id']}/status-history").status_code == 404
        assert change_status(engineer, not_mine, "In progress").status_code == 404


def test_status_history_unknown_call_is_404(client: TestClient) -> None:
    assert client.get(f"{URL}/999999/status-history").status_code == 404


def test_machine_options_search(client: TestClient) -> None:
    rows = client.get(f"{URL}/machine-options", params={"search": "SN"}).json()
    assert [(m["serialNumber"], m["modelName"]) for m in rows] == [("SN-1", "EX200")]
    assert client.get(f"{URL}/machine-options", params={"customerId": CUSTOMER_ID}).json()[0]["id"] == MACHINE_ID


def test_create_requires_permission(settings: Settings, db: Engine) -> None:
    with make_client(settings, db, {"svc.call.view"}) as viewer:
        assert create(viewer).status_code == 403


# ------------------------------------------------------------------ team-lead triage (assign + priority)


def test_assign_engineer_and_set_priority(client: TestClient) -> None:
    call = create(client, priority="Normal").json()
    url = f"{URL}/{call['id']}"
    assert client.patch(url, json={"engineerId": ENGINEER_ID}).status_code == 428  # If-Match required
    bad = client.patch(url, json={"engineerId": ENGINEER_ID}, headers={"If-Match": '"AAAAAAAAAAA="'})
    assert bad.status_code == 409

    updated = client.patch(
        url, json={"engineerId": ENGINEER_ID, "priority": "Critical"}, headers=if_match(call)
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["assignedEngineerName"] == "Satyajit Tung"
    assert body["priority"] == "Critical"
    assert body["currentStatus"] == "Assigned"  # Logged -> Assigned on assignment


def test_unassign_returns_status_to_logged(client: TestClient) -> None:
    call = create(client).json()
    url = f"{URL}/{call['id']}"
    assigned = client.patch(url, json={"engineerId": ENGINEER_ID}, headers=if_match(call)).json()
    cleared = client.patch(url, json={"engineerId": None}, headers=if_match(assigned))
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["assignedEngineerName"] is None
    assert cleared.json()["currentStatus"] == "Logged"


def test_triage_rejects_unknown_engineer(client: TestClient) -> None:
    call = create(client).json()
    rejected = client.patch(f"{URL}/{call['id']}", json={"engineerId": 999}, headers=if_match(call))
    assert rejected.status_code == 400
    assert "engineerId" in rejected.json()["errors"]


def test_link_customer(client: TestClient) -> None:
    call = create(client).json()  # starts on CUSTOMER_ID (Blue Earth Movers)
    linked = client.patch(f"{URL}/{call['id']}", json={"customerId": 101}, headers=if_match(call))
    assert linked.status_code == 200, linked.text
    assert linked.json()["customerName"] == "Real Customer Ltd"


def test_link_customer_rejects_unknown(client: TestClient) -> None:
    call = create(client).json()
    rejected = client.patch(f"{URL}/{call['id']}", json={"customerId": 999}, headers=if_match(call))
    assert rejected.status_code == 400
    assert "customerId" in rejected.json()["errors"]


def test_engineer_options_lists_only_service_engineers(client: TestClient) -> None:
    rows = client.get(f"{URL}/engineer-options").json()
    # Only the Service Engineer (E300), not the back-office clerk (E301).
    assert [(e["name"], e["employeeCode"]) for e in rows] == [("Satyajit Tung", "E300")]


def test_triage_requires_assign_permission(client: TestClient, settings: Settings, db: Engine) -> None:
    call = create(client).json()
    with make_client(settings, db, {"svc.call.view"}) as viewer:
        blocked = viewer.patch(f"{URL}/{call['id']}", json={"priority": "Low"}, headers=if_match(call))
        assert blocked.status_code == 403
