"""Alert module: the six service alert types, duplicate prevention, re-raise policy, automatic resolution,
recipients (with brand/branch access), the Alert Master API, Test Rule, and the in-app inbox (SQLite)."""

import json
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import Alert, AlertRecipient, SlaEvent
from trishul_api.main import create_app
from trishul_api.modules.alerts.engine import AlertEngine, utcnow

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "core.principal",
    "core.customer",
    "core.customer_site",
    "core.employee",
    "core.app_user",
    "core.role",
    "core.user_role",
    "core.user_principal_access",
    "core.machine_model",
    "core.machine_unit",
    "core.lookup_type",
    "core.lookup_value",
    "core.audit_log",
    "svc.service_call",
    "svc.call_status_log",
    "svc.call_assignment",
    "svc.sla_rule",
    "svc.sla_event",
    "svc.service_contract",
    "core.alert_rule",
    "core.alert_rule_recipient",
    "core.alert",
    "core.alert_recipient",
]

NOW = datetime(2026, 11, 2, 12, 0)
COMPANY, BBSR, CTC, HITACHI, BYD = 1, 1, 2, 1, 2
TEAM_LEAD, ADMIN, ENGINEER_ROLE = 1, 2, 3
TL_BBSR, TL_CTC, ENGINEER_USER, LOGGER, ADMIN_USER, SYSTEM = 10, 11, 12, 13, 14, 99
ENGINEER_EMPLOYEE = 300
CUSTOMER = 100
URL = "/api/v1/core"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TRISHUL", legal_name="Trishul", trade_name="Trishul")
    insert_row(engine, "core.branch", id=BBSR, company_id=COMPANY, code="BBSR", name="Bhubaneswar")
    insert_row(engine, "core.branch", id=CTC, company_id=COMPANY, code="CTC", name="Cuttack")
    insert_row(engine, "core.principal", id=HITACHI, code="TATA_HITACHI", name="Tata Hitachi")
    insert_row(engine, "core.principal", id=BYD, code="BYD", name="BYD")
    insert_row(
        engine,
        "core.customer",
        id=CUSTOMER,
        company_id=COMPANY,
        code="C100",
        name="Blue Earth Movers",
        customer_type="Company",
        primary_phone="9000000000",
    )
    for role_id, code, name in (
        (TEAM_LEAD, "TEAM_LEAD", "Team Lead"),
        (ADMIN, "ADMIN", "Administrator"),
        (ENGINEER_ROLE, "SERVICE_ENGINEER", "Service Engineer"),
    ):
        insert_row(engine, "core.role", id=role_id, code=code, name=name)
    insert_row(
        engine,
        "core.employee",
        id=ENGINEER_EMPLOYEE,
        company_id=COMPANY,
        branch_id=BBSR,
        employee_code="E300",
        first_name="Satyajit",
        last_name="Tung",
    )
    users: tuple[tuple[int, str, int | None, bool, int | None, int | None], ...] = (
        (TL_BBSR, "tl.bbsr", None, False, TEAM_LEAD, BBSR),
        (TL_CTC, "tl.ctc", None, False, TEAM_LEAD, CTC),
        (ENGINEER_USER, "engineer", ENGINEER_EMPLOYEE, False, ENGINEER_ROLE, BBSR),
        (LOGGER, "back.office", None, False, None, None),
        (ADMIN_USER, "admin", None, False, ADMIN, None),
        (SYSTEM, "system", None, True, ADMIN, None),
    )
    for user_id, username, employee_id, locked, user_role_id, branch_id in users:
        insert_row(
            engine,
            "core.app_user",
            id=user_id,
            username=username,
            cognito_sub=f"sub-{username}",
            employee_id=employee_id,
            is_locked=locked,
        )
        if user_role_id is not None:
            insert_row(engine, "core.user_role", app_user_id=user_id, role_id=user_role_id, branch_id=branch_id)
        insert_row(engine, "core.user_principal_access", app_user_id=user_id, principal_id=HITACHI)
    insert_row(engine, "core.machine_model", id=1, model_code="EX200", model_name="EX 200LC", principal_id=HITACHI)
    return engine


