"""Item list import (Excel / CSV into the item master) and its history: route -> service -> SQL (SQLite)."""

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user
from trishul_api.auth.deps import get_db
from trishul_api.config import Settings
from trishul_api.db.audit import set_audit_context
from trishul_api.db.models import AuditLog, Item, ItemImport
from trishul_api.main import create_app
from trishul_api.modules.core.documents import storage

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.principal",
    "core.branch",
    "core.uom",
    "core.hsn_sac",
    "core.item_category",
    "core.item",
    "core.app_user",
    "core.employee",
    "core.audit_log",
    "inv.item_import",
    "inv.item_import_line",
]
COMPANY, BRANCH = 1, 1
NOS, BOX = 1, 2
SPARES, OLD_CATEGORY = 31, 33
TATA, OTHER_BRAND = 1, 2
ACTOR, SOMEONE_ELSE = 1, 2
API = "/api/v1/inv/item-imports"
IMPORTER = {"inv.item.import", "inv.item.import.view", "inv.item.manage"}
ENTITY = "core.item"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEADER = ["Item Code *", "Description *", "Category Code *", "UOM Code", "Brand Code", "OEM Part Number", "MRP"]


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Engine:
    monkeypatch.setattr(storage, "_ROOT", tmp_path)
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TRISHUL", legal_name="Trishul", trade_name="Trishul")
    insert_row(engine, "core.branch", id=BRANCH, company_id=COMPANY, code="HO", name="Head office")
    insert_row(engine, "core.app_user", id=ACTOR, username="store.keeper", cognito_sub="a")
    insert_row(engine, "core.app_user", id=SOMEONE_ELSE, username="other.user", cognito_sub="b")
    insert_row(engine, "core.principal", id=TATA, code="TATA", name="Tata Hitachi")
    insert_row(engine, "core.principal", id=OTHER_BRAND, code="OTHER", name="Other brand")
    insert_row(engine, "core.uom", id=NOS, code="NOS", name="Numbers", decimals=0)
    insert_row(engine, "core.uom", id=BOX, code="BOX", name="Box", decimals=0, is_active=False)
    insert_row(engine, "core.hsn_sac", id=7, code="84212300", code_type="Goods", description="Filters")
    spare = {"item_nature": "Spare part", "default_uom_id": NOS, "default_hsn_sac_id": 7}
    insert_row(engine, "core.item_category", id=SPARES, code="SP", name="Spare parts", **spare)
    insert_row(engine, "core.item_category", id=OLD_CATEGORY, code="OLD", name="Old", is_active=False, **spare)
    existing = {"company_id": COMPANY, "category_id": SPARES, "uom_id": NOS, "item_type": "Stock"}
    insert_row(engine, "core.item", id=500, item_code="FIL-1", description="Old filter", mrp=100, principal_id=TATA,
               oem_part_number="4429729", **existing)  # fmt: skip
    insert_row(engine, "core.item", id=501, item_code="SECRET-1", description="Other brand part",
               principal_id=OTHER_BRAND, **existing)  # fmt: skip
    return engine


def make_client(settings: Settings, db: Engine, permissions: set[str], *, user_id: int = ACTOR) -> TestClient:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(
        id=user_id, permissions=frozenset(permissions), principal_ids=frozenset({TATA}), default_branch_id=BRANCH
    )
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=user_id, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with make_client(settings, db, IMPORTER) as test_client:
        yield test_client


def workbook(rows: list[list[Any]], header: list[str] = HEADER) -> bytes:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = "Items"
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def upload(client: TestClient, content: bytes, name: str = "items.xlsx", **form: str) -> Any:
    files = {"file": (name, content, XLSX)}
    return client.post(API, files=files, data=form)


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


ROWS: list[list[Any]] = [
    ["fil-2", "Fuel filter", "SP", "", "TATA", "111", 250],  # new (code upper-cased)
    ["FIL-1", "Old filter, new name", "SP", "", "TATA", "4429729", 120],  # exists: skipped
    ["FIL-2", "Fuel filter again", "SP", "", "TATA", "", 260],  # repeats row 2
    ["", "No code", "SP", "", "", "", ""],  # no item code
    ["OIL-1", "Engine oil", "XX", "BOX", "", "", "-5"],  # unknown category, inactive unit, negative MRP
    ["OIL-2", "Gear oil", "OLD", "", "OTHER", "", "abc"],  # inactive category, brand not allowed, not a number
    ["PART-9", "Same part, other code", "SP", "", "TATA", "4429729", 10],  # brand + OEM of FIL-1
    ["SECRET-1", "Someone else's code", "SP", "", "", "", ""],  # code of an item of a brand we can't see
    ["GREASE-1", "Grease", "SP", "NOS", "", "", "99.999"],  # new common item, MRP rounded
]


