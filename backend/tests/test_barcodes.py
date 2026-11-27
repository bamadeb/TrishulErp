"""Warehouse storage, phase 2: optional item barcodes, the scan / find lookup and barcode labels."""

# ruff: noqa: F811  (the inventory fixtures are imported, then used as test arguments)

import re
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from trishul_api.config import Settings
from trishul_api.db.models import Item, ScanLog
from trishul_api.modules.inv.common import age_parts, age_text

from .test_inventory_api import (
    ALL_PERMISSIONS,
    API,
    FILTER_ITEM,
    OIL_ITEM,
    PUR,
    RACK_A1,
    SUPPLIER,
    WH_MAIN,
    db,  # noqa: F401  (fixture)
    line,
    make_client,
    ok,
)

MANAGE = ALL_PERMISSIONS | {"inv.barcode.manage"}
EAN = "4006381333931"  # a valid EAN-13


def barcodes(client: TestClient, item: int = FILTER_ITEM) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = ok(client.get(f"{API}/items/{item}/barcodes"))
    return result


def add(client: TestClient, item: int = FILTER_ITEM, **body: Any) -> Any:
    return client.post(f"{API}/items/{item}/barcodes", json={"barcode": EAN, "barcodeType": "EAN13", **body})


def scan(client: TestClient, code: str) -> dict[str, Any]:
    result: dict[str, Any] = ok(client.get(f"{API}/scan", params={"code": code, "screen": "test"}))
    return result


def test_barcodes_are_optional_validated_and_unique(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, MANAGE)
    assert barcodes(client) == []  # an item needs no barcode

    first = ok(add(client))
    assert (first["barcode"], first["source"], first["isPrimary"], Decimal(first["packQty"])) == (
        EAN, "Manufacturer", True, 1,
    )  # fmt: skip
    assert add(client).status_code == 409  # already registered
    assert add(client, OIL_ITEM).status_code == 409  # one barcode, one item
    wrong = add(client, barcode="4006381333932")
    assert wrong.status_code == 400 and "check digit" in wrong.json()["detail"]
    assert add(client, barcode="12345").status_code == 400  # EAN-13 is 13 digits
    own_code = add(client, barcode="FLT-01", barcodeType="Code128")
    assert own_code.status_code == 400 and "already works as its barcode" in own_code.json()["detail"]
    assert add(client, barcode="OIL-15W40", barcodeType="Code128").status_code == 400  # another item's code
    assert add(client, barcode="A1", barcodeType="Code128").status_code == 400  # a bin code

    box = ok(add(client, barcode="BOX-100-FLT", barcodeType="Code128", packQty="100", isPrimary=True))
    listed = {b["barcode"]: b for b in barcodes(client)}
    assert listed["BOX-100-FLT"]["isPrimary"] and not listed[EAN]["isPrimary"]  # one primary per item

    off = ok(
        client.patch(
            f"{API}/item-barcodes/{box['id']}", json={"isActive": False}, headers={"If-Match": box["rowVersion"]}
        )
    )
    assert (off["isActive"], off["isPrimary"]) == (False, False)


def test_internal_barcode_only_when_asked_and_none_exists(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, MANAGE)
    internal = ok(client.post(f"{API}/items/{OIL_ITEM}/generate-barcode"))
    assert (internal["barcode"], internal["source"], internal["isPrimary"]) == (
        f"TR{OIL_ITEM:08d}", "Internal", True,
    )  # fmt: skip
    assert client.post(f"{API}/items/{OIL_ITEM}/generate-barcode").status_code == 400  # it has one now


def test_scan_finds_items_bins_and_unknown_codes(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, MANAGE)
    ok(add(client, barcode="BOX-100-FLT", barcodeType="Code128", packQty="100"))
    receipt = {"locationId": WH_MAIN, "supplierId": SUPPLIER, "grnDate": date.today().isoformat()}
    ok(client.post(f"{PUR}/grns", json={**receipt, "lines": [line(quantity="5", binId=RACK_A1)]}), 201)

    by_code = scan(client, "flt-01")  # typed in lower case
    assert by_code["resolvedType"] == "Item" and by_code["matches"][0]["via"] == "Item code"
    assert [(r["binCode"], Decimal(r["qtyOnHand"])) for r in by_code["stock"]] == [("A1", 5)]

    by_box = scan(client, "BOX-100-FLT")
    assert by_box["matches"][0]["via"] == "Manufacturer barcode"
    assert Decimal(by_box["matches"][0]["packQty"]) == 100

    with Session(db) as s:
        s.execute(update(Item).where(Item.id.in_([FILTER_ITEM, OIL_ITEM])).values(oem_part_number="4429729"))
        s.commit()
    shared = scan(client, "4429729")  # a part number two items share: the user chooses
    assert shared["resolvedType"] == "Many" and len(shared["matches"]) == 2 and shared["stock"] == []

    bin_ = scan(client, "a1")
    assert bin_["resolvedType"] == "Bin" and [r["itemCode"] for r in bin_["stock"]] == ["FLT-01"]
    assert scan(client, "WH-MAIN")["resolvedType"] == "Location"

    unknown = scan(client, "8901234567890")
    assert (unknown["resolvedType"], unknown["matches"]) == ("Unknown", [])
    with Session(db) as s:
        logged = s.scalars(select(ScanLog).order_by(ScanLog.id)).all()
        assert [(x.resolved_type, x.screen) for x in logged][-1] == ("Unknown", "test")
        assert len(logged) == 6