def add_call(db: Engine, call_id: int, **values: Any) -> int:
    row = {
        "id": call_id,
        "company_id": COMPANY,
        "branch_id": BBSR,
        "principal_id": HITACHI,
        "call_no": f"SC-{call_id:04d}",
        "customer_id": CUSTOMER,
        "priority": "Normal",
        "current_status": "Logged",
        "received_at": NOW - timedelta(hours=1),
        "received_by_user_id": LOGGER,
        "complaint_description": "Engine not starting",
        "caller_phone": "9876543210",
        "is_machine_down": False,
    } | values
    return insert_row(db, "svc.service_call", **row)


def add_rule(
    db: Engine, alert_type: str, parameters: dict[str, Any], recipients: list[dict[str, Any]], **values: Any
) -> int:
    rule_id = insert_row(
        db,
        "core.alert_rule",
        company_id=COMPANY,
        code=values.pop("code", alert_type),
        name=values.pop("name", alert_type.title()),
        alert_type=alert_type,
        severity=values.pop("severity", "Warning"),
        parameters=json.dumps(parameters),
        reraise_policy=values.pop("reraise_policy", "After resolution"),
        cooldown_minutes=values.pop("cooldown_minutes", 0),
        is_active=values.pop("is_active", True),
        **values,
    )
    for recipient in recipients:
        insert_row(db, "core.alert_rule_recipient", alert_rule_id=rule_id, channel="In-app", **recipient)
    return rule_id


TEAM_LEADS = {"recipient_type": "Role", "role_id": TEAM_LEAD}
ASSIGNED_ENGINEER = {"recipient_type": "Assigned engineer"}


def run(db: Engine, now: datetime = NOW) -> tuple[int, int]:
    with Session(db) as session:
        summary = AlertEngine(session, now=now).run_scheduled()
        assert not [r for r in summary.rules if r.error], [r.error for r in summary.rules]
        return summary.raised, summary.resolved


def alerts(db: Engine) -> list[Alert]:
    with Session(db) as session:
        return list(session.scalars(select(Alert).order_by(Alert.id)))


def recipients_of(db: Engine, alert_id: int) -> set[int]:
    with Session(db) as session:
        return set(session.scalars(select(AlertRecipient.app_user_id).where(AlertRecipient.alert_id == alert_id)))


def update_call(db: Engine, call_id: int, **values: Any) -> None:
    from trishul_api.db.models import ServiceCall

    with Session(db) as session:
        call = session.get(ServiceCall, call_id)
        assert call is not None
        for key, value in values.items():
            setattr(call, key, value)
        session.commit()


# ------------------------------------------------------------------ unassigned + duplicate prevention


def test_unassigned_call_alerts_once_and_only_the_branch_team_lead(db: Engine) -> None:
    add_rule(db, "SVC_CALL_UNASSIGNED", {"afterMinutes": 30}, [TEAM_LEADS])
    add_call(db, 1, received_at=NOW - timedelta(minutes=45))
    add_call(db, 2, received_at=NOW - timedelta(minutes=10))  # too recent

    assert run(db) == (1, 0)
    (alert,) = alerts(db)
    assert alert.dedupe_key == "svc.service_call:1" and alert.status == "Open"
    assert "SC-0001" in alert.title and "45 min" in alert.message
    assert recipients_of(db, alert.id) == {TL_BBSR}  # not the Cuttack team lead, never 'system'

    assert run(db, NOW + timedelta(minutes=5)) == (0, 0)  # still open: no duplicate
    assert len(alerts(db)) == 1


def test_support_engineers_receive_the_assigned_engineer_alert(db: Engine) -> None:
    insert_row(
        db, "svc.sla_rule", company_id=COMPANY, resolution_hours=24, alert_before_minutes=120, clock_type="Calendar"
    )
    add_rule(db, "SVC_SLA_DUE", {"stages": ["Due soon"]}, [ASSIGNED_ENGINEER])
    insert_row(db, "core.employee", id=301, company_id=COMPANY, branch_id=BBSR, employee_code="E301", first_name="Lead")
    insert_row(db, "core.app_user", id=15, username="lead", cognito_sub="sub-lead", employee_id=301)
    add_call(db, 1, sla_due_at=NOW + timedelta(hours=1), assigned_engineer_id=301, current_status="In progress")
    insert_row(db, "svc.call_assignment", service_call_id=1, engineer_employee_id=ENGINEER_EMPLOYEE,
               assignment_type="Support", assigned_by_user_id=TL_BBSR, is_current=True)
    # Taken off the call: no longer told about it.
    insert_row(db, "svc.call_assignment", service_call_id=1, engineer_employee_id=301,
               assignment_type="Support", assigned_by_user_id=TL_BBSR, is_current=False)

    assert run(db) == (1, 0)
    (alert,) = alerts(db)
    assert recipients_of(db, alert.id) == {15, ENGINEER_USER}


