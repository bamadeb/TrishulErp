"""Logging a service call: route -> service -> repository -> SQL (SQLite)."""

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.common.errors import NotFound
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import CallAssignment, MachineUnit, ServiceCall, ServiceVisit
from trishul_api.main import create_app
from trishul_api.modules.trk import handlers

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
    "core.team",
    "core.team_member",
    "svc.service_call",
    "svc.call_status_log",
    "svc.call_assignment",
    "svc.service_visit",
    "hr.holiday",
    "hr.leave_type",
    "hr.leave_request",
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


def test_sla_due_time_comes_from_the_most_specific_sla_rule(client: TestClient, db: Engine) -> None:
    received = "2026-11-02T06:00:00Z"
    assert create(client, receivedAt=received).json()["slaDueAt"] is None  # no SLA rule: no due time
    insert_row(db, "svc.sla_rule", company_id=COMPANY, resolution_hours=48, clock_type="Calendar")
    insert_row(db, "svc.sla_rule", company_id=COMPANY, principal_id=PRINCIPAL, priority="High",
               resolution_hours=8, clock_type="Calendar")
    assert create(client, receivedAt=received, priority="High").json()["slaDueAt"] == "2026-11-02T14:00:00Z"
    assert create(client, receivedAt=received, priority="Low").json()["slaDueAt"] == "2026-11-04T06:00:00Z"


def test_machine_must_belong_to_the_selected_customer(client: TestClient) -> None:
    # MACHINE_ID is registered to CUSTOMER_ID, not to customer 101.
    response = create(client, customerId=101)
    assert response.status_code == 400
    assert response.json()["errors"]["machineUnitId"] == ["That machine is not registered to this customer."]
    assert create(client, customerId=101, machineUnitId=None).status_code == 201  # no machine is fine


def test_machine_of_another_brand_is_rejected(client: TestClient, db: Engine) -> None:
    insert_row(db, "core.principal", id=2, code="BYD", name="BYD")
    insert_row(db, "core.machine_model", id=2, model_code="E6", model_name="BYD E6", principal_id=2)
    insert_row(db, "core.machine_unit", id=201, serial_number="BYD-1", model_id=2, principal_id=2,
               customer_id=CUSTOMER_ID, status="Sold")
    assert "machineUnitId" in create(client, machineUnitId=201).json()["errors"]


def test_deactivated_machine_is_not_offered_but_old_calls_keep_it(client: TestClient, db: Engine) -> None:
    call = create(client).json()
    with Session(db) as s:
        s.execute(update(MachineUnit).where(MachineUnit.id == MACHINE_ID).values(is_active=False))
        s.commit()
    assert create(client).json()["errors"]["machineUnitId"] == [f"Unknown or inactive machine {MACHINE_ID}"]
    assert client.get(f"{URL}/machine-options", params={"customerId": CUSTOMER_ID}).json() == []
    detail = client.get(f"{URL}/{call['id']}").json()
    assert detail["machineSerialNo"] == "SN-1" and detail["machineIsActive"] is False


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
    assert body["machineModelCode"] == "EX200" and body["machineIsActive"] is True


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
    assigned: dict[str, Any] = client.patch(
        f"{URL}/{call['id']}", json={"engineerId": ENGINEER_ID}, headers=if_match(call)
    ).json()
    return assigned


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


def test_link_customer_and_their_machine_together(client: TestClient, db: Engine) -> None:
    call = create(client, machineUnitId=None).json()
    insert_row(db, "core.machine_unit", id=201, serial_number="SN-2", model_id=1, principal_id=PRINCIPAL,
               customer_id=101, status="Sold")
    url = f"{URL}/{call['id']}"
    linked = client.patch(url, json={"customerId": 101, "machineUnitId": 201}, headers=if_match(call))
    assert linked.status_code == 200, linked.text
    assert linked.json()["customerId"] == 101
    assert linked.json()["machineUnitId"] == 201
    assert linked.json()["machineSerialNo"] == "SN-2"