def test_linking_an_unknown_barcode_and_finding_items_by_it(settings: Settings, db: Engine) -> None:
    linker = make_client(settings, db, ALL_PERMISSIONS | {"inv.barcode.link"})
    assert add(linker).status_code == 403  # managing barcodes on the item page needs the manage permission
    linked = linker.post(f"{API}/item-barcodes", json={"itemId": OIL_ITEM, "barcode": EAN, "barcodeType": "EAN13"})
    assert ok(linked, 201)["itemId"] == OIL_ITEM
    found = ok(linker.get(f"{API}/items", params={"search": EAN}))
    assert [i["itemCode"] for i in found["items"]] == ["OIL-15W40"]  # item search matches barcodes too
    plain = make_client(settings, db, ALL_PERMISSIONS)
    assert plain.post(f"{API}/item-barcodes", json={"itemId": OIL_ITEM, "barcode": "X1"}).status_code == 403


def test_labels_for_bins_racks_and_items(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, MANAGE)
    rack = ok(
        client.post(f"{API}/locations/{WH_MAIN}/storage-racks", json={"shortCode": "R01", "levels": 2, "positions": 2})
    )
    roll = client.get(f"{API}/labels", params={"kind": "Bin", "storageRackIds": [rack["id"]]})
    assert roll.status_code == 200 and roll.headers["content-type"] == "application/pdf"
    assert roll.content.startswith(b"%PDF")

    sheet = client.get(f"{API}/labels", params={"kind": "Bin", "locationId": WH_MAIN, "layout": "sheet", "copies": 2})
    assert sheet.status_code == 200 and sheet.content.startswith(b"%PDF")  # the loose bins A1 and A2
    assert client.get(f"{API}/labels", params={"kind": "Rack", "ids": [rack["id"]]}).status_code == 200

    ok(add(client))  # FLT-01 prints its EAN-13; OIL-15W40 has none and prints its item code
    items = client.get(f"{API}/labels", params=[("kind", "Item"), ("ids", FILTER_ITEM), ("ids", OIL_ITEM)])
    assert items.status_code == 200 and items.content.startswith(b"%PDF")
    assert client.get(f"{API}/labels", params={"kind": "Item"}).status_code == 400  # nothing chosen

    locations_only = make_client(settings, db, ALL_PERMISSIONS)  # inv.location.manage, no barcode permission
    assert locations_only.get(f"{API}/labels", params={"kind": "Bin", "ids": [RACK_A1]}).status_code == 200
    assert locations_only.get(f"{API}/labels", params={"kind": "Item", "ids": [OIL_ITEM]}).status_code == 403


def receive(client: TestClient, grn_date: date, *lines: dict[str, Any]) -> dict[str, Any]:
    body = {"locationId": WH_MAIN, "supplierId": SUPPLIER, "grnDate": grn_date.isoformat(), "lines": list(lines)}
    result: dict[str, Any] = ok(client.post(f"{PUR}/grns", json=body), 201)
    return result


def pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type /Page[^s]", pdf))


def test_each_grn_batch_is_aged_from_its_own_grn_date(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, MANAGE)
    old, new = date(2025, 10, 15), date.today()
    receive(client, old, line(quantity="5", binId=RACK_A1))
    receive(client, new, line(quantity="3"))

    by_item = scan(client, "FLT-01")
    rows = [
        (b["grnDate"], Decimal(b["qtyReceived"]), Decimal(b["qtyAvailable"]), b["ageText"]) for b in by_item["batches"]
    ]
    assert rows == [(old.isoformat(), 5, 5, age_text(old)), (new.isoformat(), 3, 3, "0 days")]  # oldest first
    first = by_item["batches"][0]
    assert (first["ageYears"], first["ageMonths"], first["ageRestDays"]) == age_parts(old)
    assert first["ageDays"] == (date.today() - old).days and first["places"] == ["WH-MAIN · A1: 5"]

    by_batch = scan(client, first["lotNo"].lower())  # the batch label: that receipt only
    assert by_batch["resolvedType"] == "Lot" and by_batch["matches"][0]["via"] == "Batch number"
    assert [b["grnNo"] for b in by_batch["batches"]] == [first["grnNo"]]
    with Session(db) as s:
        assert s.scalars(select(ScanLog.resolved_type).order_by(ScanLog.id.desc())).first() == "Lot"


def test_batch_labels_for_a_grn(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, MANAGE)
    grn = receive(client, date.today(), line(quantity="3"), line(OIL_ITEM, quantity="2"))
    two = client.get(f"{API}/labels", params={"kind": "Lot", "grnId": grn["id"]})
    assert two.status_code == 200 and pages(two.content) == 2  # one label a batch
    each = client.get(f"{API}/labels", params={"kind": "Lot", "grnId": grn["id"], "onePerUnit": True})
    assert pages(each.content) == 5  # one a unit received

    storekeeper = make_client(settings, db, {"inv.grn.manage", "inv.stock.view"})
    assert storekeeper.get(f"{API}/labels", params={"kind": "Lot", "grnId": grn["id"]}).status_code == 200
    assert storekeeper.get(f"{API}/labels", params={"kind": "Bin", "ids": [RACK_A1]}).status_code == 403