def test_condition_clearing_resolves_and_after_resolution_raises_again(db: Engine) -> None:
    add_rule(db, "SVC_CALL_UNASSIGNED", {"afterMinutes": 30}, [TEAM_LEADS], cooldown_minutes=60)
    add_call(db, 1, received_at=NOW - timedelta(hours=2))
    run(db)
    update_call(db, 1, assigned_engineer_id=ENGINEER_EMPLOYEE, current_status="Assigned")
    assert run(db, NOW + timedelta(minutes=1)) == (0, 1)
    assert alerts(db)[0].status == "Resolved" and alerts(db)[0].resolution_note == "Condition cleared"

    update_call(db, 1, assigned_engineer_id=None, current_status="Logged")
    assert run(db, NOW + timedelta(minutes=30)) == (0, 0)  # within the 60-minute cooldown
    assert run(db, NOW + timedelta(minutes=90)) == (1, 0)  # cooldown over: raised again
    assert [a.status for a in alerts(db)] == ["Resolved", "Open"]


def test_never_policy_does_not_raise_again_for_the_same_record(db: Engine) -> None:
    add_rule(db, "SVC_CALL_UNASSIGNED", {"afterMinutes": 30}, [TEAM_LEADS], reraise_policy="Never")
    add_call(db, 1, received_at=NOW - timedelta(hours=2))
    run(db)
    update_call(db, 1, assigned_engineer_id=ENGINEER_EMPLOYEE)
    run(db, NOW + timedelta(minutes=1))
    update_call(db, 1, assigned_engineer_id=None)
    assert run(db, NOW + timedelta(days=1)) == (0, 0)


def test_rule_filters_brand_and_priority_and_inactive_rules_do_nothing(db: Engine) -> None:
    add_rule(db, "SVC_CALL_UNASSIGNED", {"afterMinutes": 30, "priorities": ["Critical"]}, [TEAM_LEADS], code="CRIT")
    add_rule(db, "SVC_CALL_UNASSIGNED", {"afterMinutes": 30}, [TEAM_LEADS], code="BYD", principal_id=BYD)
    add_rule(db, "SVC_CALL_UNASSIGNED", {"afterMinutes": 30}, [TEAM_LEADS], code="OFF", is_active=False)
    add_call(db, 1, received_at=NOW - timedelta(hours=2), priority="Normal")
    add_call(db, 2, received_at=NOW - timedelta(hours=2), priority="Critical")
    run(db)
    assert [(a.dedupe_key) for a in alerts(db)] == ["svc.service_call:2"]


# ------------------------------------------------------------------ SLA (from svc.sla_rule)


def test_sla_due_soon_then_breached_with_sla_events(db: Engine) -> None:
    insert_row(
        db, "svc.sla_rule", company_id=COMPANY, resolution_hours=24, alert_before_minutes=120, clock_type="Calendar"
    )
    add_rule(db, "SVC_SLA_DUE", {"stages": ["Due soon", "Breached"]}, [TEAM_LEADS, ASSIGNED_ENGINEER])
    add_call(
        db, 1, sla_due_at=NOW + timedelta(hours=1), assigned_engineer_id=ENGINEER_EMPLOYEE, current_status="In progress"
    )
    add_call(db, 2, sla_due_at=NOW + timedelta(hours=5))  # outside the 120-minute warning window

    assert run(db) == (1, 0)
    (due_soon,) = alerts(db)
    assert due_soon.dedupe_key == "svc.service_call:1:due-soon" and "due by" in due_soon.message
    assert recipients_of(db, due_soon.id) == {TL_BBSR, ENGINEER_USER}

    assert run(db, NOW + timedelta(hours=2)) == (1, 1)  # breached; the due-soon alert is resolved
    keys = {a.dedupe_key: a.status for a in alerts(db)}
    assert keys == {"svc.service_call:1:due-soon": "Resolved", "svc.service_call:1:breached": "Open"}
    with Session(db) as session:
        assert [e.event_type for e in session.scalars(select(SlaEvent).order_by(SlaEvent.id))] == [
            "Warning",
            "Breached",
        ]