def test_upload_checks_every_row_and_changes_nothing(client: TestClient, db: Engine) -> None:
    batch = ok(upload(client, workbook(ROWS)), 201)
    assert batch["status"] == "Pending" and batch["batchNo"] == f"IMP-{batch['id']:06d}"
    assert (batch["totalRows"], batch["validCount"], batch["failedCount"], batch["skippedCount"]) == (9, 2, 4, 3)
    assert batch["canConfirm"] and batch["uploadedByName"] == "store.keeper" and batch["hasFile"]

    lines = {line["rowNumber"]: line for line in ok(client.get(f"{API}/{batch['id']}/lines?pageSize=50"))["items"]}
    assert lines[2]["action"] == "Create" and lines[2]["itemCode"] == "FIL-2" and lines[2]["outcome"] is None
    assert lines[3]["action"] == "Skip" and "Already exists" in lines[3]["messages"][0]
    assert lines[4]["action"] == "Skip" and "same Item Code as row 2" in lines[4]["messages"][0]
    assert lines[5]["messages"] == ["Item Code is required."]
    assert lines[6]["messages"] == [
        "Category 'XX' does not exist.",
        "UOM 'BOX' is inactive.",
        "MRP cannot be negative.",
    ]
    assert lines[7]["messages"] == [
        "Category 'OLD' is inactive.",
        "You do not have access to brand 'OTHER'.",
        "MRP 'abc' is not a number.",
    ]
    assert lines[8]["action"] == "Skip" and "same brand and OEM Part Number as row 3" in lines[8]["messages"][0]
    assert lines[9]["action"] == "Error" and "brand you do not have access to" in lines[9]["messages"][0]

    errors = ok(client.get(f"{API}/{batch['id']}/lines?status=Error"))
    assert errors["total"] == 4
    with Session(db) as s:
        assert len(s.scalars(select(Item)).all()) == 2  # nothing imported yet


def test_confirm_imports_only_the_valid_rows_once(client: TestClient, db: Engine) -> None:
    batch_id = ok(upload(client, workbook(ROWS)), 201)["id"]
    done = ok(client.post(f"{API}/{batch_id}/confirm"))
    assert done["status"] == "Partially Completed" and not done["canConfirm"]
    assert (done["createdCount"], done["updatedCount"], done["failedCount"], done["skippedCount"]) == (2, 0, 4, 3)

    with Session(db) as s:
        items = {i.item_code: i for i in s.scalars(select(Item))}
        fuel = items["FIL-2"]
        assert (fuel.description, fuel.principal_id, fuel.uom_id, fuel.hsn_sac_id) == ("Fuel filter", TATA, NOS, 7)
        assert fuel.mrp == 250 and fuel.created_by_user_id == ACTOR and fuel.is_active
        assert items["GREASE-1"].principal_id is None and float(items["GREASE-1"].mrp or 0) == 100.0
        assert items["FIL-1"].description == "Old filter"  # existing item not overwritten
        audited = s.scalars(select(AuditLog).where(AuditLog.entity_type == ENTITY, AuditLog.action == "Insert"))
        assert {(a.entity_id, a.changed_by_user_id) for a in audited} == {
            (fuel.id, ACTOR),
            (items["GREASE-1"].id, ACTOR),
        }

    created = ok(client.get(f"{API}/{batch_id}/lines?status=Created"))["items"]
    assert {line["itemCode"] for line in created} == {"FIL-2", "GREASE-1"} and all(line["itemId"] for line in created)
    again = client.post(f"{API}/{batch_id}/confirm")
    assert again.status_code == 409


def test_update_mode_needs_permission_and_only_fills_given_cells(settings: Settings, db: Engine) -> None:
    rows = [["FIL-1", "Better name", "SP", "", "TATA", "", 130]]
    plain = make_client(settings, db, IMPORTER)
    assert upload(plain, workbook(rows), duplicateMode="Update").status_code == 400

    admin = make_client(settings, db, IMPORTER | {"inv.item.import.overwrite"})
    batch = ok(upload(admin, workbook(rows), duplicateMode="Update"), 201)
    line = ok(admin.get(f"{API}/{batch['id']}/lines"))["items"][0]
    assert line["action"] == "Update"
    assert line["changes"] == [
        {"field": "Description", "from": "Old filter", "to": "Better name"},
        {"field": "MRP", "from": "100", "to": "130"},
    ]
    assert ok(admin.post(f"{API}/{batch['id']}/confirm"))["status"] == "Completed"

    with Session(db) as s:
        item = s.get(Item, 500)
        assert item is not None
        assert (item.description, item.mrp, item.oem_part_number) == ("Better name", 130, "4429729")  # blank kept
        assert item.updated_by_user_id == ACTOR


