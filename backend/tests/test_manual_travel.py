"""Manual travel (Bus / Train / Other) and the common document module: route -> service -> SQL (SQLite)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import AuditLog
from trishul_api.main import create_app
from trishul_api.modules.core.documents import storage

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "core.principal",
    "core.customer",
    "core.employee",
    "core.app_user",
    "core.audit_log",
    "core.attachment",
    "svc.service_call",
    "svc.call_assignment",
    "trk.trip_vehicle_type",
    "trk.manual_travel",
]

COMPANY, BRANCH, PRINCIPAL, CUSTOMER = 1, 1, 1, 100
ENGINEER, OTHER_ENGINEER, REVIEWER_EMP = 300, 301, 302
TODAY = datetime.now(UTC).date()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
TRAVEL = "/api/v1/trk/manual-travel"
DOCS = "/api/v1/core/documents"


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
    for emp, first in ((ENGINEER, "Jyoti"), (OTHER_ENGINEER, "Parsuram"), (REVIEWER_EMP, "Lead")):
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
    for user_id, emp in ((1, ENGINEER), (2, OTHER_ENGINEER), (3, REVIEWER_EMP)):
        insert_row(
            engine, "core.app_user", id=user_id, username=f"user{user_id}", cognito_sub=f"sub{user_id}", employee_id=emp
        )
    for code, name, tracked, order in (
        ("Own bike", "Own bike", True, 1),
        ("Own car", "Own car", True, 2),
        ("Company vehicle", "Company vehicle", True, 3),
        ("Public transport", "Public transport", False, 4),
        ("Bus", "Bus", False, 5),
        ("Train", "Train", False, 6),
        ("Other", "Other", False, 7),
    ):
        insert_row(engine, "trk.trip_vehicle_type", code=code, name=name, sort_order=order, is_gps_tracked=tracked)
    insert_row(
        engine,
        "svc.service_call",
        id=24,
        company_id=COMPANY,
        branch_id=BRANCH,
        principal_id=PRINCIPAL,
        call_no="BHADRAK/SC/00024",
        customer_id=CUSTOMER,
        assigned_engineer_id=ENGINEER,
        current_status="Assigned",
    )
    return engine


def client_for(settings: Settings, db: Engine, user_id: int, employee_id: int, permissions: set[str]) -> TestClient:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(
        id=user_id,
        employee_id=employee_id,
        permissions=frozenset(permissions),
        default_branch_id=BRANCH,
        branch_ids=None,
        principal_ids=None,
    )
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=user_id, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def engineer(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, 1, ENGINEER, {"trk.trip.manage", "svc.call.view.assigned"}) as c:
        yield c


@pytest.fixture
def other(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, 2, OTHER_ENGINEER, {"trk.trip.manage", "svc.call.view.assigned"}) as c:
        yield c


@pytest.fixture
def reviewer(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, 3, REVIEWER_EMP, {"trk.trip.view.team", "svc.call.view"}) as c:
        yield c


def entry(**changes: Any) -> dict[str, Any]:
    return {
        "serviceCallId": 24,
        "vehicleType": "Bus",
        "travelDate": TODAY.isoformat(),
        "distanceKm": "42.5",
        "notes": "Bhubaneswar to Bhadrak by state bus",
    } | changes


def if_match(item: dict[str, Any]) -> dict[str, str]:
    return {"If-Match": f'"{item["rowVersion"]}"'}


def upload(client: TestClient, travel_id: int, name: str = "ticket.pdf", raw: bytes = PDF, **form: Any) -> Any:
    data = {"entityType": "trk.manual_travel", "entityId": str(travel_id), "category": "Document"} | form
    return client.post(DOCS, data=data, files={"file": (name, raw, "application/octet-stream")})


# ---------------------------------------------------------------- manual travel


@pytest.mark.parametrize("vehicle", ["Public transport", "Bus", "Train", "Other"])
def test_engineer_records_manual_travel_against_the_call(engineer: TestClient, vehicle: str) -> None:
    response = engineer.post(TRAVEL, json=entry(vehicleType=vehicle))
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["serviceCallId"], body["employeeId"], body["vehicleType"]) == (24, ENGINEER, vehicle)
    assert float(body["distanceKm"]) == 42.5
    assert body["employeeName"] == "Jyoti Das"
    assert body["documentCount"] == 0


@pytest.mark.parametrize("vehicle", ["Own bike", "Own car", "Company vehicle"])
def test_gps_vehicles_cannot_be_entered_by_hand(engineer: TestClient, vehicle: str) -> None:
    response = engineer.post(TRAVEL, json=entry(vehicleType=vehicle))
    assert response.status_code == 422
    assert "GPS" in response.json()["errors"]["vehicleType"][0]


def test_unknown_vehicle_type_is_rejected(engineer: TestClient) -> None:
    assert engineer.post(TRAVEL, json=entry(vehicleType="Jetpack")).status_code == 422


@pytest.mark.parametrize("distance", ["0", "-5", "5000.01", "abc"])
def test_distance_must_be_positive_and_realistic(engineer: TestClient, distance: str) -> None:
    assert engineer.post(TRAVEL, json=entry(distanceKm=distance)).status_code == 422


def test_travel_date_cannot_be_in_the_future_or_too_old(engineer: TestClient) -> None:
    future = (TODAY + timedelta(days=3)).isoformat()
    old = (TODAY - timedelta(days=120)).isoformat()
    assert "travelDate" in engineer.post(TRAVEL, json=entry(travelDate=future)).json()["errors"]
    assert "travelDate" in engineer.post(TRAVEL, json=entry(travelDate=old)).json()["errors"]


def test_unknown_fields_are_rejected(engineer: TestClient) -> None:
    assert engineer.post(TRAVEL, json=entry(employeeId=OTHER_ENGINEER)).status_code == 422  # mass assignment


def test_only_an_engineer_on_the_call_can_record_travel(other: TestClient) -> None:
    assert other.post(TRAVEL, json=entry()).status_code == 404


def test_recording_needs_the_trip_permission(settings: Settings, db: Engine) -> None:
    with client_for(settings, db, 1, ENGINEER, {"svc.call.view"}) as client:
        assert client.post(TRAVEL, json=entry()).status_code == 403


def test_retried_save_returns_the_same_entry(engineer: TestClient) -> None:
    key = str(uuid4())
    first = engineer.post(TRAVEL, json=entry(clientUuid=key))
    second = engineer.post(TRAVEL, json=entry(clientUuid=key))
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(engineer.get("/api/v1/svc/service-calls/24/manual-travel").json()) == 1


def test_engineer_corrects_and_removes_their_entry(engineer: TestClient) -> None:
    created = engineer.post(TRAVEL, json=entry()).json()
    body = {k: entry()[k] for k in ("vehicleType", "travelDate", "distanceKm", "notes")} | {"distanceKm": "55"}
    updated = engineer.put(f"{TRAVEL}/{created['id']}", json=body, headers=if_match(created))
    assert updated.status_code == 200, updated.text
    assert float(updated.json()["distanceKm"]) == 55
    # (A stale If-Match gives 409 on SQL Server; SQLite has no rowversion, so that is not asserted here.)
    assert engineer.delete(f"{TRAVEL}/{created['id']}", headers=if_match(updated.json())).status_code == 204
    assert engineer.get(f"{TRAVEL}/{created['id']}").status_code == 404


def test_call_list_shows_own_entries_to_engineers_and_everyones_to_reviewers(
    engineer: TestClient, reviewer: TestClient
) -> None:
    engineer.post(TRAVEL, json=entry(vehicleType="Train", distanceKm="120"))
    url = "/api/v1/svc/service-calls/24/manual-travel"
    assert [t["vehicleType"] for t in engineer.get(url).json()] == ["Train"]
    assert [t["employeeName"] for t in reviewer.get(url).json()] == ["Jyoti Das"]


def test_a_reviewer_cannot_change_an_engineers_entry(engineer: TestClient, reviewer: TestClient) -> None:
    created = engineer.post(TRAVEL, json=entry()).json()
    body = {k: entry()[k] for k in ("vehicleType", "travelDate", "distanceKm", "notes")}
    assert reviewer.get(f"{TRAVEL}/{created['id']}").status_code == 200
    assert reviewer.put(f"{TRAVEL}/{created['id']}", json=body, headers=if_match(created)).status_code in (403, 404)


# ---------------------------------------------------------------- common documents


def test_ticket_is_attached_through_the_common_document_module(engineer: TestClient, storage_dir: Path) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    response = upload(engineer, travel["id"], name="Bus ticket.pdf", category="Invoice")
    assert response.status_code == 201, response.text
    doc = response.json()
    assert (doc["entityType"], doc["entityId"], doc["category"]) == ("trk.manual_travel", travel["id"], "Invoice")
    assert doc["fileName"] == "Bus ticket.pdf"
    assert doc["contentType"] == "application/pdf"
    assert doc["fileSizeBytes"] == len(PDF)
    assert doc["uploadedByName"] == "Jyoti Das"
    assert doc["canDelete"] is True
    assert any(storage_dir.rglob("*.pdf"))
    shown = engineer.get(f"{TRAVEL}/{travel['id']}").json()
    assert shown["documentCount"] == 1
    assert shown["documents"] == [{"id": doc["id"], "fileName": "Bus ticket.pdf", "contentType": "application/pdf"}]


def test_documents_are_listed_viewed_and_downloaded(engineer: TestClient) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    upload(engineer, travel["id"], name="a.pdf")
    doc = upload(engineer, travel["id"], name="b.png", raw=PNG).json()
    listed = engineer.get(DOCS, params={"entityType": "trk.manual_travel", "entityId": travel["id"]}).json()
    assert [d["fileName"] for d in listed] == ["a.pdf", "b.png"]
    download = engineer.get(f"{DOCS}/{doc['id']}/content")
    assert download.content == PNG
    assert download.headers["content-disposition"].startswith("attachment")
    inline = engineer.get(f"{DOCS}/{doc['id']}/content", params={"inline": True})
    assert inline.headers["content-disposition"].startswith("inline")
    assert inline.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    ("name", "raw", "message"),
    [
        ("virus.exe", b"MZ\x90\x00", "Only PDF"),
        ("notes.txt", b"hello", "Only PDF"),
        ("fake.pdf", b"MZ not a pdf", "not a valid PDF"),
        ("fake.png", PDF, "not a valid PNG"),
        ("empty.pdf", b"", "empty"),
    ],
)
def test_only_real_pdf_jpg_png_files_are_accepted(engineer: TestClient, name: str, raw: bytes, message: str) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    response = upload(engineer, travel["id"], name=name, raw=raw)
    assert response.status_code == 400
    assert message in response.json()["detail"]


def test_files_over_10_mb_are_refused(engineer: TestClient) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    big = PDF + b"0" * (storage.MAX_BYTES + 1)
    assert upload(engineer, travel["id"], raw=big).status_code == 400


def test_path_tricks_in_the_file_name_are_neutralised(engineer: TestClient, storage_dir: Path) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    doc = upload(engineer, travel["id"], name="..\\..\\evil/../ticket.pdf").json()
    assert doc["fileName"] == "ticket.pdf"
    assert all(storage_dir in p.parents for p in storage_dir.rglob("*") if p.is_file())


def test_unregistered_record_types_cannot_hold_documents(engineer: TestClient) -> None:
    response = upload(engineer, 1, entityType="sal.sales_invoice")
    assert response.status_code == 400


def test_other_engineers_cannot_see_or_change_the_documents(engineer: TestClient, other: TestClient) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    doc = upload(engineer, travel["id"]).json()
    assert other.get(DOCS, params={"entityType": "trk.manual_travel", "entityId": travel["id"]}).status_code == 404
    assert other.get(f"{DOCS}/{doc['id']}/content").status_code == 404
    assert upload(other, travel["id"]).status_code == 404


def test_reviewer_can_view_but_not_change_documents(engineer: TestClient, reviewer: TestClient) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    doc = upload(engineer, travel["id"]).json()
    listed = reviewer.get(DOCS, params={"entityType": "trk.manual_travel", "entityId": travel["id"]}).json()
    assert [d["canDelete"] for d in listed] == [False]
    assert reviewer.get(f"{DOCS}/{doc['id']}/content").content == PDF
    assert upload(reviewer, travel["id"]).status_code == 403
    assert reviewer.delete(f"{DOCS}/{doc['id']}", headers=if_match(doc)).status_code == 403


def test_document_can_be_renamed_and_removed(engineer: TestClient, storage_dir: Path, db: Engine) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    doc = upload(engineer, travel["id"], name="ticket.pdf").json()
    renamed = engineer.patch(
        f"{DOCS}/{doc['id']}", json={"fileName": "Train ticket.pdf", "category": "Invoice"}, headers=if_match(doc)
    )
    assert renamed.status_code == 200, renamed.text
    assert (renamed.json()["fileName"], renamed.json()["category"]) == ("Train ticket.pdf", "Invoice")
    changed_type = engineer.patch(
        f"{DOCS}/{doc['id']}", json={"fileName": "ticket.png"}, headers=if_match(renamed.json())
    )
    assert changed_type.status_code == 400  # a document keeps its file type

    assert engineer.delete(f"{DOCS}/{doc['id']}", headers=if_match(renamed.json())).status_code == 204
    assert not any(storage_dir.rglob("*.pdf"))
    assert engineer.get(DOCS, params={"entityType": "trk.manual_travel", "entityId": travel["id"]}).json() == []
    assert engineer.get(f"{TRAVEL}/{travel['id']}").json()["documentCount"] == 0
    with Session(db) as session:  # the audit trail records who uploaded and removed it
        actions = [a.action for a in session.scalars(select(AuditLog).where(AuditLog.entity_type == "core.attachment"))]
    assert "Insert" in actions
    assert "Update" in actions


def test_removing_the_entry_removes_its_documents(engineer: TestClient, storage_dir: Path) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    upload(engineer, travel["id"])
    assert engineer.delete(f"{TRAVEL}/{travel['id']}", headers=if_match(travel)).status_code == 204
    assert not any(storage_dir.rglob("*.pdf"))


# ---------------------------------------------------------------- Administration > Documents library

LIBRARY = f"{DOCS}/library"


@pytest.fixture
def admin(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, 4, REVIEWER_EMP, {"core.document.view", "core.document.manage"}) as c:
        yield c


@pytest.fixture
def viewer(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, 5, REVIEWER_EMP, {"core.document.view"}) as c:
        yield c


def test_library_lists_every_document_with_its_record(engineer: TestClient, admin: TestClient) -> None:
    mine = engineer.post(TRAVEL, json=entry()).json()
    upload(engineer, mine["id"], name="bus.pdf", category="Invoice")
    upload(engineer, mine["id"], name="photo.png", raw=PNG, category="Photo")
    page = admin.get(LIBRARY).json()
    assert page["total"] == 2
    first = page["items"][0]  # newest first
    assert first["fileName"] == "photo.png"
    assert first["entityType"] == "trk.manual_travel"
    assert first["entityLabel"] == "Manual travel"
    assert first["recordLabel"].startswith("BHADRAK/SC/00024 · Bus · ")
    assert first["uploadedByName"] == "Jyoti Das"
    assert first["canDelete"] is True


def test_library_filters_by_type_category_name_and_dates(engineer: TestClient, admin: TestClient) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    upload(engineer, travel["id"], name="bus ticket.pdf", category="Invoice")
    upload(engineer, travel["id"], name="selfie.png", raw=PNG, category="Photo")

    def names(**params: Any) -> list[str]:
        return sorted(d["fileName"] for d in admin.get(LIBRARY, params=params).json()["items"])

    assert names(category="Photo") == ["selfie.png"]
    assert names(search="ticket") == ["bus ticket.pdf"]
    assert names(entityType="trk.manual_travel") == ["bus ticket.pdf", "selfie.png"]
    assert names(entityType="core.employee") == []
    assert names(uploadedFrom=TODAY.isoformat(), uploadedTo=TODAY.isoformat()) == ["bus ticket.pdf", "selfie.png"]
    assert names(uploadedTo=(TODAY - timedelta(days=1)).isoformat()) == []


def test_library_pages_and_sorts(engineer: TestClient, admin: TestClient) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    for name in ("b.pdf", "a.pdf", "c.pdf"):
        upload(engineer, travel["id"], name=name)
    page = admin.get(LIBRARY, params={"page": 2, "pageSize": 2, "sort": "fileName"}).json()
    assert (page["total"], page["page"], [d["fileName"] for d in page["items"]]) == (3, 2, ["c.pdf"])
    desc = admin.get(LIBRARY, params={"sort": "-fileName"}).json()["items"]
    assert [d["fileName"] for d in desc] == ["c.pdf", "b.pdf", "a.pdf"]


def test_library_needs_the_document_permission(engineer: TestClient, other: TestClient) -> None:
    assert engineer.get(LIBRARY).status_code == 403
    assert other.get(f"{DOCS}/entity-types").status_code == 403


def test_entity_types_name_the_modules_that_use_documents(admin: TestClient) -> None:
    types = {t["entityType"]: t["label"] for t in admin.get(f"{DOCS}/entity-types").json()}
    assert types == {
        "core.customer": "Customer",
        "core.employee": "Employee",
        "svc.service_call": "Service call",
        "trk.manual_travel": "Manual travel",
    }


def test_removed_documents_leave_the_library(engineer: TestClient, admin: TestClient) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    doc = upload(engineer, travel["id"]).json()
    engineer.delete(f"{DOCS}/{doc['id']}", headers=if_match(doc))
    assert admin.get(LIBRARY).json()["total"] == 0


def test_administrator_views_adds_and_removes_documents_of_any_record(
    engineer: TestClient, admin: TestClient, storage_dir: Path
) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    doc = upload(engineer, travel["id"]).json()
    assert admin.get(f"{DOCS}/{doc['id']}/content").content == PDF  # not their record, still viewable
    added = upload(admin, travel["id"], name="from-admin.pdf")  # the Documents page uploads to any record
    assert added.status_code == 201, added.text
    item = next(d for d in admin.get(LIBRARY).json()["items"] if d["fileName"] != "from-admin.pdf")
    renamed = admin.patch(f"{DOCS}/{item['id']}", json={"fileName": "checked.pdf"}, headers=if_match(item))
    assert renamed.status_code == 200, renamed.text
    assert admin.delete(f"{DOCS}/{item['id']}", headers=if_match(renamed.json())).status_code == 204
    assert len(list(storage_dir.rglob("*.pdf"))) == 1  # only the one the administrator added is left


def test_view_only_administrator_cannot_change_documents(engineer: TestClient, viewer: TestClient) -> None:
    travel = engineer.post(TRAVEL, json=entry()).json()
    doc = upload(engineer, travel["id"]).json()
    item = viewer.get(LIBRARY).json()["items"][0]
    assert item["canDelete"] is False
    assert viewer.get(f"{DOCS}/{doc['id']}/content").status_code == 200
    assert viewer.delete(f"{DOCS}/{doc['id']}", headers=if_match(item)).status_code == 403