def test_link_machine_clears_the_linking_flag(client: TestClient, db: Engine) -> None:
    call = create(client, machineUnitId=None).json()
    with Session(db) as s:
        s.execute(update(ServiceCall).values(external_product_id="RP-9", needs_master_linking=True))
        s.commit()
    linked = client.patch(f"{URL}/{call['id']}", json={"machineUnitId": MACHINE_ID}, headers=if_match(call))
    assert linked.status_code == 200, linked.text
    with Session(db) as s:
        row = s.get(ServiceCall, call["id"])
        assert row is not None
        assert row.needs_master_linking is False and row.external_product_id is None


def test_link_machine_still_flags_an_unlinked_customer(client: TestClient, db: Engine) -> None:
    call = create(client).json()
    with Session(db) as s:
        s.execute(update(ServiceCall).values(external_account_name="Unknown Account", needs_master_linking=True))
        s.commit()
    cleared = client.patch(f"{URL}/{call['id']}", json={"machineUnitId": None}, headers=if_match(call))
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["machineUnitId"] is None
    with Session(db) as s:
        row = s.get(ServiceCall, call["id"])
        assert row is not None and row.needs_master_linking is True


def test_link_machine_rejects_another_customers_machine(client: TestClient) -> None:
    call = create(client, machineUnitId=None).json()
    url = f"{URL}/{call['id']}"
    rejected = client.patch(url, json={"customerId": 101, "machineUnitId": MACHINE_ID}, headers=if_match(call))
    assert rejected.status_code == 400
    assert "machineUnitId" in rejected.json()["errors"]
    assert client.get(url).json()["customerName"] == CUSTOMER_NAME  # nothing half-saved


def test_link_machine_rejects_unknown_or_other_brand(client: TestClient, db: Engine) -> None:
    insert_row(db, "core.principal", id=2, code="OTHER", name="Other brand")
    insert_row(db, "core.machine_unit", id=202, serial_number="SN-3", model_id=1, principal_id=2,
               customer_id=CUSTOMER_ID, status="Sold")
    call = create(client, machineUnitId=None).json()
    url = f"{URL}/{call['id']}"
    for machine_id in (999, 202):
        rejected = client.patch(url, json={"machineUnitId": machine_id}, headers=if_match(call))
        assert rejected.status_code == 400
        assert "machineUnitId" in rejected.json()["errors"]


def test_keeping_the_current_machine_is_not_rechecked(client: TestClient, db: Engine) -> None:
    """A BYD call can hold a machine with no owner yet; saving the customer must not reject it."""
    call = create(client).json()
    with Session(db) as s:
        s.execute(update(MachineUnit).values(customer_id=None))
        s.commit()
    body = {"customerId": 101, "machineUnitId": MACHINE_ID}
    kept = client.patch(f"{URL}/{call['id']}", json=body, headers=if_match(call))
    assert kept.status_code == 200, kept.text
    assert kept.json()["machineUnitId"] == MACHINE_ID


def test_link_machine_follows_its_asc(client: TestClient, db: Engine) -> None:
    call = create(client, machineUnitId=None).json()
    assert call["isAscPriority"] is False
    insert_row(db, "svc.service_contract", id=1, company_id=COMPANY, contract_no="ASC-1", customer_id=CUSTOMER_ID,
               contract_type="ASC", start_date=date(2020, 1, 1), end_date=date(2099, 1, 1), status="Active")
    insert_row(db, "svc.contract_coverage", id=1, service_contract_id=1, machine_unit_id=MACHINE_ID)
    url = f"{URL}/{call['id']}"
    linked = client.patch(url, json={"machineUnitId": MACHINE_ID}, headers=if_match(call)).json()
    assert linked["isAscPriority"] is True and linked["coverageType"] == "Contract"
    cleared = client.patch(url, json={"machineUnitId": None}, headers=if_match(linked)).json()
    assert cleared["isAscPriority"] is False and cleared["coverageType"] is None


TODAY = date.today().isoformat()
UNASSIGNED_URL = f"{URL}/unassigned"
WORKLOAD_URL = f"{URL}/engineer-workload"


def add_engineer(db: Engine, employee_id: int, first_name: str) -> None:
    insert_row(db, "core.employee", id=employee_id, company_id=COMPANY, branch_id=BRANCH,
               employee_code=f"E{employee_id}", first_name=first_name, designation_id=1,
               employee_type="Permanent", status="Active")


