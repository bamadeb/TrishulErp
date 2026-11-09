"""Service reports and inspection checklists: route -> service -> SQL (SQLite)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.common.errors import ApiError
from trishul_api.config import Settings
from trishul_api.db.models import CallStatusLog, ServiceCall, ServiceReport, ServiceVisit
from trishul_api.modules.core.documents import storage
from trishul_api.modules.service.service import ServiceCallService

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine
from .test_manual_travel import BRANCH, COMPANY, CUSTOMER, ENGINEER, OTHER_ENGINEER, PNG, PRINCIPAL, client_for

TABLES = [
    "core.company",
    "core.branch",
    "core.principal",
    "core.customer",
    "core.employee",
    "core.app_user",
    "core.audit_log",
    "core.attachment",
    "core.lookup_type",
    "core.lookup_value",
    "svc.service_call",
    "svc.call_assignment",
    "svc.call_status_log",
    "svc.service_visit",
    "svc.service_report",
    "svc.report_checklist_item",
    "svc.checklist_template",
    "svc.checklist_template_item",
]
LEAD = 302
CALL, VISIT = 24, 500
CHECKLIST = "/api/v1/svc/checklist-templates"
ENGINEER_PERMISSIONS = {"svc.call.view.assigned", "svc.report.submit", "svc.call.status.update"}


@pytest.fixture(autouse=True)
def storage_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(storage, "_ROOT", tmp_path / "attachments")
    return tmp_path / "attachments"


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
    for emp, first in ((ENGINEER, "Jyoti"), (OTHER_ENGINEER, "Parsuram"), (LEAD, "Lead")):
        insert_row(
            engine,
            "core.employee",
            id=emp,
            company_id=COMPANY,
            branch_id=BRANCH,
            employee_code=f"E{emp}",
            first_name=first,
            last_name="Das",
            employee_type="Permanent",
            status="Active",
        )
    for user_id, emp in ((1, ENGINEER), (2, OTHER_ENGINEER), (3, LEAD)):
        insert_row(
            engine, "core.app_user", id=user_id, username=f"user{user_id}", cognito_sub=f"sub{user_id}", employee_id=emp
        )
    for type_id, code in ((1, "MACHINE_CONDITION"), (2, "FAILURE_CODE"), (3, "CALL_TYPE")):
        insert_row(engine, "core.lookup_type", id=type_id, code=code, name=code, module="Service")
    for value_id, type_id, code, label in (
        (10, 1, "WORKING", "Working"),
        (11, 1, "BREAKDOWN", "Breakdown"),
        (20, 2, "HYD", "Hydraulic leak"),
        (30, 3, "BREAKDOWN", "Breakdown"),
    ):
        insert_row(
            engine, "core.lookup_value", id=value_id, lookup_type_id=type_id, code=code, label=label, sort_order=1
        )
    insert_row(
        engine,
        "svc.service_call",
        id=CALL,
        company_id=COMPANY,
        branch_id=BRANCH,
        principal_id=PRINCIPAL,
        call_no="BHADRAK/SC/00024",
        customer_id=CUSTOMER,
        assigned_engineer_id=ENGINEER,
        call_type_lookup_id=30,
        current_status="Reached site",
    )
    insert_row(
        engine,
        "svc.service_visit",
        id=VISIT,
        service_call_id=CALL,
        visit_no=1,
        visit_purpose="Inspection",
        engineer_employee_id=ENGINEER,
        status="On site",
        service_started_at=datetime.now(UTC).replace(tzinfo=None),
    )
    return engine


def make_template(engine: Engine, name: str, template_id: int, principal_id: int | None, questions: int = 2) -> None:
    insert_row(engine, "svc.checklist_template", id=template_id, name=name, principal_id=principal_id)
    for n in range(1, questions + 1):
        insert_row(
            engine,
            "svc.checklist_template_item",
            id=template_id * 100 + n,
            checklist_template_id=template_id,
            sequence=n,
            item_text=f"{name} question {n}",
            response_type="OK Not OK",
            is_mandatory=n == 1,
        )


@pytest.fixture
def engineer(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, 1, ENGINEER, ENGINEER_PERMISSIONS) as c:
        yield c


@pytest.fixture
def other(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, 2, OTHER_ENGINEER, ENGINEER_PERMISSIONS) as c:
        yield c


@pytest.fixture
def lead(settings: Settings, db: Engine) -> Iterator[TestClient]:
    permissions = {"svc.call.view", "svc.call.assign", "svc.call.close", "svc.checklist.manage"}
    with client_for(settings, db, 3, LEAD, permissions) as c:
        yield c


def if_match(report: dict[str, Any]) -> dict[str, str]:
    return {"If-Match": f'"{report["rowVersion"]}"'}


def start(client: TestClient, visit: int = VISIT) -> Any:
    return client.post(f"/api/v1/svc/service-visits/{visit}/report")


def fill(client: TestClient, report: dict[str, Any], **changes: Any) -> dict[str, Any]:
    body = {
        "hmrReading": "1234.5",
        "machineConditionLookupId": 10,
        "findings": "Hydraulic hose leaking",
        "failureCodeLookupId": 20,
        "actionTaken": "Hose replaced",
        "customerSignedName": "Banamali Behera",
    } | changes
    response = client.patch(f"/api/v1/svc/service-reports/{report['id']}", json=body, headers=if_match(report))
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    return out


def submit(client: TestClient, report: dict[str, Any], **body: Any) -> Any:
    return client.post(
        f"/api/v1/svc/service-reports/{report['id']}/submit",
        json={"nextAction": "None"} | body,
        headers=if_match(report),
    )


def answer_all(client: TestClient, report: dict[str, Any]) -> dict[str, Any]:
    answers = [{"id": q["id"], "isOk": True} for q in report["checklist"]]
    return fill(client, report, checklist=answers)


# ---------------------------------------------------------------- starting


def test_start_report_copies_the_best_matching_checklist(engineer: TestClient, db: Engine) -> None:
    make_template(db, "Generic", 1, None)
    make_template(db, "Hitachi", 2, PRINCIPAL, questions=3)
    make_template(db, "BYD", 3, 2)
    response = start(engineer)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reportNo"] == "BHADRAK/SC/00024/R1"
    assert body["status"] == "Draft" and body["canEdit"] is True
    assert [q["itemText"] for q in body["checklist"]] == [f"Hitachi question {n}" for n in (1, 2, 3)]
    assert [q["isMandatory"] for q in body["checklist"]] == [True, False, False]
    with Session(db) as s:
        assert s.get(ServiceCall, CALL).current_status == "In progress"  # type: ignore[union-attr]


def test_starting_twice_returns_the_same_report(engineer: TestClient, db: Engine) -> None:
    make_template(db, "Generic", 1, None)
    first, second = start(engineer).json(), start(engineer).json()
    assert first["id"] == second["id"]
    assert len(second["checklist"]) == 2


def test_report_cannot_start_before_reaching_the_site(engineer: TestClient, db: Engine) -> None:
    with Session(db) as s:
        s.get(ServiceVisit, VISIT).status = "On the way"  # type: ignore[union-attr]
        s.commit()
    response = start(engineer)
    assert response.status_code == 400
    assert "site" in response.json()["detail"]


def test_an_engineer_not_on_the_call_cannot_start_or_see_it(other: TestClient) -> None:
    assert start(other).status_code == 404
    assert other.get(f"/api/v1/svc/service-visits/{VISIT}/report").status_code == 404


def test_visits_list_shows_who_can_start_a_report(engineer: TestClient) -> None:
    before = engineer.get(f"/api/v1/svc/service-calls/{CALL}/visits").json()
    assert before[0]["canStartReport"] is True and before[0]["report"] is None
    start(engineer)
    after = engineer.get(f"/api/v1/svc/service-calls/{CALL}/visits").json()
    assert after[0]["canStartReport"] is False
    assert after[0]["report"]["status"] == "Draft"


# ---------------------------------------------------------------- filling and submitting


def test_submit_lists_everything_still_missing(engineer: TestClient, db: Engine) -> None:
    make_template(db, "Generic", 1, None)
    report = start(engineer).json()
    response = submit(engineer, report)
    assert response.status_code == 400
    errors = response.json()["errors"]
    assert {"machineConditionLookupId", "findings", "failureCodeLookupId", "actionTaken", "customerSignedName"} <= set(
        errors
    )
    assert "Generic question 1" in errors["checklist"][0]


def test_lookup_values_must_be_of_the_right_type(engineer: TestClient) -> None:
    report = start(engineer).json()
    response = engineer.patch(
        f"/api/v1/svc/service-reports/{report['id']}",
        json={"machineConditionLookupId": 20},  # a FAILURE_CODE value
        headers=if_match(report),
    )
    assert response.status_code == 400
    assert "machineConditionLookupId" in response.json()["errors"]


def test_unknown_checklist_question_is_rejected(engineer: TestClient) -> None:
    report = start(engineer).json()
    response = engineer.patch(
        f"/api/v1/svc/service-reports/{report['id']}",
        json={"checklist": [{"id": 9999, "isOk": True}]},
        headers=if_match(report),
    )
    assert response.status_code == 400


def test_submitting_finishes_the_visit_and_the_report_but_not_the_call(engineer: TestClient, db: Engine) -> None:
    make_template(db, "Generic", 1, None)
    report = answer_all(engineer, start(engineer).json())
    response = submit(engineer, report)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "Submitted" and body["canEdit"] is False and body["nextAction"] == "None"
    assert body["machineCondition"] == "Working" and body["failureCode"] == "Hydraulic leak"
    with Session(db) as s:
        visit = s.get(ServiceVisit, VISIT)
        assert (visit.status, visit.next_action) == ("Completed", "None")  # type: ignore[union-attr]
        assert visit.service_ended_at is not None  # type: ignore[union-attr]
        assert s.get(ServiceCall, CALL).current_status == "Report submitted"  # type: ignore[union-attr]
        assert s.scalars(select(CallStatusLog.to_status).order_by(CallStatusLog.id)).all()[-1] == "Report submitted"


def test_a_submitted_report_is_locked(engineer: TestClient, db: Engine) -> None:
    report = fill(engineer, start(engineer).json())
    done = submit(engineer, report).json()
    response = engineer.patch(
        f"/api/v1/svc/service-reports/{done['id']}", json={"findings": "changed"}, headers=if_match(done)
    )
    assert response.status_code == 400
    assert "submitted" in response.json()["detail"]


def test_parts_required_puts_the_call_on_awaiting_parts(engineer: TestClient, db: Engine) -> None:
    report = fill(engineer, start(engineer).json(), failureCodeLookupId=None, actionTaken=None)
    body = submit(engineer, report, nextAction="Parts required").json()
    assert body["isPartsRequired"] is True
    with Session(db) as s:
        assert s.get(ServiceCall, CALL).current_status == "Awaiting parts"  # type: ignore[union-attr]


def test_revisit_needs_a_date_and_plans_the_next_visit(engineer: TestClient, db: Engine) -> None:
    report = fill(engineer, start(engineer).json(), failureCodeLookupId=None, actionTaken=None)
    assert submit(engineer, report, nextAction="Revisit").status_code == 400
    past = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    assert submit(engineer, report, nextAction="Revisit", nextVisitDate=past).status_code == 400
    day = (datetime.now(UTC).date() + timedelta(days=2)).isoformat()
    response = submit(engineer, report, nextAction="Revisit", nextVisitDate=day)
    assert response.status_code == 200, response.text
    with Session(db) as s:
        planned = s.scalars(select(ServiceVisit).where(ServiceVisit.status == "Planned")).all()
        assert [(v.visit_no, v.planned_date.isoformat()) for v in planned] == [(2, day)]
        assert s.get(ServiceCall, CALL).current_status == "Revisit scheduled"  # type: ignore[union-attr]


def test_customer_who_is_away_can_be_recorded_with_a_reason(engineer: TestClient, db: Engine) -> None:
    report = fill(engineer, start(engineer).json(), customerSignedName=None)
    assert submit(engineer, report).status_code == 400
    body = submit(engineer, report, customerUnavailableReason="Owner out of town").json()
    assert body["customerSignedName"] == "Customer not available"
    with Session(db) as s:
        assert "Owner out of town" in s.get(ServiceVisit, VISIT).remarks  # type: ignore[union-attr,operator]


def test_customer_signature_is_stored_with_the_report(engineer: TestClient, db: Engine) -> None:
    report = start(engineer).json()
    response = engineer.post(
        f"/api/v1/svc/service-reports/{report['id']}/customer-signature",
        files={"file": ("signature.png", PNG, "image/png")},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()["customerSignatureDocumentId"]
    assert document_id
    download = engineer.get(f"/api/v1/svc/service-reports/{report['id']}/customer-signature")
    assert download.status_code == 200 and download.content == PNG


def test_signature_must_be_a_png(engineer: TestClient) -> None:
    report = start(engineer).json()
    response = engineer.post(
        f"/api/v1/svc/service-reports/{report['id']}/customer-signature",
        files={"file": ("signature.png", b"not a png", "image/png")},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------- closing the call


def test_call_cannot_be_completed_while_the_visit_is_open(engineer: TestClient, db: Engine) -> None:
    """The completion rule itself (the status endpoint also needs the call's machine and site tables)."""
    lead_user = make_user(id=3, employee_id=LEAD, permissions=frozenset({"svc.call.view", "svc.call.close"}))
    with Session(db) as s, pytest.raises(ApiError, match="service report of visit 1"):
        ServiceCallService(s, lead_user)._require_reports_submitted(CALL)

    report = fill(engineer, start(engineer).json())
    assert submit(engineer, report).status_code == 200
    with Session(db) as s:
        ServiceCallService(s, lead_user)._require_reports_submitted(CALL)  # no longer raises


def test_team_lead_can_read_the_report_but_an_office_viewer_cannot_change_it(
    settings: Settings, db: Engine, engineer: TestClient
) -> None:
    report = start(engineer).json()
    with client_for(settings, db, 3, LEAD, {"svc.call.view", "svc.report.submit"}) as viewer:
        got = viewer.get(f"/api/v1/svc/service-visits/{VISIT}/report")
        assert got.status_code == 200 and got.json()["canEdit"] is False
        denied = viewer.patch(
            f"/api/v1/svc/service-reports/{report['id']}", json={"findings": "x"}, headers=if_match(report)
        )
        assert denied.status_code == 404


# ---------------------------------------------------------------- checklist templates


def test_checklists_are_managed_with_a_stable_question_history(
    lead: TestClient, engineer: TestClient, db: Engine
) -> None:
    created = lead.post(
        CHECKLIST,
        json={
            "name": "Excavator inspection",
            "principalId": PRINCIPAL,
            "callTypeLookupId": 30,
            "items": [
                {"itemText": "Hydraulic oil level", "responseType": "OK Not OK", "isMandatory": True},
                {"itemText": "Engine hours", "responseType": "Number", "isMandatory": False},
            ],
        },
    )
    assert created.status_code == 201, created.text
    template = created.json()
    assert [i["itemText"] for i in template["items"]] == ["Hydraulic oil level", "Engine hours"]
    assert template["principalName"] == "Tata Hitachi" and template["callType"] == "Breakdown"

    report = start(engineer).json()  # copies the new checklist
    assert [q["itemText"] for q in report["checklist"]] == ["Hydraulic oil level", "Engine hours"]
    assert report["checklist"][1]["responseType"] == "Number"

    keep = template["items"][0]
    updated = lead.patch(
        f"{CHECKLIST}/{template['id']}",
        json={
            "name": "Excavator inspection v2",
            "principalId": PRINCIPAL,
            "callTypeLookupId": 30,
            "items": [{"id": keep["id"], "itemText": "Hydraulic oil level and colour"}, {"itemText": "Track tension"}],
        },
        headers={"If-Match": f'"{template["rowVersion"]}"'},
    )
    assert updated.status_code == 200, updated.text
    assert [i["itemText"] for i in updated.json()["items"]] == ["Hydraulic oil level and colour", "Track tension"]
    # the report started earlier keeps its own copy
    after = engineer.get(f"/api/v1/svc/service-visits/{VISIT}/report").json()
    assert [q["itemText"] for q in after["checklist"]] == ["Hydraulic oil level", "Engine hours"]
    listed = lead.get(CHECKLIST).json()
    assert [t["name"] for t in listed] == ["Excavator inspection v2"]


def test_checklist_references_are_validated(lead: TestClient) -> None:
    response = lead.post(CHECKLIST, json={"name": "X", "principalId": 999, "items": [{"itemText": "Q"}]})
    assert response.status_code == 400
    assert "principalId" in response.json()["errors"]


def test_engineer_cannot_manage_checklists(engineer: TestClient) -> None:
    assert engineer.get(CHECKLIST).status_code == 403
    assert engineer.post(CHECKLIST, json={"name": "X", "items": [{"itemText": "Q"}]}).status_code == 403


def test_reports_are_a_document_target(engineer: TestClient) -> None:
    report = start(engineer).json()
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF"
    response = engineer.post(
        "/api/v1/core/documents",
        data={"entityType": "svc.service_report", "entityId": str(report["id"]), "category": "Photo"},
        files={"file": ("work.pdf", pdf, "application/octet-stream")},
    )
    assert response.status_code == 201, response.text


def test_report_row_matches_the_database(engineer: TestClient, db: Engine) -> None:
    report = fill(engineer, start(engineer).json())
    with Session(db) as s:
        row = s.scalars(select(ServiceReport)).one()
        assert (row.report_no, float(row.hmr_reading or 0), row.action_taken) == (
            report["reportNo"],
            1234.5,
            "Hose replaced",
        )
