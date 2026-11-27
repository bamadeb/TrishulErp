"""Warehouse storage, phase 3: receiving bins, put-away suggestions, bin moves and item storage rules."""

# ruff: noqa: F811  (the inventory fixtures are imported, then used as test arguments)

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.config import Settings
from trishul_api.db.models import MovementType, StockMove

from .test_inventory_api import (
    ALL_PERMISSIONS,
    API,
    BR_MAIN,
    FILTER_ITEM,
    OIL_ITEM,
    PUR,
    RACK_A1,
    RACK_A2,
    SUPPLIER,
    WH_MAIN,
    batches,
    db,  # noqa: F401  (fixture)
    line,
    make_client,
    ok,
)

MOVER = ALL_PERMISSIONS | {"inv.binmove.manage"}


def receive(client: TestClient, *lines: dict[str, Any], grn_date: date | None = None) -> Any:
    body = {
        "locationId": WH_MAIN,
        "supplierId": SUPPLIER,
        "grnDate": (grn_date or date.today()).isoformat(),
        "lines": list(lines),
    }
    return ok(client.post(f"{PUR}/grns", json=body), 201)


def bin_of(client: TestClient, bin_id: int, location: int = WH_MAIN) -> dict[str, Any]:
    rows: list[dict[str, Any]] = ok(client.get(f"{API}/locations/{location}/racks?status=all"))
    return next(b for b in rows if b["id"] == bin_id)


def make_receiving(client: TestClient, bin_id: int) -> None:
    current = bin_of(client, bin_id)
    ok(client.patch(f"{API}/racks/{bin_id}", json={"isReceiving": True}, headers={"If-Match": current["rowVersion"]}))


def move(client: TestClient, *lines: dict[str, Any], kind: str = "Put-away") -> Any:
    return client.post(f"{API}/bin-moves", json={"locationId": WH_MAIN, "moveType": kind, "lines": list(lines)})


def test_putaway_lists_receiving_and_unbinned_stock_with_suggestions(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, MOVER)
    rack = ok(
        client.post(f"{API}/locations/{WH_MAIN}/storage-racks", json={"shortCode": "R1", "levels": 1, "positions": 2})
    )
    rack_bins = ok(client.get(f"{API}/locations/{WH_MAIN}/racks?storageRackId={rack['id']}"))
    make_receiving(client, RACK_A2)
    assert bin_of(client, RACK_A2)["isReceiving"] is True
    receive(client, line(quantity="5", binId=RACK_A2), line(OIL_ITEM, quantity="3"))  # receiving bin, no bin
    receive(client, line(quantity="2", binId=RACK_A1))  # FLT-01 already stored in A1

    rows = ok(client.get(f"{API}/putaway?locationId={WH_MAIN}"))
    by_item = {(r["itemCode"], r["fromBinCode"]): r for r in rows}
    assert set(by_item) == {("FLT-01", "A2"), ("OIL-15W40", None)}  # A1 stock is already put away
    assert (by_item[("FLT-01", "A2")]["suggestedBinCode"], by_item[("FLT-01", "A2")]["suggestion"]) == (
        "A1", "Already stored here",
    )  # fmt: skip
    assert by_item[("OIL-15W40", None)]["suggestion"] == "Empty bin"  # never the receiving bin A2

    # a home bin wins over everything
    storage = ok(client.get(f"{API}/items/{OIL_ITEM}/storage"))
    home = {"storageType": "Grouped", "rules": [{"locationId": WH_MAIN, "binId": rack_bins[1]["id"], "maxQty": "50"}]}
    saved = ok(client.put(f"{API}/items/{OIL_ITEM}/storage", json=home, headers={"If-Match": storage["rowVersion"]}))
    assert (saved["storageType"], [r["binCode"] for r in saved["rules"]]) == ("Grouped", ["WH-MAIN-R1-L1-B02"])
    oil = next(r for r in ok(client.get(f"{API}/putaway?locationId={WH_MAIN}")) if r["itemCode"] == "OIL-15W40")
    assert (oil["suggestedBinCode"], oil["suggestion"]) == ("WH-MAIN-R1-L1-B02", "Home bin")