def test_sla_stage_filter_and_closing_the_call_resolves(db: Engine) -> None:
    add_rule(db, "SVC_SLA_DUE", {"stages": ["Breached"]}, [TEAM_LEADS])
    add_call(db, 1, sla_due_at=NOW + timedelta(minutes=30))  # due soon (default 60-min window): not wanted
    add_call(db, 2, sla_due_at=NOW - timedelta(hours=3))
    assert run(db) == (1, 0)
    update_call(db, 2, current_status="Closed")
    assert run(db, NOW + timedelta(minutes=1)) == (0, 1)


# ------------------------------------------------------------------ stale status / awaiting parts


def test_status_unchanged_uses_the_last_status_change(db: Engine) -> None:
    add_rule(db, "SVC_STATUS_STALE", {"afterHours": 24}, [ASSIGNED_ENGINEER])
    add_call(
        db, 1, current_status="In progress", assigned_engineer_id=ENGINEER_EMPLOYEE, received_at=NOW - timedelta(days=3)
    )
    insert_row(
        db,
        "svc.call_status_log",
        service_call_id=1,
        from_status="Assigned",
        to_status="In progress",
        changed_at=NOW - timedelta(hours=30),
    )
    add_call(db, 2, current_status="In progress", received_at=NOW - timedelta(days=3))
    insert_row(
        db,
        "svc.call_status_log",
        service_call_id=2,
        from_status="Assigned",
        to_status="In progress",
        changed_at=NOW - timedelta(hours=2),
    )
    assert run(db) == (1, 0)
    (alert,) = alerts(db)
    assert alert.dedupe_key == "svc.service_call:1:In progress" and "1 d 6 h" in alert.message
    assert recipients_of(db, alert.id) == {ENGINEER_USER}


def test_awaiting_parts_beyond_the_set_days(db: Engine) -> None:
    add_rule(db, "SVC_AWAITING_PARTS", {"afterDays": 3}, [TEAM_LEADS])
    for call_id, days in ((1, 4), (2, 2)):
        add_call(db, call_id, current_status="Awaiting parts", received_at=NOW - timedelta(days=10))
        insert_row(
            db,
            "svc.call_status_log",
            service_call_id=call_id,
            from_status="In progress",
            to_status="Awaiting parts",
            changed_at=NOW - timedelta(days=days),
        )
    assert run(db) == (1, 0)
    assert alerts(db)[0].dedupe_key == "svc.service_call:1"


# ------------------------------------------------------------------ warranty / AMC


def test_warranty_and_amc_ending(db: Engine) -> None:
    add_rule(db, "MACHINE_COVERAGE_EXPIRY", {"daysBefore": 30}, [TEAM_LEADS])
    today = NOW.date()
    insert_row(
        db,
        "core.machine_unit",
        id=1,
        serial_number="SN-1",
        model_id=1,
        principal_id=HITACHI,
        customer_id=CUSTOMER,
        sold_by_branch_id=BBSR,
        status="Sold",
        warranty_end_date=today + timedelta(days=10),
    )
    insert_row(
        db,
        "core.machine_unit",
        id=2,
        serial_number="SN-2",
        model_id=1,
        principal_id=HITACHI,
        customer_id=CUSTOMER,
        status="Sold",
        warranty_end_date=today + timedelta(days=90),
    )
    insert_row(
        db,
        "svc.service_contract",
        id=1,
        company_id=COMPANY,
        contract_no="AMC-1",
        principal_id=HITACHI,
        customer_id=CUSTOMER,
        contract_type="AMC",
        status="Active",
        start_date=date(2026, 1, 1),
        end_date=today + timedelta(days=20),
    )
    assert run(db) == (2, 0)
    keys = sorted(a.dedupe_key for a in alerts(db))
    assert keys == [
        f"core.machine_unit:1:warranty:{today + timedelta(days=10)}",
        f"svc.service_contract:1:amc:{today + timedelta(days=20)}",
    ]
    # Once the end date has passed, the alert is no longer relevant and is resolved.
    assert run(db, NOW + timedelta(days=40)) == (0, 2)


# ------------------------------------------------------------------ API: Alert Master, events, inbox


def make_client(settings: Settings, db: Engine, user_id: int, permissions: set[str], **user: Any) -> TestClient:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(
        id=user_id,
        permissions=frozenset(permissions),
        default_branch_id=BBSR,
        branch_ids=None,
        principal_ids=None,
        **user,
    )
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=user_id, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    return TestClient(app, raise_server_exceptions=False)