def workload(client: TestClient, **params: Any) -> dict[str, dict[str, Any]]:
    rows = client.get(WORKLOAD_URL, params={"onDate": TODAY} | params).json()
    return {row["name"]: row for row in rows}


def test_unassigned_lists_only_calls_without_an_engineer_most_urgent_first(client: TestClient) -> None:
    low = create(client, priority="Low").json()
    critical = create(client, priority="Critical").json()
    taken = create(client).json()
    client.patch(f"{URL}/{taken['id']}", json={"engineerId": ENGINEER_ID}, headers=if_match(taken))
    response = client.get(UNASSIGNED_URL)
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["items"]] == [critical["id"], low["id"]]


@pytest.mark.parametrize(
    ("warranty_end", "under_asc", "machine", "cover"),
    [
        (date(2099, 1, 1), False, True, "Warranty"),
        (date(2020, 1, 1), True, True, "ASC"),
        (date(2099, 1, 1), True, True, "ASC + Warranty"),
        (date(2020, 1, 1), False, True, "Not covered"),
        (None, False, False, "Unknown"),
    ],
)
def test_unassigned_shows_the_cover(
    client: TestClient, db: Engine, warranty_end: date | None, under_asc: bool, machine: bool, cover: str
) -> None:
    with Session(db) as s:
        s.execute(update(MachineUnit).values(warranty_end_date=warranty_end))
        s.commit()
    if under_asc:
        insert_row(db, "svc.service_contract", id=1, company_id=COMPANY, contract_no="ASC-1",
                   customer_id=CUSTOMER_ID, contract_type="ASC", start_date=date(2020, 1, 1),
                   end_date=date(2099, 1, 1), status="Active")
        insert_row(db, "svc.contract_coverage", id=1, service_contract_id=1, machine_unit_id=MACHINE_ID)
    create(client, machineUnitId=MACHINE_ID if machine else None)
    assert client.get(UNASSIGNED_URL).json()["items"][0]["cover"] == cover


def test_unassigned_needs_the_assign_permission(settings: Settings, db: Engine) -> None:
    with make_client(settings, db, {"svc.call.view"}) as viewer:
        assert viewer.get(UNASSIGNED_URL).status_code == 403
        assert viewer.get(WORKLOAD_URL, params={"onDate": TODAY}).status_code == 403


def test_assign_for_a_date_plans_a_visit_and_counts_on_that_day_only(client: TestClient, db: Engine) -> None:
    add_engineer(db, 310, "Free")
    call = create(client).json()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assigned = client.patch(f"{URL}/{call['id']}", json={"engineerId": ENGINEER_ID, "visitDate": tomorrow},
                            headers=if_match(call))
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["currentStatus"] == "Assigned"
    assert client.get(UNASSIGNED_URL).json()["items"] == []

    on_the_day = workload(client, onDate=tomorrow)
    assert on_the_day["Satyajit Tung"]["callsOnDate"] == 1
    assert on_the_day["Satyajit Tung"]["openCalls"] == 1
    assert on_the_day["Free"]["callsOnDate"] == 0
    assert workload(client)["Satyajit Tung"]["callsOnDate"] == 0  # today: not that engineer's busy day
    assert list(on_the_day) == ["Free", "Satyajit Tung"]  # the free engineer comes first


