"""Common document module across modules: formats, record search and per-module access (SQLite)."""

import io
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
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
]
DOCS = "/api/v1/core/documents"
LIBRARY = f"{DOCS}/library"
COMPANY, BRANCH, PRINCIPAL, CUSTOMER = 1, 1, 1, 100
ENGINEER, OTHER_ENGINEER = 300, 301

PDF = b"%PDF-1.4\n%%EOF"


def office(kind: str, extra: tuple[str, ...] = ()) -> bytes:
    """A minimal valid .docx ("word") or .xlsx ("xl")."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in ("[Content_Types].xml", f"{kind}/main.xml", *extra):
            archive.writestr(name, "x")
    return buffer.getvalue()


OLE = bytes.fromhex("d0cf11e0a1b11ae1") + b"\x00" * 64


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
        name="Blue Earth Movers",
        customer_type="Company",
        primary_phone="9000000000",
    )
    insert_row(
        engine,
        "core.customer",
        id=101,
        company_id=COMPANY,
        code="C101",
        name="Real Customer Ltd",
        customer_type="Company",
        primary_phone="9111111111",
    )
    for emp, first in ((ENGINEER, "Jyoti"), (OTHER_ENGINEER, "Parsuram")):
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
    for user_id in (1, 2, 3, 4):
        insert_row(engine, "core.app_user", id=user_id, username=f"user{user_id}", cognito_sub=f"sub{user_id}")
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
    insert_row(
        engine,
        "svc.service_call",
        id=25,
        company_id=COMPANY,
        branch_id=BRANCH,
        principal_id=PRINCIPAL,
        call_no="BHADRAK/SC/00025",
        customer_id=101,
        assigned_engineer_id=OTHER_ENGINEER,
        current_status="Assigned",
    )
    return engine


def client_for(
    settings: Settings, db: Engine, user_id: int, employee_id: int | None, permissions: set[str]
) -> TestClient:
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
def admin(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, 1, None, {"core.document.view", "core.document.manage"}) as c:
        yield c


@pytest.fixture
def engineer(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, 2, ENGINEER, {"svc.call.view.assigned"}) as c:
        yield c


@pytest.fixture
def customer_clerk(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, 3, None, {"core.customer.view"}) as c:
        yield c


@pytest.fixture
def customer_manager(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, 4, None, {"core.customer.view", "core.customer.manage"}) as c:
        yield c


def upload(
    client: TestClient, entity_type: str, entity_id: int, name: str = "a.pdf", raw: bytes = PDF, **form: Any
) -> Any:
    data = {"entityType": entity_type, "entityId": str(entity_id), "category": "Document"} | form
    return client.post(DOCS, data=data, files={"file": (name, raw, "application/octet-stream")})


def if_match(item: dict[str, Any]) -> dict[str, str]:
    return {"If-Match": f'"{item["rowVersion"]}"'}


# ---------------------------------------------------------------- file formats


@pytest.mark.parametrize(
    ("name", "raw", "content_type"),
    [
        ("report.pdf", PDF, "application/pdf"),
        ("letter.docx", office("word"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("sheet.xlsx", office("xl"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("old.doc", OLE, "application/msword"),
        ("old.xls", OLE, "application/vnd.ms-excel"),
        ("photo.jpg", b"\xff\xd8\xff\xe0" + b"0" * 8, "image/jpeg"),
        ("pic.png", b"\x89PNG\r\n\x1a\n" + b"0" * 8, "image/png"),
        ("anim.gif", b"GIF89a" + b"0" * 8, "image/gif"),
        ("web.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
    ],
)
def test_pdf_word_excel_and_image_files_are_accepted(
    admin: TestClient, name: str, raw: bytes, content_type: str
) -> None:
    response = upload(admin, "core.customer", CUSTOMER, name=name, raw=raw)
    assert response.status_code == 201, response.text
    assert response.json()["contentType"] == content_type
    assert response.json()["fileName"] == name


@pytest.mark.parametrize(
    ("name", "raw", "message"),
    [
        ("macro.xlsm", office("xl"), "Only PDF, Word"),
        ("tool.exe", b"MZ\x90\x00", "Only PDF, Word"),
        ("page.html", b"<html>", "Only PDF, Word"),
        ("fake.docx", b"PK\x03\x04 not really", "not a valid Word"),
        ("fake.xlsx", PDF, "not a valid Excel"),
        ("renamed.xlsx", office("word"), "not a valid Excel"),  # a docx renamed to xlsx
        ("fake.doc", b"hello", "not a valid Word"),
        ("macros.docx", office("word", ("word/vbaProject.bin",)), "macros"),
        ("fake.webp", b"RIFF\x00\x00\x00\x00AVI ", "not a valid WebP"),
    ],
)
def test_renamed_or_dangerous_files_are_refused(admin: TestClient, name: str, raw: bytes, message: str) -> None:
    response = upload(admin, "core.customer", CUSTOMER, name=name, raw=raw)
    assert response.status_code == 400
    assert message in response.json()["detail"]


# ---------------------------------------------------------------- the Documents page uploads to any record


def test_administrator_attaches_documents_to_service_calls_customers_and_employees(admin: TestClient) -> None:
    for entity_type, entity_id in (("svc.service_call", 24), ("core.customer", CUSTOMER), ("core.employee", ENGINEER)):
        assert upload(admin, entity_type, entity_id).status_code == 201, entity_type
    items = {d["entityType"]: d for d in admin.get(LIBRARY).json()["items"]}
    assert items["svc.service_call"]["recordLabel"] == "BHADRAK/SC/00024 · Blue Earth Movers"
    assert items["core.customer"]["recordLabel"] == "Blue Earth Movers (C100)"
    assert items["core.employee"]["recordLabel"] == "Jyoti Das (E300)"
    assert {d["entityLabel"] for d in items.values()} == {"Service call", "Customer", "Employee"}


def test_unknown_record_is_not_found(admin: TestClient) -> None:
    assert upload(admin, "core.customer", 9999).status_code == 404
    assert upload(admin, "svc.service_call", 9999).status_code == 404


def test_employee_photos_are_not_documents(admin: TestClient, db: Engine) -> None:
    insert_row(
        db,
        "core.attachment",
        entity_type="core.employee",
        entity_id=ENGINEER,
        category="Photo",
        file_name="photo.jpg",
        content_type="image/jpeg",
        file_size_bytes=10,
        s3_key="employees/300/photo.jpg",
    )
    assert admin.get(LIBRARY).json()["total"] == 0
    assert admin.get(DOCS, params={"entityType": "core.employee", "entityId": ENGINEER}).json() == []
    assert upload(admin, "core.employee", ENGINEER, category="Photo").status_code == 400
    assert upload(admin, "core.employee", ENGINEER, category="Document").status_code == 201
    assert admin.get(LIBRARY).json()["total"] == 1
    photo_id = 1
    assert admin.get(f"{DOCS}/{photo_id}/content").status_code == 404  # the photo is not reachable here


# ---------------------------------------------------------------- record search


def test_record_search_finds_records_by_name_or_number(admin: TestClient) -> None:
    def find(entity_type: str, text: str = "") -> list[str]:
        response = admin.get(f"{DOCS}/records", params={"entityType": entity_type, "search": text})
        assert response.status_code == 200, response.text
        return [r["label"] for r in response.json()]

    assert find("core.customer", "blue") == ["Blue Earth Movers (C100)"]
    assert find("core.customer", "C101") == ["Real Customer Ltd (C101)"]
    assert find("svc.service_call", "00025") == ["BHADRAK/SC/00025 · Real Customer Ltd"]
    assert find("svc.service_call", "blue") == ["BHADRAK/SC/00024 · Blue Earth Movers"]
    assert find("core.employee", "parsu") == ["Parsuram Das (E301)"]
    assert find("core.employee", "E30") == ["Jyoti Das (E300)", "Parsuram Das (E301)"]
    assert len(find("core.customer")) == 2  # an empty search lists the first records


def test_record_search_treats_wildcards_as_text(admin: TestClient) -> None:
    assert admin.get(f"{DOCS}/records", params={"entityType": "core.customer", "search": "%"}).json() == []


def test_record_search_is_for_document_administrators(engineer: TestClient, customer_manager: TestClient) -> None:
    assert engineer.get(f"{DOCS}/records", params={"entityType": "svc.service_call"}).status_code == 403
    assert customer_manager.get(f"{DOCS}/records", params={"entityType": "core.customer"}).status_code == 403


def test_record_search_rejects_unknown_modules(admin: TestClient) -> None:
    assert admin.get(f"{DOCS}/records", params={"entityType": "sal.sales_invoice"}).status_code == 400


# ---------------------------------------------------------------- each module's own access rules


def test_engineer_attaches_to_their_own_call_only(engineer: TestClient) -> None:
    assert upload(engineer, "svc.service_call", 24).status_code == 201
    assert upload(engineer, "svc.service_call", 25).status_code == 404  # assigned to someone else
    assert engineer.get(DOCS, params={"entityType": "svc.service_call", "entityId": 25}).status_code == 404
    assert len(engineer.get(DOCS, params={"entityType": "svc.service_call", "entityId": 24}).json()) == 1


def test_customer_documents_follow_the_customer_permissions(
    customer_clerk: TestClient, customer_manager: TestClient, admin: TestClient
) -> None:
    doc = upload(admin, "core.customer", CUSTOMER).json()
    listed = customer_clerk.get(DOCS, params={"entityType": "core.customer", "entityId": CUSTOMER}).json()
    assert [d["canDelete"] for d in listed] == [False]  # view only
    assert upload(customer_clerk, "core.customer", CUSTOMER).status_code == 403
    assert customer_clerk.delete(f"{DOCS}/{doc['id']}", headers=if_match(doc)).status_code == 403
    assert upload(customer_manager, "core.customer", CUSTOMER).status_code == 201


def test_people_without_any_customer_permission_see_nothing(engineer: TestClient, admin: TestClient) -> None:
    upload(admin, "core.customer", CUSTOMER)
    assert engineer.get(DOCS, params={"entityType": "core.customer", "entityId": CUSTOMER}).status_code == 404


def test_library_filters_by_the_new_modules(admin: TestClient) -> None:
    upload(admin, "core.customer", CUSTOMER, name="c.pdf")
    upload(admin, "svc.service_call", 24, name="s.pdf")
    only = admin.get(LIBRARY, params={"entityType": "svc.service_call"}).json()["items"]
    assert [d["fileName"] for d in only] == ["s.pdf"]