RULE_ADMIN = {"core.alert.rule.view", "core.alert.rule.manage", "core.alert.view"}


@pytest.fixture
def admin(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with make_client(settings, db, ADMIN_USER, RULE_ADMIN) as client:
        yield client


def new_rule(client: TestClient, **changes: Any) -> Any:
    body = {
        "code": "UNASSIGNED_30",
        "name": "Not assigned in 30 min",
        "alertType": "SVC_CALL_UNASSIGNED",
        "severity": "Warning",
        "parameters": {"afterMinutes": 30},
        "recipients": [{"recipientType": "Role", "roleId": TEAM_LEAD}],
    } | changes
    return client.post(f"{URL}/alert-rules", json=body)


def test_alert_types_catalogue(admin: TestClient) -> None:
    types = {t["code"]: t for t in admin.get(f"{URL}/alert-types").json()}
    assert set(types) == {
        "SVC_CALL_UNASSIGNED",
        "SVC_SLA_DUE",
        "SVC_STATUS_STALE",
        "SVC_AWAITING_PARTS",
        "SVC_CALL_REOPENED",
        "MACHINE_COVERAGE_EXPIRY",
        "SVC_PART_REQUEST",
    }
    assert types["SVC_CALL_REOPENED"]["trigger"] == "Event"
    assert types["SVC_PART_REQUEST"]["trigger"] == "Event"
    assert "Assigned engineer" not in types["MACHINE_COVERAGE_EXPIRY"]["recipientTypes"]
    assert [p["key"] for p in types["SVC_SLA_DUE"]["params"]] == ["stages", "priorities"]  # no SLA times here


def test_create_rule_fills_defaults_and_validates(admin: TestClient) -> None:
    created = new_rule(admin, parameters={})
    assert created.status_code == 201, created.text
    rule = created.json()
    assert rule["parameters"] == {"afterMinutes": 30, "priorities": [], "machineDownOnly": False}
    assert rule["recipientSummary"] == "Team Lead" and rule["trigger"] == "Scheduled"

    assert new_rule(admin).status_code == 409  # duplicate code
    bad = new_rule(admin, code="X1", parameters={"afterMinutes": 0, "foo": 1}).json()["errors"]
    assert set(bad) == {"parameters.afterMinutes", "parameters.foo"}
    wrong_recipient = new_rule(
        admin,
        code="X2",
        alertType="MACHINE_COVERAGE_EXPIRY",
        parameters={},
        recipients=[{"recipientType": "Assigned engineer"}],
    )
    assert wrong_recipient.status_code == 400 and "recipients.0" in wrong_recipient.json()["errors"]
    assert new_rule(admin, code="X3", recipients=[]).status_code == 422


def test_update_rule_with_row_version_and_replace_recipients(admin: TestClient) -> None:
    rule = new_rule(admin).json()
    url = f"{URL}/alert-rules/{rule['id']}"
    change = {"parameters": {"afterMinutes": 60}, "recipients": [{"recipientType": "User", "appUserId": TL_CTC}]}
    assert admin.patch(url, json=change).status_code == 428
    updated = admin.patch(url, json=change, headers={"If-Match": f'"{rule["rowVersion"]}"'})
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["parameters"]["afterMinutes"] == 60
    assert [r["recipientType"] for r in body["recipients"]] == ["User"] and body["recipientSummary"] == "tl.ctc"


def test_test_rule_is_a_dry_run(admin: TestClient, db: Engine) -> None:
    add_call(db, 1, received_at=utcnow() - timedelta(hours=2))  # the API runs on the real clock (UTC)
    rule = new_rule(admin).json()
    result = admin.post(f"{URL}/alert-rules/{rule['id']}/test").json()
    assert result["total"] == 1
    assert result["matches"][0]["entityId"] == 1 and result["matches"][0]["recipients"] == ["tl.bbsr"]
    assert alerts(db) == []  # nothing raised


def test_deactivating_a_rule_resolves_its_open_alerts(admin: TestClient, db: Engine) -> None:
    rule_id = add_rule(db, "SVC_CALL_UNASSIGNED", {"afterMinutes": 30}, [TEAM_LEADS])
    add_call(db, 1, received_at=NOW - timedelta(hours=2))
    run(db)
    deactivated = admin.post(f"{URL}/alert-rules/{rule_id}/deactivate").json()
    assert deactivated["isActive"] is False and deactivated["openAlertCount"] == 0
    assert alerts(db)[0].resolution_note == "Rule deactivated"


def test_reopening_a_call_raises_an_event_alert_per_reopen(settings: Settings, db: Engine) -> None:
    add_rule(db, "SVC_CALL_REOPENED", {}, [TEAM_LEADS, {"recipient_type": "Call logged by"}], reraise_policy="Never")
    add_call(db, 1, current_status="Closed", reopen_count=0)
    lead = {"svc.call.view", "svc.call.assign", "svc.call.reopen", "svc.call.close"}
    with make_client(settings, db, TL_BBSR, lead) as client:
        call = client.get("/api/v1/svc/service-calls/1").json()
        reopened = client.post(
            "/api/v1/svc/service-calls/1/status",
            json={"status": "Reopened"},
            headers={"If-Match": f'"{call["rowVersion"]}"'},
        )
        assert reopened.status_code == 200, reopened.text
        (alert,) = alerts(db)
        assert alert.dedupe_key == "svc.service_call:1:reopen-1" and alert.title == "SC-0001 reopened"
        assert recipients_of(db, alert.id) == {TL_BBSR, LOGGER}

        # Closed again: the scheduled pass resolves it; a second reopen is a new alert despite 'Never'.
        update_call(db, 1, current_status="Closed")
        assert run(db) == (0, 1)
        call = client.get("/api/v1/svc/service-calls/1").json()
        client.post(
            "/api/v1/svc/service-calls/1/status",
            json={"status": "Reopened"},
            headers={"If-Match": f'"{call["rowVersion"]}"'},
        )
        assert [a.dedupe_key for a in alerts(db)] == ["svc.service_call:1:reopen-1", "svc.service_call:1:reopen-2"]


def test_inbox_lists_only_my_alerts_and_tracks_read_and_acknowledge(settings: Settings, db: Engine) -> None:
    add_rule(db, "SVC_CALL_UNASSIGNED", {"afterMinutes": 30}, [TEAM_LEADS, {"recipient_type": "Call logged by"}])
    add_call(db, 1, received_at=NOW - timedelta(hours=2))
    add_call(db, 2, received_at=NOW - timedelta(hours=2), branch_id=CTC)
    run(db)
    # All three stay open together: closing an app disposes the shared in-memory SQLite engine.
    with (
        make_client(settings, db, TL_BBSR, {"core.alert.view"}) as lead,
        make_client(settings, db, LOGGER, {"core.alert.view"}) as logger,
        make_client(settings, db, TL_CTC, {"core.alert.view"}) as other,
    ):
        mine = lead.get(f"{URL}/my-alerts").json()
        assert [a["entityId"] for a in mine["items"]] == [1]  # the Cuttack call goes to the Cuttack lead
        alert_id = mine["items"][0]["id"]
        assert lead.get(f"{URL}/my-alerts/summary").json() == {"unread": 1, "open": 1}

        assert lead.post(f"{URL}/my-alerts/{alert_id}/read").json()["readAt"] is not None
        assert lead.get(f"{URL}/my-alerts/summary").json() == {"unread": 0, "open": 1}
        acknowledged = lead.post(f"{URL}/my-alerts/{alert_id}/acknowledge").json()
        assert acknowledged["status"] == "Acknowledged" and acknowledged["acknowledgedByName"] == "tl.bbsr"
        assert lead.get(f"{URL}/my-alerts", params={"unreadOnly": True}).json()["total"] == 0

        theirs = logger.get(f"{URL}/my-alerts").json()["items"]
        assert {a["entityId"] for a in theirs} == {1, 2}
        assert next(a for a in theirs if a["entityId"] == 1)["status"] == "Acknowledged"  # for everyone
        assert next(a for a in theirs if a["entityId"] == 1)["readAt"] is None  # read state is per person

        assert other.post(f"{URL}/my-alerts/{alert_id}/read").status_code == 404  # not their alert


def test_permissions(settings: Settings, db: Engine) -> None:
    with make_client(settings, db, TL_BBSR, {"core.alert.view", "core.alert.rule.view"}) as viewer:
        assert viewer.get(f"{URL}/alert-rules").status_code == 200
        assert new_rule(viewer).status_code == 403
        assert viewer.get(f"{URL}/alert-rules/form-options").status_code == 403