def test_a_planned_visit_becomes_the_engineers_trip(
    client: TestClient, db: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    call = create(client).json()
    client.patch(f"{URL}/{call['id']}", json={"engineerId": ENGINEER_ID, "visitDate": TODAY}, headers=if_match(call))
    start_trip(db, call["id"], ENGINEER_ID, monkeypatch)
    with Session(db) as s:
        visits = list(s.scalars(select(ServiceVisit)))
    assert [(v.visit_no, v.status, v.planned_date) for v in visits] == [(1, "On the way", date.today())]


def test_reassigning_drops_the_old_engineers_day(client: TestClient, db: Engine) -> None:
    add_engineer(db, 310, "Second")
    call = create(client).json()
    url = f"{URL}/{call['id']}"
    first = client.patch(url, json={"engineerId": ENGINEER_ID, "visitDate": TODAY}, headers=if_match(call)).json()
    client.patch(url, json={"engineerId": 310, "visitDate": TODAY}, headers=if_match(first))
    day = workload(client)
    assert day["Satyajit Tung"]["callsOnDate"] == 0
    assert day["Second"]["callsOnDate"] == 1


def test_replanning_moves_the_same_visit(client: TestClient, db: Engine) -> None:
    call = create(client).json()
    url = f"{URL}/{call['id']}"
    first = client.patch(url, json={"engineerId": ENGINEER_ID, "visitDate": TODAY}, headers=if_match(call)).json()
    tomorrow = date.today() + timedelta(days=1)
    client.patch(url, json={"visitDate": tomorrow.isoformat()}, headers=if_match(first))
    with Session(db) as s:
        assert [v.planned_date for v in s.scalars(select(ServiceVisit))] == [tomorrow]


def test_visit_date_rules(client: TestClient, db: Engine) -> None:
    call = create(client).json()
    url = f"{URL}/{call['id']}"
    no_lead = client.patch(url, json={"visitDate": TODAY}, headers=if_match(call))
    assert no_lead.status_code == 400 and "engineerId" in no_lead.json()["errors"]
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    past = client.patch(url, json={"engineerId": ENGINEER_ID, "visitDate": yesterday}, headers=if_match(call))
    assert past.status_code == 400 and "visitDate" in past.json()["errors"]
    assert client.get(url).json()["assignedEngineerName"] is None  # nothing half-saved


def add_leave(db: Engine, *, half_day: bool = False, status: str = "Approved") -> None:
    if not half_day and status == "Approved":
        insert_row(db, "hr.leave_type", id=1, code="CL", name="Casual leave")
    today = date.today()
    insert_row(db, "hr.leave_request", employee_id=ENGINEER_ID, leave_type_id=1, from_date=today, to_date=today,
               is_half_day=half_day, days=1, status=status)


def test_engineer_on_leave_is_last_and_cannot_be_assigned(client: TestClient, db: Engine) -> None:
    add_engineer(db, 310, "Free")
    add_leave(db)
    assert workload(client)["Satyajit Tung"]["availability"] == "On leave"
    assert list(workload(client)) == ["Free", "Satyajit Tung"]
    call = create(client).json()
    rejected = client.patch(f"{URL}/{call['id']}", json={"engineerId": ENGINEER_ID, "visitDate": TODAY},
                            headers=if_match(call))
    assert rejected.status_code == 400 and "visitDate" in rejected.json()["errors"]


def test_half_day_leave_and_holiday_only_warn(client: TestClient, db: Engine) -> None:
    add_engineer(db, 310, "Free")
    insert_row(db, "hr.leave_type", id=1, code="CL", name="Casual leave")
    add_leave(db, half_day=True)
    insert_row(db, "hr.holiday", branch_id=None, holiday_date=date.today(), name="Diwali", holiday_type="Festival")
    day = workload(client)
    assert day["Satyajit Tung"]["availability"] == "Half-day leave"
    assert day["Free"]["availability"] == "Holiday"
    call = create(client).json()
    allowed = client.patch(f"{URL}/{call['id']}", json={"engineerId": ENGINEER_ID, "visitDate": TODAY},
                           headers=if_match(call))
    assert allowed.status_code == 200, allowed.text


def test_workload_distance_and_order_for_a_call(client: TestClient, db: Engine) -> None:
    add_engineer(db, 310, "Near")
    insert_row(db, "core.customer_site", id=1, customer_id=CUSTOMER_ID, site_name="Mine", address="Angul",
               latitude=20.84, longitude=85.10)
    call = create(client).json()
    with Session(db) as s:
        s.execute(update(ServiceCall).values(customer_site_id=1))
        s.commit()
    for visit_id, engineer, lat in ((1, ENGINEER_ID, 22.0), (2, 310, 20.85)):
        insert_row(db, "svc.service_visit", id=visit_id, service_call_id=call["id"], visit_no=visit_id,
                   visit_purpose="Inspection", engineer_employee_id=engineer, status="Completed",
                   site_latitude=lat, site_longitude=85.10, planned_date=date(2020, 1, 1))
    day = workload(client, callId=call["id"])
    assert list(day) == ["Near", "Satyajit Tung"]
    assert day["Near"]["distanceKm"] == 1.1
    assert day["Near"]["sameBranch"] is True
    assert workload(client)["Near"]["distanceKm"] is None


def test_workload_rejects_an_unknown_call(client: TestClient) -> None:
    assert client.get(WORKLOAD_URL, params={"onDate": TODAY, "callId": 999}).status_code == 404


def test_engineer_options_lists_only_service_engineers(client: TestClient) -> None:
    rows = client.get(f"{URL}/engineer-options").json()
    # Only the Service Engineer (E300), not the back-office clerk (E301).
    assert [(e["name"], e["employeeCode"]) for e in rows] == [("Satyajit Tung", "E300")]


def test_triage_requires_assign_permission(client: TestClient, settings: Settings, db: Engine) -> None:
    call = create(client).json()
    with make_client(settings, db, {"svc.call.view"}) as viewer:
        blocked = viewer.patch(f"{URL}/{call['id']}", json={"priority": "Low"}, headers=if_match(call))
        assert blocked.status_code == 403


LEAD_ID, OTHER_ENGINEER_ID = 400, 302


@pytest.fixture
def team_calls(client: TestClient, db: Engine) -> dict[str, int]:
    """A team (lead 400, engineer 300); engineer 302 is in no team. One call each, plus an unassigned one."""
    insert_row(db, "core.employee", id=OTHER_ENGINEER_ID, company_id=COMPANY, branch_id=BRANCH,
               employee_code="E302", first_name="Other", last_name="Engineer", designation_id=1,
               employee_type="Permanent", status="Active")
    insert_row(db, "core.employee", id=LEAD_ID, company_id=COMPANY, branch_id=BRANCH, employee_code="E400",
               first_name="Team", last_name="Lead", designation_id=2, employee_type="Permanent", status="Active")
    insert_row(db, "core.team", id=1, branch_id=BRANCH, name="Service A", team_type="Service",
               team_lead_employee_id=LEAD_ID)
    insert_row(db, "core.team_member", team_id=1, employee_id=ENGINEER_ID, from_date=date(2026, 1, 1))
    # Left the team: no longer counts.
    insert_row(db, "core.team_member", team_id=1, employee_id=OTHER_ENGINEER_ID, from_date=date(2026, 1, 1),
               to_date=date(2026, 2, 1))
    calls = {}
    for key, engineer in (("team", ENGINEER_ID), ("other", OTHER_ENGINEER_ID), ("unassigned", None)):
        call = create(client).json()
        if engineer is not None:
            client.patch(f"{URL}/{call['id']}", json={"engineerId": engineer}, headers=if_match(call))
        calls[key] = call["id"]
    return calls


def listed(client: TestClient) -> set[int]:
    response = client.get(URL)
    assert response.status_code == 200, response.text
    return {row["id"] for row in response.json()["items"]}


def test_team_lead_sees_their_teams_calls_and_unassigned_ones(
    settings: Settings, db: Engine, team_calls: dict[str, int]
) -> None:
    with make_client(settings, db, {"svc.call.view.team", "svc.call.assign"}, employee_id=LEAD_ID) as lead:
        assert listed(lead) == {team_calls["team"], team_calls["unassigned"]}
        assert lead.get(f"{URL}/{team_calls['team']}").status_code == 200
        assert lead.get(f"{URL}/{team_calls['other']}").status_code == 404
        assert lead.get(f"{URL}/{team_calls['other']}/status-history").status_code == 404
        # The assign picker offers only the team's engineers.
        assert [e["employeeCode"] for e in lead.get(f"{URL}/engineer-options").json()] == ["E300"]


def test_team_lead_assigns_only_within_their_team(
    settings: Settings, db: Engine, team_calls: dict[str, int]
) -> None:
    with make_client(settings, db, {"svc.call.view.team", "svc.call.assign"}, employee_id=LEAD_ID) as lead:
        call = lead.get(f"{URL}/{team_calls['unassigned']}").json()
        outside = lead.patch(f"{URL}/{call['id']}", json={"engineerId": OTHER_ENGINEER_ID}, headers=if_match(call))
        assert outside.status_code == 400
        assert "engineerId" in outside.json()["errors"]
        inside = lead.patch(f"{URL}/{call['id']}", json={"engineerId": ENGINEER_ID}, headers=if_match(call))
        assert inside.status_code == 200, inside.text


def test_engineer_sees_only_calls_assigned_to_them(
    settings: Settings, db: Engine, team_calls: dict[str, int]
) -> None:
    with make_client(settings, db, {"svc.call.view.assigned"}, employee_id=ENGINEER_ID) as engineer:
        assert listed(engineer) == {team_calls["team"]}
        assert engineer.get(f"{URL}/{team_calls['unassigned']}").status_code == 404


def test_office_sees_every_call(client: TestClient, team_calls: dict[str, int]) -> None:
    assert listed(client) == set(team_calls.values())


# ------------------------------------------------------------------ more than one engineer on a call


def set_team(client: TestClient, call_id: int, lead: int | None, support: list[int]) -> httpx.Response:
    call = client.get(f"{URL}/{call_id}").json()
    return client.patch(
        f"{URL}/{call_id}", json={"engineerId": lead, "supportEngineerIds": support}, headers=if_match(call)
    )


def assignment_rows(db: Engine, call_id: int) -> list[tuple[int, str, bool]]:
    with Session(db) as session:
        rows = session.scalars(select(CallAssignment).where(CallAssignment.service_call_id == call_id))
        return sorted((r.engineer_employee_id, r.assignment_type, r.is_current) for r in rows)


def test_call_takes_a_lead_and_support_engineers(client: TestClient, team_calls: dict[str, int]) -> None:
    call_id = team_calls["unassigned"]
    updated = set_team(client, call_id, ENGINEER_ID, [OTHER_ENGINEER_ID])
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["assignedEngineerId"] == ENGINEER_ID and body["assignedEngineerName"] == "Satyajit Tung"
    assert body["supportEngineers"] == [{"id": OTHER_ENGINEER_ID, "name": "Other Engineer"}]
    assert body["currentStatus"] == "Assigned"

    row = next(r for r in client.get(URL).json()["items"] if r["id"] == call_id)
    assert row["supportEngineers"] == body["supportEngineers"]
    assert client.get(f"{URL}/{call_id}").json()["supportEngineers"] == body["supportEngineers"]


def test_changing_the_team_keeps_the_history(
    client: TestClient, db: Engine, team_calls: dict[str, int]
) -> None:
    call_id = team_calls["unassigned"]
    set_team(client, call_id, ENGINEER_ID, [OTHER_ENGINEER_ID])
    # The two swap roles, which is two closed rows and two new ones.
    swapped = set_team(client, call_id, OTHER_ENGINEER_ID, [ENGINEER_ID])
    assert swapped.status_code == 200, swapped.text
    assert swapped.json()["assignedEngineerId"] == OTHER_ENGINEER_ID
    assert assignment_rows(db, call_id) == [
        (ENGINEER_ID, "Primary", False),
        (ENGINEER_ID, "Support", True),
        (OTHER_ENGINEER_ID, "Primary", True),
        (OTHER_ENGINEER_ID, "Support", False),
    ]


def test_changing_only_the_lead_keeps_the_support_engineers(
    client: TestClient, team_calls: dict[str, int]
) -> None:
    call_id = team_calls["unassigned"]
    call = set_team(client, call_id, ENGINEER_ID, [OTHER_ENGINEER_ID]).json()
    # An older screen sending only engineerId; the new lead also stops being support.
    moved = client.patch(f"{URL}/{call_id}", json={"engineerId": OTHER_ENGINEER_ID}, headers=if_match(call))
    assert moved.status_code == 200, moved.text
    assert moved.json()["assignedEngineerId"] == OTHER_ENGINEER_ID and moved.json()["supportEngineers"] == []


def test_the_lead_is_not_also_support(client: TestClient, team_calls: dict[str, int]) -> None:
    body = set_team(client, team_calls["unassigned"], ENGINEER_ID, [ENGINEER_ID, OTHER_ENGINEER_ID]).json()
    assert [e["id"] for e in body["supportEngineers"]] == [OTHER_ENGINEER_ID]


def test_unassigning_clears_everyone(client: TestClient, db: Engine, team_calls: dict[str, int]) -> None:
    call_id = team_calls["unassigned"]
    call = set_team(client, call_id, ENGINEER_ID, [OTHER_ENGINEER_ID]).json()
    cleared = client.patch(f"{URL}/{call_id}", json={"engineerId": None}, headers=if_match(call))
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["supportEngineers"] == [] and cleared.json()["currentStatus"] == "Logged"
    assert not any(current for _, _, current in assignment_rows(db, call_id))


def test_support_needs_a_lead(client: TestClient, team_calls: dict[str, int]) -> None:
    rejected = set_team(client, team_calls["unassigned"], None, [ENGINEER_ID])
    assert rejected.status_code == 400 and "engineerId" in rejected.json()["errors"]


def test_unknown_support_engineer_is_rejected(client: TestClient, team_calls: dict[str, int]) -> None:
    rejected = set_team(client, team_calls["unassigned"], ENGINEER_ID, [999])
    assert rejected.status_code == 400 and "supportEngineerIds" in rejected.json()["errors"]


def test_support_engineer_has_the_call_until_removed(
    client: TestClient, settings: Settings, db: Engine, team_calls: dict[str, int]
) -> None:
    call_id = team_calls["other"]
    set_team(client, call_id, OTHER_ENGINEER_ID, [ENGINEER_ID])
    permissions = {"svc.call.view.assigned", "svc.call.status.update"}
    with make_client(settings, db, permissions, employee_id=ENGINEER_ID) as engineer:
        assert listed(engineer) == {team_calls["team"], call_id}
        mine = engineer.get(f"{URL}/assigned-to-me").json()["items"]
        assert {row["id"] for row in mine} == {team_calls["team"], call_id}
        call = engineer.get(f"{URL}/{call_id}").json()
        assert "Customer contacted" in call["allowedStatuses"]
        moved = engineer.post(
            f"{URL}/{call_id}/status", json={"status": "Customer contacted"}, headers=if_match(call)
        )
        assert moved.status_code == 200, moved.text

        set_team(client, call_id, OTHER_ENGINEER_ID, [])
        assert engineer.get(f"{URL}/{call_id}").status_code == 404
        assert listed(engineer) == {team_calls["team"]}


def test_team_lead_sees_a_call_their_engineer_supports(
    client: TestClient, settings: Settings, db: Engine, team_calls: dict[str, int]
) -> None:
    set_team(client, team_calls["other"], OTHER_ENGINEER_ID, [ENGINEER_ID])
    with make_client(settings, db, {"svc.call.view.team", "svc.call.assign"}, employee_id=LEAD_ID) as lead:
        assert team_calls["other"] in listed(lead)
        # The outside lead was put there by the office; the team lead may leave them on but can't add others.
        kept = set_team(lead, team_calls["other"], OTHER_ENGINEER_ID, [ENGINEER_ID])
        assert kept.status_code == 200, kept.text
        outside = set_team(lead, team_calls["team"], ENGINEER_ID, [OTHER_ENGINEER_ID])
        assert outside.status_code == 400 and "supportEngineerIds" in outside.json()["errors"]


def start_trip(db: Engine, call_id: int, employee_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(handlers, "_get_or_create_activity", lambda *_, **__: None)
    with Session(db) as session:
        handlers.ServiceActivityHandler().resolve(session, employee_id, call_id, ACTOR_ID, 20.0, 85.0, datetime.now())
        session.commit()


def call_status(db: Engine, call_id: int) -> str:
    with Session(db) as session:
        call = session.get(ServiceCall, call_id)
        assert call is not None
        return call.current_status


def test_support_engineer_can_start_a_trip_without_undoing_progress(
    client: TestClient, db: Engine, team_calls: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    call_id = team_calls["team"]
    set_team(client, call_id, ENGINEER_ID, [OTHER_ENGINEER_ID])
    start_trip(db, call_id, OTHER_ENGINEER_ID, monkeypatch)
    assert call_status(db, call_id) == "Trip started"

    with Session(db) as session:
        session.execute(update(ServiceCall).where(ServiceCall.id == call_id).values(current_status="In progress"))
        session.commit()
    start_trip(db, call_id, ENGINEER_ID, monkeypatch)  # the second engineer sets off later
    assert call_status(db, call_id) == "In progress"

    with pytest.raises(NotFound):
        start_trip(db, call_id, LEAD_ID, monkeypatch)  # not on the call