def test_a_bin_move_keeps_the_batch_and_writes_the_ledger(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, MOVER)
    receive(client, line(OIL_ITEM, quantity="3"), grn_date=date(2026, 1, 5))  # kept without a bin
    before = batches(db, WH_MAIN)
    done = ok(move(client, {"itemId": OIL_ITEM, "toBinId": RACK_A1, "quantity": "2"}), 201)
    assert done["moveNo"].startswith("BM-") and done["moveType"] == "Put-away" and done["lineCount"] == 1
    assert done["lines"][0]["fromBinCode"] is None and done["lines"][0]["toBinCode"] == "A1"

    after = batches(db, WH_MAIN)
    assert [(b[0], b[2], b[3]) for b in after] == [(before[0][0], 1, None), (before[0][0], 2, RACK_A1)]
    assert {b[1] for b in after} == {date(2026, 1, 5)}  # the GRN date (ageing) never resets
    with Session(db) as s:
        codes = s.execute(
            select(MovementType.code, StockMove.quantity, StockMove.bin_id)
            .join(MovementType, MovementType.id == StockMove.movement_type_id)
            .where(StockMove.source_document_type == "BIN_MOVE")
            .order_by(StockMove.id)
        ).all()
        assert [(c, Decimal(q), b) for c, q, b in codes] == [("BIN_OUT", -2, None), ("BIN_IN", 2, RACK_A1)]

    history = ok(client.get(f"{API}/bin-moves?itemId={OIL_ITEM}"))
    assert history["total"] == 1 and history["items"][0]["movedByName"]


def test_bin_moves_are_checked(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, MOVER)
    receive(client, line(quantity="4", binId=RACK_A1))
    too_much = move(client, {"itemId": FILTER_ITEM, "fromBinId": RACK_A1, "toBinId": RACK_A2, "quantity": "9"})
    assert too_much.status_code == 400 and "Only 4" in too_much.json()["detail"]
    same = move(client, {"itemId": FILTER_ITEM, "fromBinId": RACK_A1, "toBinId": RACK_A1, "quantity": "1"})
    assert same.status_code == 400
    other_place = move(client, {"itemId": FILTER_ITEM, "fromBinId": RACK_A1, "toBinId": 23, "quantity": "1"})
    assert other_place.status_code == 400  # B1 is in another location

    target = bin_of(client, RACK_A2)
    ok(client.patch(f"{API}/racks/{RACK_A2}", json={"isBlocked": True}, headers={"If-Match": target["rowVersion"]}))
    blocked = move(client, {"itemId": FILTER_ITEM, "fromBinId": RACK_A1, "toBinId": RACK_A2, "quantity": "1"})
    assert blocked.status_code == 400 and "blocked" in blocked.json()["detail"]
    assert [b[2] for b in batches(db, WH_MAIN)] == [4]  # nothing moved


def test_storage_rules_are_validated(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, MOVER)
    storage = ok(client.get(f"{API}/items/{FILTER_ITEM}/storage"))
    assert (storage["storageType"], storage["rules"]) == (None, [])
    headers = {"If-Match": storage["rowVersion"]}
    elsewhere = {"rules": [{"locationId": WH_MAIN, "binId": 23}]}  # B1 belongs to BR-MAIN
    assert client.put(f"{API}/items/{FILTER_ITEM}/storage", json=elsewhere, headers=headers).status_code == 400
    upside_down = {"rules": [{"locationId": WH_MAIN, "binId": RACK_A1, "minQty": "9", "maxQty": "2"}]}
    assert client.put(f"{API}/items/{FILTER_ITEM}/storage", json=upside_down, headers=headers).status_code == 400
    two = {
        "storageType": "Individual",
        "rules": [{"locationId": WH_MAIN, "binId": RACK_A1}, {"locationId": BR_MAIN, "binId": 23, "minQty": "1"}],
    }
    saved = ok(client.put(f"{API}/items/{FILTER_ITEM}/storage", json=two, headers=headers))
    assert [r["binCode"] for r in saved["rules"]] == ["B1", "A1"] or [r["binCode"] for r in saved["rules"]] == [
        "A1",
        "B1",
    ]
    cleared = ok(
        client.put(f"{API}/items/{FILTER_ITEM}/storage", json={"rules": []}, headers={"If-Match": saved["rowVersion"]})
    )
    assert (cleared["storageType"], cleared["rules"]) == (None, [])
    assert client.put(f"{API}/items/{FILTER_ITEM}/storage", json={"rules": []}).status_code == 428


def test_permissions(settings: Settings, db: Engine) -> None:
    viewer = make_client(settings, db, ALL_PERMISSIONS)
    assert viewer.get(f"{API}/bin-moves").status_code == 200
    assert viewer.get(f"{API}/putaway?locationId={WH_MAIN}").status_code == 403
    assert viewer.post(f"{API}/bin-moves", json={"locationId": WH_MAIN, "lines": []}).status_code in (403, 422)
