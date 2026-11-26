"""Complaint management: raise, own complaints, department complaints, status history, alerts, issue types.

People in these tests:
    RAJU     (user 11, employee 101, Service)    raises complaints
    MEERA    (user 12, employee 102, Admin dept) head of the Admin department, no complaint permission
    SUNIL    (user 13, employee 103, Admin dept) core.complaint.manage in the Admin department
    OTHER    (user 14, employee 104, Service)    core.complaint.manage, but in Service: not an Admin leader
    SUPER    (user 15, no employee)              core.complaint.manage_all
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import Alert, AlertRecipient, Complaint, ComplaintHistory
from trishul_api.main import create_app
from trishul_api.modules.core.documents import storage

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.region",
    "core.principal",
    "core.branch",
    "hr.department",
    "hr.designation",
    "core.employee",
    "core.app_user",
    "core.role",
    "core.user_role",
    "core.permission",
    "core.role_permission",
    "core.user_principal_access",
    "core.number_series",
    "core.complaint_issue_type",
    "core.complaint",
    "core.complaint_history",
    "core.attachment",
    "core.alert_rule",
    "core.alert_rule_recipient",
    "core.alert",
    "core.alert_recipient",
    "core.audit_log",
]
SERVICE, ADMIN_DEPT = 1, 2
WATER, OTHER_ADMIN, SERVICE_TOOLS = 1, 2, 3
RAISE, MANAGE, MANAGE_ALL = "core.complaint.raise", "core.complaint.manage", "core.complaint.manage_all"

PEOPLE: dict[str, CurrentUser] = {
    "raju": make_user(id=11, employee_id=101, display_name="Raju Das", permissions=frozenset({RAISE})),
    "meera": make_user(id=12, employee_id=102, display_name="Meera Rao", permissions=frozenset({RAISE})),
    "sunil": make_user(id=13, employee_id=103, display_name="Sunil Sahu", permissions=frozenset({RAISE, MANAGE})),
    "other": make_user(id=14, employee_id=104, display_name="Asha Nayak", permissions=frozenset({RAISE, MANAGE})),
    "super": make_user(
        id=15, employee_id=None, display_name="Admin", default_branch_id=1, permissions=frozenset({RAISE, MANAGE_ALL})
    ),
    "nobody": make_user(id=16, employee_id=None, default_branch_id=None, permissions=frozenset()),
    # Raju's colleague in Service whose role grants nothing about complaints.
    "norole": make_user(id=17, employee_id=105, display_name="Biju Sethi", permissions=frozenset()),
}


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Engine:
    monkeypatch.setattr(storage, "_ROOT", tmp_path / "attachments")
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=1, code="TRISHUL", legal_name="Trishul Pvt Ltd")
    insert_row(engine, "core.branch", id=1, company_id=1, code="BDK", name="Bhadrak")
    insert_row(engine, "hr.department", id=SERVICE, code="SERVICE", name="Service")
    insert_row(engine, "hr.department", id=ADMIN_DEPT, code="ADMIN", name="Admin", head_employee_id=102)
    insert_row(engine, "hr.designation", id=1, code="ENG", name="Engineer")
    for employee_id, code, first, department in [
        (101, "EMP0101", "Raju", SERVICE),
        (102, "EMP0102", "Meera", ADMIN_DEPT),
        (103, "EMP0103", "Sunil", ADMIN_DEPT),
        (104, "EMP0104", "Asha", SERVICE),
        (105, "EMP0105", "Biju", SERVICE),
    ]:
        insert_row(
            engine,
            "core.employee",
            id=employee_id,
            company_id=1,
            branch_id=1,
            department_id=department,
            designation_id=1,
            employee_code=code,
            first_name=first,
            mobile="9876543210",
            status="Active",
            is_active=True,
        )
    for user_id, employee_id, username in [
        (11, 101, "raju"),
        (12, 102, "meera"),
        (13, 103, "sunil"),
        (14, 104, "asha"),
        (15, None, "admin"),
        (17, 105, "biju"),
    ]:
        insert_row(
            engine,
            "core.app_user",
            id=user_id,
            employee_id=employee_id,
            username=username,
            is_active=True,
            is_locked=False,
        )
    # Roles, so the leaders of a department are found from role permissions like in production.
    insert_row(engine, "core.permission", id=1, code=RAISE, module="Core", is_active=True)
    insert_row(engine, "core.permission", id=2, code=MANAGE, module="Core", is_active=True)
    insert_row(engine, "core.permission", id=3, code=MANAGE_ALL, module="Core", is_active=True)
    insert_row(engine, "core.role", id=1, code="STAFF", name="Staff", is_active=True)
    insert_row(engine, "core.role", id=2, code="DEPT_ADMIN", name="Department admin", is_active=True)
    insert_row(engine, "core.role", id=3, code="ADMIN", name="Administrator", is_active=True)
    for role_id, permission_id in [(1, 1), (2, 1), (2, 2), (3, 1), (3, 3)]:
        insert_row(engine, "core.role_permission", role_id=role_id, permission_id=permission_id, is_active=True)
    for user_id, role_id in [(11, 1), (12, 1), (13, 2), (14, 2), (15, 3)]:
        insert_row(engine, "core.user_role", app_user_id=user_id, role_id=role_id, is_active=True)

    insert_row(
        engine,
        "core.number_series",
        company_id=1,
        branch_id=1,
        document_type="COMPLAINT",
        prefix="BHADRAK/CMP/",
        next_number=1,
        padding=5,
    )
    insert_row(
        engine, "core.complaint_issue_type", id=WATER, department_id=ADMIN_DEPT, name="Water supply", sort_order=1
    )
    insert_row(
        engine, "core.complaint_issue_type", id=OTHER_ADMIN, department_id=ADMIN_DEPT, name="Other", sort_order=9
    )
    insert_row(engine, "core.complaint_issue_type", id=SERVICE_TOOLS, department_id=SERVICE, name="Tools", sort_order=1)
    for rule_id, code, alert_type, severity in [
        (1, "COMPLAINT_RAISED", "CMP_COMPLAINT_RAISED", "Warning"),
        (2, "COMPLAINT_UPDATED", "CMP_COMPLAINT_UPDATED", "Info"),
    ]:
        insert_row(
            engine,
            "core.alert_rule",
            id=rule_id,
            company_id=1,
            code=code,
            name=code,
            alert_type=alert_type,
            severity=severity,
            parameters="{}",
            reraise_policy="Never",
            is_active=True,
        )
    return engine


@pytest.fixture
def as_user(db: Engine) -> Iterator[Callable[[str], TestClient]]:
    settings = Settings(environment="test", auth_mode="dev", dev_username="t", _env_file=None)
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    current: dict[str, CurrentUser] = {}

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=current["user"].id, source="Android", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    api.dependency_overrides[get_current_user] = lambda: current["user"]
    with TestClient(app, raise_server_exceptions=False) as client:

        def switch(name: str) -> TestClient:
            current["user"] = PEOPLE[name]
            return client

        yield switch


def _raise(client: TestClient, description: str = "No drinking water on the 2nd floor since Monday") -> dict:
    response = client.post(
        "/api/v1/core/complaints",
        json={"departmentId": ADMIN_DEPT, "issueTypeId": WATER, "description": description},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _alerts(db: Engine) -> list[tuple[str, str, str, list[int]]]:
    with Session(db) as s:
        alerts = s.scalars(select(Alert).order_by(Alert.id)).all()
        return [
            (
                a.alert_type,
                a.status,
                a.title,
                sorted(s.scalars(select(AlertRecipient.app_user_id).where(AlertRecipient.alert_id == a.id))),
            )
            for a in alerts
        ]


# ---------------------------------------------------------------- raise


def test_the_form_lists_departments_with_their_issue_types(as_user: Callable[[str], TestClient]) -> None:
    options = as_user("raju").get("/api/v1/core/complaint-departments").json()
    assert [(d["name"], [t["name"] for t in d["issueTypes"]]) for d in options] == [
        ("Admin", ["Water supply", "Other"]),
        ("Service", ["Tools"]),
    ]


def test_a_new_department_gets_the_other_issue_type_and_shows_on_the_form(
    as_user: Callable[[str], TestClient], db: Engine
) -> None:
    insert_row(db, "hr.department", id=3, code="HR", name="HR")
    insert_row(db, "hr.department", id=4, code="OLD", name="Closed down", is_active=False)
    insert_row(db, "hr.department", id=5, code="STORE", name="Store")
    # The Super Admin switched off the Store's only type: it stays off the form, nothing is re-added.
    insert_row(db, "core.complaint_issue_type", id=5, department_id=5, name="Racks", sort_order=1, is_active=False)
    client = as_user("raju")
    options = client.get("/api/v1/core/complaint-departments").json()
    assert [(d["name"], [t["name"] for t in d["issueTypes"]]) for d in options] == [
        ("Admin", ["Water supply", "Other"]),
        ("HR", ["Other"]),
        ("Service", ["Tools"]),
    ]
    # Only once: listing again adds nothing.
    client.get("/api/v1/core/complaint-departments")
    issue_types = as_user("super").get("/api/v1/core/complaint-issue-types", params={"status": "all"}).json()
    assert sorted((t["departmentName"], t["name"]) for t in issue_types if t["departmentId"] in (3, 4, 5)) == [
        ("HR", "Other"),
        ("Store", "Racks"),
    ]


def test_raising_a_complaint_numbers_it_records_who_and_tells_the_department_leaders(
    as_user: Callable[[str], TestClient], db: Engine
) -> None:
    complaint = _raise(as_user("raju"))
    assert complaint["complaintNo"] == "BHADRAK/CMP/00001"
    assert complaint["status"] == "Open"
    assert complaint["departmentName"] == "Admin" and complaint["issueTypeName"] == "Water supply"
    assert complaint["raisedVia"] == "Android"
    raised_by = complaint["raisedBy"]
    assert (raised_by["userId"], raised_by["employeeCode"], raised_by["departmentName"]) == (11, "EMP0101", "Service")
    assert [(h["action"], h["toStatus"], h["changedByName"]) for h in complaint["history"]] == [
        ("Raised", "Open", "Raju")
    ]
    assert complaint["canManage"] is False and complaint["canAttach"] is True
    # The head (Meera, user 12) and the Admin department's manager (Sunil, user 13); not Asha (Service).
    assert _alerts(db) == [("CMP_COMPLAINT_RAISED", "Open", "New complaint BHADRAK/CMP/00001 to Admin", [12, 13])]
    assert _raise(as_user("raju"), "Second complaint about the water")["complaintNo"] == "BHADRAK/CMP/00002"


def test_the_number_comes_from_the_branch_even_when_the_employee_names_another_company(
    as_user: Callable[[str], TestClient], db: Engine
) -> None:
    # On RDS some employees' company differs from their branch's company: the series is the branch's.
    insert_row(db, "core.company", id=2, code="TREAD", legal_name="Trishul Tread Pvt Ltd")
    insert_row(
        db,
        "core.employee",
        id=106,
        company_id=2,
        branch_id=1,
        department_id=SERVICE,
        designation_id=1,
        employee_code="EMP0106",
        first_name="Mixed",
        mobile="9876543210",
        status="Active",
        is_active=True,
    )
    insert_row(db, "core.app_user", id=18, employee_id=106, username="mixed", is_active=True, is_locked=False)
    PEOPLE["mixed"] = make_user(id=18, employee_id=106, display_name="Mixed", permissions=frozenset())
    try:
        created = as_user("mixed").post(
            "/api/v1/core/complaints",
            json={"departmentId": ADMIN_DEPT, "issueTypeId": WATER, "description": "Fan not working"},
        )
    finally:
        PEOPLE.pop("mixed")
    assert created.status_code == 201, created.text
    assert created.json()["complaintNo"] == "BHADRAK/CMP/00001"
    with Session(db) as s:
        assert s.get(Complaint, created.json()["id"]).company_id == 1  # type: ignore[union-attr]


def test_an_issue_type_of_another_department_is_refused(as_user: Callable[[str], TestClient]) -> None:
    response = as_user("raju").post(
        "/api/v1/core/complaints",
        json={"departmentId": ADMIN_DEPT, "issueTypeId": SERVICE_TOOLS, "description": "Wrong issue type"},
    )
    assert response.status_code == 400
    assert "issueTypeId" in response.json()["errors"]


def test_a_short_description_or_unknown_field_is_refused(as_user: Callable[[str], TestClient]) -> None:
    client = as_user("raju")
    body = {"departmentId": ADMIN_DEPT, "issueTypeId": WATER}
    assert client.post("/api/v1/core/complaints", json=body | {"description": "bad"}).status_code == 422
    assert (
        client.post("/api/v1/core/complaints", json=body | {"description": "Fine text", "status": "Closed"}).status_code
        == 422
    )


def test_every_signed_in_user_may_raise_and_see_their_own_whatever_their_role(
    as_user: Callable[[str], TestClient],
) -> None:
    # "dev": an employee whose role has no complaint permission at all.
    client = as_user("norole")
    assert client.get("/api/v1/core/complaint-access").json()["canRaise"] is True
    assert client.get("/api/v1/core/complaint-departments").status_code == 200
    created = client.post(
        "/api/v1/core/complaints",
        json={"departmentId": ADMIN_DEPT, "issueTypeId": WATER, "description": "The canteen tap is leaking"},
    )
    assert created.status_code == 201, created.text
    mine = client.get("/api/v1/core/my-complaints").json()
    assert [c["complaintNo"] for c in mine["items"]] == [created.json()["complaintNo"]]
    assert client.get(f"/api/v1/core/complaints/{created.json()['id']}").status_code == 200


def test_without_a_head_the_departments_managers_are_told(as_user: Callable[[str], TestClient], db: Engine) -> None:
    response = as_user("raju").post(
        "/api/v1/core/complaints",
        json={"departmentId": SERVICE, "issueTypeId": SERVICE_TOOLS, "description": "Torque wrench is broken"},
    )
    assert response.status_code == 201
    # Asha (14) has core.complaint.manage in Service; Raju is in Service too but never told of his own complaint.
    assert _alerts(db)[0][3] == [14]


def test_a_department_with_no_leader_alerts_the_super_admins(as_user: Callable[[str], TestClient], db: Engine) -> None:
    insert_row(db, "hr.department", id=3, code="ACCOUNTS", name="Accounts")
    insert_row(db, "core.complaint_issue_type", id=4, department_id=3, name="Salary", sort_order=1)
    response = as_user("raju").post(
        "/api/v1/core/complaints", json={"departmentId": 3, "issueTypeId": 4, "description": "October salary is short"}
    )
    assert response.status_code == 201
    assert _alerts(db)[0][3] == [15]


# ---------------------------------------------------------------- who sees what


def test_my_complaints_shows_only_my_own(as_user: Callable[[str], TestClient]) -> None:
    _raise(as_user("raju"))
    _raise(as_user("sunil"), "The lift on the ground floor is stuck")
    mine = as_user("raju").get("/api/v1/core/my-complaints").json()
    assert mine["total"] == 1 and mine["items"][0]["raisedByUserId"] == 11


def test_department_leaders_see_their_department_only(as_user: Callable[[str], TestClient]) -> None:
    _raise(as_user("raju"))
    as_user("raju").post(
        "/api/v1/core/complaints",
        json={"departmentId": SERVICE, "issueTypeId": SERVICE_TOOLS, "description": "Torque wrench is broken"},
    )

    def departments(name: str) -> list[str]:
        response = as_user(name).get("/api/v1/core/complaints")
        assert response.status_code == 200, response.text
        return sorted(i["departmentName"] for i in response.json()["items"])

    assert departments("meera") == ["Admin"]  # head, no permission code needed
    assert departments("sunil") == ["Admin"]  # manage permission in the Admin department
    assert departments("other") == ["Service"]  # manage permission in Service
    assert departments("super") == ["Admin", "Service"]
    assert as_user("raju").get("/api/v1/core/complaints").status_code == 403


def test_access_says_which_departments_the_user_manages(as_user: Callable[[str], TestClient]) -> None:
    meera = as_user("meera").get("/api/v1/core/complaint-access").json()
    assert meera == {
        "canRaise": True,
        "canManageAll": False,
        "managedDepartments": [{"id": ADMIN_DEPT, "name": "Admin", "isHead": True}],
    }
    assert as_user("raju").get("/api/v1/core/complaint-access").json()["managedDepartments"] == []
    assert len(as_user("super").get("/api/v1/core/complaint-access").json()["managedDepartments"]) == 2


def test_me_gives_department_heads_the_manage_permission_for_the_menu(as_user: Callable[[str], TestClient]) -> None:
    assert "core.complaint.manage" in as_user("meera").get("/api/v1/me").json()["permissions"]
    assert "core.complaint.manage" not in as_user("raju").get("/api/v1/me").json()["permissions"]


def test_a_complaint_is_hidden_from_people_who_may_not_see_it(as_user: Callable[[str], TestClient]) -> None:
    complaint_id = _raise(as_user("raju"))["id"]
    assert as_user("other").get(f"/api/v1/core/complaints/{complaint_id}").status_code == 404
    leader_view = as_user("meera").get(f"/api/v1/core/complaints/{complaint_id}").json()
    assert leader_view["canManage"] is True
    assert leader_view["allowedStatuses"] == ["In Progress", "On Hold", "Resolved", "Closed"]
    assert leader_view["raisedBy"]["mobile"] == "9876543210"


# ---------------------------------------------------------------- status and history


def test_status_changes_and_notes_are_recorded_and_the_raiser_is_told(
    as_user: Callable[[str], TestClient], db: Engine
) -> None:
    complaint_id = _raise(as_user("raju"))["id"]
    url = f"/api/v1/core/complaints/{complaint_id}/status"
    started = as_user("sunil").post(url, json={"status": "In Progress"})
    assert started.status_code == 200, started.text
    noted = as_user("meera").post(url, json={"status": "In Progress", "note": "Plumber comes tomorrow at 10"})
    assert noted.status_code == 200
    resolved = as_user("sunil").post(url, json={"status": "Resolved", "note": "Pipe replaced"}).json()

    assert resolved["status"] == "Resolved" and resolved["resolvedAt"] is not None
    assert [
        (h["action"], h["fromStatus"], h["toStatus"], h["note"], h["changedByName"]) for h in resolved["history"]
    ] == [
        ("Raised", None, "Open", None, "Raju"),
        ("Status changed", "Open", "In Progress", None, "Sunil"),
        ("Note", "In Progress", "In Progress", "Plumber comes tomorrow at 10", "Meera"),
        ("Status changed", "In Progress", "Resolved", "Pipe replaced", "Sunil"),
    ]
    # The raiser sees the same history.
    mine = as_user("raju").get(f"/api/v1/core/complaints/{complaint_id}").json()
    assert len(mine["history"]) == 4 and mine["canManage"] is False and mine["canAttach"] is False

    alerts = _alerts(db)
    assert alerts[0][:2] == ("CMP_COMPLAINT_RAISED", "Resolved")  # taken up
    updates = [a for a in alerts if a[0] == "CMP_COMPLAINT_UPDATED"]
    assert [a[1] for a in updates] == ["Resolved", "Resolved", "Open"]  # only the latest update stays open
    assert updates[-1][2] == "Your complaint BHADRAK/CMP/00001 is Resolved" and updates[-1][3] == [11]


def test_the_raiser_and_other_departments_cannot_change_the_status(as_user: Callable[[str], TestClient]) -> None:
    complaint_id = _raise(as_user("raju"))["id"]
    url = f"/api/v1/core/complaints/{complaint_id}/status"
    assert as_user("raju").post(url, json={"status": "Closed"}).status_code == 403
    assert as_user("other").post(url, json={"status": "Closed"}).status_code == 404


def test_the_same_status_without_a_note_and_changes_after_closing_are_refused(
    as_user: Callable[[str], TestClient],
) -> None:
    complaint_id = _raise(as_user("raju"))["id"]
    url = f"/api/v1/core/complaints/{complaint_id}/status"
    leader = as_user("super")
    assert leader.post(url, json={"status": "Open"}).status_code == 400
    closed = leader.post(url, json={"status": "Closed", "note": "Duplicate of an earlier complaint"}).json()
    assert closed["closedAt"] is not None and closed["allowedStatuses"] == []
    assert leader.post(url, json={"status": "Open"}).status_code == 400
    assert leader.post(url, json={"status": "Closed", "note": "One more thing"}).status_code == 400


def test_a_stale_row_version_is_a_conflict(as_user: Callable[[str], TestClient], db: Engine) -> None:
    complaint = _raise(as_user("raju"))
    url = f"/api/v1/core/complaints/{complaint['id']}/status"
    with Session(db) as s:  # someone else changed it meanwhile (SQLite does not bump row_version itself)
        row = s.get(Complaint, complaint["id"])
        assert row is not None
        row.row_version = b"newer-v1"
        s.commit()
    response = as_user("meera").post(url, json={"status": "In Progress", "rowVersion": complaint["rowVersion"]})
    assert response.status_code == 409


def test_the_row_version_the_user_saw_is_accepted(as_user: Callable[[str], TestClient]) -> None:
    # Web and mobile send back the base64 rowVersion from the detail; it must match, not always conflict.
    complaint = _raise(as_user("raju"))
    url = f"/api/v1/core/complaints/{complaint['id']}/status"
    leader = as_user("meera")
    shown = leader.get(f"/api/v1/core/complaints/{complaint['id']}").json()
    response = leader.post(url, json={"status": "In Progress", "rowVersion": shown["rowVersion"]})
    assert response.status_code == 200, response.text
    assert leader.post(url, json={"status": "On Hold", "rowVersion": "not base64!"}).status_code == 422


def test_history_is_written_for_every_change(as_user: Callable[[str], TestClient], db: Engine) -> None:
    complaint_id = _raise(as_user("raju"))["id"]
    as_user("meera").post(f"/api/v1/core/complaints/{complaint_id}/status", json={"status": "On Hold", "note": "Parts"})
    with Session(db) as s:
        rows = s.scalars(select(ComplaintHistory).order_by(ComplaintHistory.id)).all()
        assert [(r.action, r.from_status, r.to_status, r.changed_by_user_id) for r in rows] == [
            ("Raised", None, "Open", 11),
            ("Status changed", "Open", "On Hold", 12),
        ]


def test_lists_filter_by_status_and_search(as_user: Callable[[str], TestClient]) -> None:
    first = _raise(as_user("raju"))["id"]
    _raise(as_user("raju"), "The lift on the ground floor is stuck")
    as_user("meera").post(f"/api/v1/core/complaints/{first}/status", json={"status": "Resolved"})
    client = as_user("meera")
    assert client.get("/api/v1/core/complaints", params={"openOnly": True}).json()["total"] == 1
    assert client.get("/api/v1/core/complaints", params={"status": ["Resolved"]}).json()["total"] == 1
    assert client.get("/api/v1/core/complaints", params={"search": "lift"}).json()["total"] == 1
    assert client.get("/api/v1/core/complaints", params={"search": "EMP0101"}).json()["total"] == 2
    assert client.get("/api/v1/core/complaints", params={"sort": "-nope"}).status_code == 400


# ---------------------------------------------------------------- attachments


def test_attachments_follow_the_complaint(as_user: Callable[[str], TestClient]) -> None:
    complaint_id = _raise(as_user("raju"))["id"]
    form = {"entityType": "core.complaint", "entityId": str(complaint_id), "category": "Photo"}
    photo = b"\xff\xd8\xff\xe0" + b"0" * 64
    uploaded = as_user("raju").post(
        "/api/v1/core/documents", data=form, files={"file": ("leak.jpg", photo, "image/jpeg")}
    )
    assert uploaded.status_code == 201, uploaded.text
    renamed_exe = as_user("raju").post(
        "/api/v1/core/documents", data=form, files={"file": ("leak.jpg", b"MZ\x90\x00", "image/jpeg")}
    )
    assert renamed_exe.status_code == 400
    params = {"entityType": "core.complaint", "entityId": complaint_id}
    assert len(as_user("meera").get("/api/v1/core/documents", params=params).json()) == 1
    assert as_user("other").get("/api/v1/core/documents", params=params).status_code == 404
    listed = as_user("meera").get("/api/v1/core/complaints").json()["items"][0]
    assert listed["attachmentCount"] == 1


def test_the_raiser_cannot_attach_once_the_complaint_is_resolved(as_user: Callable[[str], TestClient]) -> None:
    complaint_id = _raise(as_user("raju"))["id"]
    as_user("meera").post(f"/api/v1/core/complaints/{complaint_id}/status", json={"status": "Resolved"})
    form = {"entityType": "core.complaint", "entityId": str(complaint_id), "category": "Document"}
    pdf = b"%PDF-1.4 test"
    late = as_user("raju").post(
        "/api/v1/core/documents", data=form, files={"file": ("bill.pdf", pdf, "application/pdf")}
    )
    assert late.status_code == 403
    leader = as_user("meera").post(
        "/api/v1/core/documents", data=form, files={"file": ("work-done.pdf", pdf, "application/pdf")}
    )
    assert leader.status_code == 201


# ---------------------------------------------------------------- issue types


def test_super_admin_maintains_issue_types(as_user: Callable[[str], TestClient]) -> None:
    client = as_user("super")
    created = client.post(
        "/api/v1/core/complaint-issue-types", json={"departmentId": ADMIN_DEPT, "name": "Electricity", "sortOrder": 2}
    )
    assert created.status_code == 201, created.text
    item = created.json()
    duplicate = client.post(
        "/api/v1/core/complaint-issue-types", json={"departmentId": ADMIN_DEPT, "name": "Electricity"}
    )
    assert duplicate.status_code == 400
    off = client.patch(
        f"/api/v1/core/complaint-issue-types/{item['id']}",
        json={"isActive": False},
        headers={"If-Match": item["rowVersion"]},
    )
    assert off.status_code == 200 and off.json()["isActive"] is False
    names = [
        t["name"] for d in as_user("raju").get("/api/v1/core/complaint-departments").json() for t in d["issueTypes"]
    ]
    assert "Electricity" not in names
    assert as_user("meera").get("/api/v1/core/complaint-issue-types").status_code == 403