def test_only_the_uploader_can_confirm(settings: Settings, db: Engine, client: TestClient) -> None:
    batch_id = ok(upload(client, workbook(ROWS[:1])), 201)["id"]
    other = make_client(settings, db, IMPORTER, user_id=SOMEONE_ELSE)  # no `with`: that would close the database
    assert not ok(other.get(f"{API}/{batch_id}"))["canConfirm"]
    assert other.post(f"{API}/{batch_id}/confirm").status_code == 400


def test_bad_files_are_refused_or_logged_as_failed(client: TestClient) -> None:
    assert upload(client, b"%PDF-1.4", name="items.pdf").status_code == 400
    assert upload(client, b"not a zip", name="items.xlsx").status_code == 400  # not real Excel content

    no_header = ok(upload(client, workbook([["x"]], header=["Something", "Else"])), 201)
    assert no_header["status"] == "Failed" and "Item Code" in no_header["errorMessage"]
    missing = ok(upload(client, workbook([["A"]], header=["Item Code"])), 201)
    assert missing["status"] == "Failed" and "Description, Category Code" in missing["errorMessage"]
    nothing_valid = ok(upload(client, workbook([["", "x", "SP"]])), 201)
    assert nothing_valid["status"] == "Failed" and not nothing_valid["canConfirm"]


def test_csv_files_are_read_too(client: TestClient, db: Engine) -> None:
    content = "Item Code,Description,Category Code,Item Type,Active (Y/N)\nCSV-1,From CSV,sp,Non stock,N\n"
    batch = ok(upload(client, content.encode("utf-8-sig"), name="items.csv"), 201)
    assert batch["validCount"] == 1
    ok(client.post(f"{API}/{batch['id']}/confirm"))
    with Session(db) as s:
        item = s.scalar(select(Item).where(Item.item_code == "CSV-1"))
        assert item is not None and item.item_type == "Non stock" and item.is_active is False


def test_history_files_and_error_report(client: TestClient, db: Engine) -> None:
    content = workbook(ROWS)
    first = ok(upload(client, content, name="first.xlsx"), 201)
    ok(upload(client, workbook(ROWS[:1]), name="second.xlsx"), 201)
    ok(client.post(f"{API}/{first['id']}/confirm"))

    page = ok(client.get(API))
    assert [b["fileName"] for b in page["items"]] == ["second.xlsx", "first.xlsx"]
    assert ok(client.get(f"{API}?status=Pending"))["total"] == 1
    assert ok(client.get(f"{API}?search=first"))["items"][0]["id"] == first["id"]
    assert ok(client.get(f"{API}?sort=fileName"))["items"][0]["fileName"] == "first.xlsx"
    assert ok(client.get(f"{API}/uploaders")) == [{"id": ACTOR, "name": "store.keeper"}]

    original = client.get(f"{API}/{first['id']}/file")
    assert original.status_code == 200 and original.content == content
    assert 'filename="first.xlsx"' in original.headers["content-disposition"]

    report = client.get(f"{API}/{first['id']}/error-report")
    assert report.status_code == 200
    sheet = load_workbook(BytesIO(report.content)).active
    assert sheet is not None
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0][:4] == ("Row", "Result", "Problems", "Item Code")
    assert [r[0] for r in rows[1:]] == [3, 4, 5, 6, 7, 8, 9]  # every row not imported, with its reasons
    assert rows[1][1] == "Skipped" and rows[3][1] == "Failed"

    with Session(db) as s:
        assert s.get(ItemImport, first["id"]) is not None


def test_template_has_the_columns_and_the_valid_codes(client: TestClient) -> None:
    response = client.get(f"{API}/template")
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.content))
    assert book.sheetnames == ["Items", "Lists", "Instructions"]
    header = [c.value for c in book["Items"][1]]
    assert header[:3] == ["Item Code *", "Description *", "Category Code *"]
    lists = list(book["Lists"].iter_rows(values_only=True))
    assert lists[1][:2] == ("SP", "Spare parts")
    assert "OTHER" not in [r[6] for r in lists]  # only the user's brands
    assert "OLD" not in [r[0] for r in lists]  # only active categories

    # the template itself uploads cleanly once filled in
    book["Items"].append(["NEW-1", "From template", "SP"])
    buffer = BytesIO()
    book.save(buffer)
    assert ok(upload(client, buffer.getvalue()), 201)["validCount"] == 1


def test_permissions(settings: Settings, db: Engine) -> None:
    viewer = make_client(settings, db, {"inv.item.import.view"})
    assert viewer.get(API).status_code == 200
    assert viewer.get(f"{API}/template").status_code == 403
    assert upload(viewer, workbook(ROWS)).status_code == 403
    manager = make_client(settings, db, {"inv.item.manage"})
    assert manager.get(API).status_code == 403
