"""Importing the spare-part price file into the item master: route -> service -> SQL (SQLite)."""

from io import BytesIO
from typing import Any

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.db.models import Item

from .sqlite_db import insert_row
from .test_inventory_api import API, COMPANY, SPARES, client, db  # noqa: F401  (fixtures)

PRINCIPAL = 1
HEADERS = {"X-Principal-Id": str(PRINCIPAL)}
HEADER_ROW = ["Sl No", "External ID (S4H)", "Material", "Description", "HSN Code", "ZAmount"]
# External ID, Material, Description, HSN, ZAmount
FILE_ROWS = [
    ("0000534", "534", "CASE;T.MISSION", "84314930", 120),  # existing item: new MRP, HSN added
    ("0000947280", "947280", "SEALING FELT", "Not assigned", 64),  # new, no HSN
    ("0000140021J", "0000140021J", "G/KIT OIL SUMP", "Not assigned", 0),  # new, no price, no HSN
    ("534", "534", "CASE;T.MISSION", "84314930", 130),  # the same part as the first row
    ("0001193", "1193", "SPINDLE", "99999999", 156137),  # new, HSN not in the master
    ("0000683", "683", "COVER", "84314930", 49418),  # new, with HSN
]


def workbook(rows: list[tuple[Any, ...]] = FILE_ROWS) -> bytes:
    sheet = Workbook().active
    assert sheet is not None
    sheet.append(HEADER_ROW)
    for number, row in enumerate(rows, start=1):
        sheet.append([number, *row])
    buffer = BytesIO()
    sheet.parent.save(buffer)
    return buffer.getvalue()


def upload(client: TestClient, path: str, content: bytes, **form: Any) -> Any:
    data = {"categoryId": str(SPARES), "priceField": "mrp", **form}
    files = {"file": ("prices.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    return client.post(f"{API}/items/{path}", files=files, data=data, headers=HEADERS)


def seed(db: Engine, client: TestClient) -> None:
    insert_row(db, "core.principal", id=PRINCIPAL, code="TATA_HITACHI", name="Tata Hitachi")
    insert_row(
        db, "core.item", id=500, company_id=COMPANY, item_code="CASE-534", description="Old name",
        oem_part_number="0000534", category_id=SPARES, uom_id=1, item_type="Stock", mrp=100, principal_id=PRINCIPAL,
    )  # fmt: skip
    assert client.post(f"{API}/hsn-codes", json={"code": "84314930", "gstPct": "18"}).status_code == 201


def test_preview_reports_what_would_change_and_saves_nothing(client: TestClient, db: Engine) -> None:
    seed(db, client)
    response = upload(client, "import/preview", workbook())
    assert response.status_code == 200, response.text
    body = response.json()
    summary = body["summary"]
    assert (summary["total"], summary["creates"], summary["updates"], summary["skips"]) == (6, 4, 1, 1)
    assert (summary["duplicates"], summary["missingHsn"], summary["unknownHsn"], summary["noPrice"]) == (1, 2, 1, 1)

    rows = {r["externalId"] + str(r["rowNumber"]): r for r in body["rows"]}
    existing = rows["00005342"]
    assert existing["action"] == "Update" and existing["itemCode"] == "CASE-534"
    assert existing["changes"] == ["MRP 100.00 → 120.00", "HSN 84314930 added"]
    repeat = next(r for r in body["rows"] if r["rowNumber"] == 5)
    assert repeat["action"] == "Skip" and [i["code"] for i in repeat["issues"]] == ["duplicateInFile"]
    unknown = next(r for r in body["rows"] if r["externalId"] == "0001193")
    assert [i["code"] for i in unknown["issues"]] == ["unknownHsn"]
    free = next(r for r in body["rows"] if r["externalId"] == "0000140021J")
    assert {i["code"] for i in free["issues"]} == {"missingHsn", "noPrice"}

    with Session(db) as s:
        assert len(s.scalars(select(Item)).all()) == 3  # the two fixture items and ours; nothing added


def test_import_creates_items_and_updates_prices_without_overwriting_with_zero(client: TestClient, db: Engine) -> None:
    seed(db, client)
    response = upload(client, "import", workbook())
    assert response.status_code == 201, response.text

    with Session(db) as s:
        items = {i.item_code: i for i in s.scalars(select(Item))}
        assert items["CASE-534"].mrp == 120 and items["CASE-534"].hsn_sac_id is not None
        assert items["CASE-534"].description == "Old name"  # the description is not overwritten
        felt = items["0000947280"]
        assert (felt.oem_part_number, felt.mrp, felt.hsn_sac_id, felt.principal_id) == ("0000947280", 64, None, PRINCIPAL)
        assert items["0000140021J"].mrp is None  # a zero price is not stored
        assert items["0000683"].hsn_sac_id is not None
        assert "534" not in items  # the repeat of 0000534 created nothing

    again = upload(client, "import", workbook()).json()["summary"]  # re-running changes nothing more
    assert (again["creates"], again["updates"]) == (0, 0)


def test_a_zero_price_never_overwrites_an_existing_price(client: TestClient, db: Engine) -> None:
    seed(db, client)
    rows = [("0000534", "534", "CASE;T.MISSION", "Not assigned", 0)]
    summary = upload(client, "import", workbook(rows)).json()["summary"]
    assert (summary["updates"], summary["unchanged"], summary["noPrice"]) == (0, 1, 1)
    with Session(db) as s:
        assert s.scalar(select(Item.mrp).where(Item.id == 500)) == 100


def test_the_price_can_go_to_the_standard_cost(client: TestClient, db: Engine) -> None:
    seed(db, client)
    upload(client, "import", workbook(FILE_ROWS[:1]), priceField="standardCost")
    with Session(db) as s:
        item = s.get(Item, 500)
        assert item is not None and item.standard_cost == 120 and item.mrp == 100


def test_the_import_needs_a_brand_a_category_and_the_right_file(client: TestClient, db: Engine) -> None:
    seed(db, client)
    files = {"file": ("p.xlsx", workbook(), "application/octet-stream")}
    assert client.post(f"{API}/items/import/preview", files=files).status_code == 400  # no brand selected
    no_category = {"file": ("p.xlsx", workbook(), "application/octet-stream")}
    response = client.post(f"{API}/items/import/preview", files=no_category, headers=HEADERS)
    assert response.status_code == 400 and "category" in response.json()["detail"].lower()
    assert upload(client, "import/preview", b"not a workbook").status_code == 400
    sheet = Workbook().active
    assert sheet is not None
    sheet.append(["Name", "Qty"])
    buffer = BytesIO()
    sheet.parent.save(buffer)
    assert upload(client, "import/preview", buffer.getvalue()).status_code == 400  # missing the columns
