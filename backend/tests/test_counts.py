"""Warehouse storage, phase 5: physical stock counts (blind counting, variance review, the posted adjustment)."""

# ruff: noqa: F811  (the inventory fixtures are imported, then used as test arguments)

from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.config import Settings
from trishul_api.db.models import StockAdjustment

from .test_inventory_api import (
    ALL_PERMISSIONS,
    API,
    COUNT_DIFFERENCE,
    DAMAGE,
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

COUNTER = ALL_PERMISSIONS | {"inv.count.manage", "inv.binmove.manage"}
APPROVER = COUNTER | {"inv.count.approve"}


def receive(client: TestClient, *lines: dict[str, Any]) -> None:
    body = {
        "locationId": WH_MAIN,
        "supplierId": SUPPLIER,
        "grnDate": date(2026, 1, 5).isoformat(),
        "lines": list(lines),
    }
    ok(client.post(f"{PUR}/grns", json=body), 201)


def start(client: TestClient, **body: Any) -> Any:
    return ok(client.post(f"{API}/stock-counts", json={"locationId": WH_MAIN, **body}), 201)


def enter(client: TestClient, count_id: int, item: int, qty: str, bin_id: int | None, mode: str = "set") -> Any:
    body = {"itemId": item, "binId": bin_id, "quantity": qty, "mode": mode}
    return client.post(f"{API}/stock-counts/{count_id}/lines", json=body)


def key(row: dict[str, Any]) -> tuple[str, str | None]:
    return row["itemCode"], row["binCode"]


def test_a_blind_full_count_is_reviewed_and_posted(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, APPROVER)
    receive(client, line(quantity="5", binId=RACK_A1), line(OIL_ITEM, quantity="3"))
    count = start(client)
    assert (count["countNo"], count["countType"], count["status"]) == (f"SC-{count['id']:06d}", "Full", "Open")
    assert {key(r): r["systemQty"] for r in count["lines"]} == {("FLT-01", "A1"): None, ("OIL-15W40", None): None}

    ok(enter(client, count["id"], FILTER_ITEM, "4", RACK_A1))  # one filter is missing
    ok(enter(client, count["id"], OIL_ITEM, "1", RACK_A2, mode="add"))  # oil found in A2, scanned twice
    scanned = ok(enter(client, count["id"], OIL_ITEM, "1", RACK_A2, mode="add"))
    assert (scanned["countedQty"], scanned["isExpected"], scanned["systemQty"]) == ("2.000", False, None)

    closed = ok(client.post(f"{API}/stock-counts/{count['id']}/close", json={}))
    rows = {key(r): r for r in closed["lines"]}
    assert closed["status"] == "Counted" and closed["countedCount"] == 2
    assert (rows[("FLT-01", "A1")]["systemQty"], rows[("FLT-01", "A1")]["variance"]) == ("5.000", "-1.000")
    assert rows[("OIL-15W40", "A2")]["variance"] == "2.000"
    assert rows[("OIL-15W40", None)]["countedQty"] is None  # not counted: left out
    assert (closed["shortQty"], closed["excessQty"]) == ("1.000", "2.000")

    posted = ok(client.post(f"{API}/stock-counts/{count['id']}/post"))
    assert posted["status"] == "Adjusted" and posted["adjustmentNo"].startswith("ADJ/")
    with Session(db) as s:
        adjustment = s.scalars(select(StockAdjustment)).one()
        assert (adjustment.stock_count_id, adjustment.reason_lookup_id) == (count["id"], COUNT_DIFFERENCE)
    assert sorted((b[2], b[3]) for b in batches(db, WH_MAIN)) == sorted([(4, RACK_A1), (3, None), (2, RACK_A2)])
    assert client.post(f"{API}/stock-counts/{count['id']}/post").status_code == 409


def test_uncounted_lines_can_be_counted_as_zero(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, APPROVER)
    receive(client, line(quantity="5", binId=RACK_A1), line(OIL_ITEM, quantity="3", binId=RACK_A2))
    count = start(client, scope="Bins", binIds=[RACK_A1, RACK_A2], isBlind=False)
    assert count["countType"] == "Cycle" and count["binCodes"] == ["A1", "A2"]
    assert client.post(f"{API}/stock-counts/{count['id']}/close", json={}).status_code == 400  # nothing counted
    ok(enter(client, count["id"], FILTER_ITEM, "5", RACK_A1))
    closed = ok(client.post(f"{API}/stock-counts/{count['id']}/close", json={"uncountedAsZero": True}))
    assert {key(r): r["variance"] for r in closed["lines"]} == {
        ("FLT-01", "A1"): "0.000",
        ("OIL-15W40", "A2"): "-3.000",
    }
    ok(client.post(f"{API}/stock-counts/{count['id']}/post"))
    assert [(b[2], b[3]) for b in batches(db, WH_MAIN)] == [(5, RACK_A1)]


def test_counting_is_limited_to_the_scope_and_flags_later_moves(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, APPROVER)
    receive(client, line(quantity="5", binId=RACK_A1))
    count = start(client, scope="Bins", binIds=[RACK_A1])
    assert enter(client, count["id"], FILTER_ITEM, "1", RACK_A2).status_code == 400  # not in the count
    assert enter(client, count["id"], FILTER_ITEM, "1", None).status_code == 400  # only a full count has no bin
    ok(enter(client, count["id"], FILTER_ITEM, "5", RACK_A1))

    # two filters move to A2 after A1 was counted: flagged, and not counted twice when posting
    move = {
        "locationId": WH_MAIN,
        "lines": [{"itemId": FILTER_ITEM, "fromBinId": RACK_A1, "toBinId": RACK_A2, "quantity": "2"}],
    }
    ok(client.post(f"{API}/bin-moves", json=move), 201)
    closed = ok(client.post(f"{API}/stock-counts/{count['id']}/close", json={}))
    assert [(r["variance"], r["movedSinceCount"]) for r in closed["lines"]] == [("0.000", True)]
    posted = ok(client.post(f"{API}/stock-counts/{count['id']}/post"))
    assert posted["adjustmentId"] is None  # no difference: nothing posted
    assert sorted((b[2], b[3]) for b in batches(db, WH_MAIN)) == [(2, RACK_A2), (3, RACK_A1)]


def test_reopen_cancel_and_permissions(settings: Settings, db: Engine) -> None:
    counter = make_client(settings, db, COUNTER)
    receive(counter, line(quantity="5", binId=RACK_A1))
    count = start(counter)
    ok(enter(counter, count["id"], FILTER_ITEM, "6", RACK_A1))
    ok(counter.post(f"{API}/stock-counts/{count['id']}/close", json={}))
    assert counter.post(f"{API}/stock-counts/{count['id']}/post").status_code == 403  # needs inv.count.approve
    assert enter(counter, count["id"], FILTER_ITEM, "5", RACK_A1).status_code == 409  # counting finished
    assert ok(counter.post(f"{API}/stock-counts/{count['id']}/reopen"))["status"] == "Open"
    assert ok(counter.post(f"{API}/stock-counts/{count['id']}/cancel"))["status"] == "Cancelled"
    listed = ok(counter.get(f"{API}/stock-counts?status=Cancelled"))
    assert listed["total"] == 1 and listed["items"][0]["lineCount"] == 1

    viewer = make_client(settings, db, ALL_PERMISSIONS)
    assert viewer.get(f"{API}/stock-counts/{count['id']}").status_code == 200
    assert viewer.post(f"{API}/stock-counts", json={"locationId": WH_MAIN}).status_code == 403


def test_stock_in_a_blocked_bin_is_only_taken_when_the_bin_is_named(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, APPROVER)
    receive(client, line(quantity="5", binId=RACK_A1))
    rows: list[dict[str, Any]] = ok(client.get(f"{API}/locations/{WH_MAIN}/racks?status=all"))
    a1 = next(b for b in rows if b["id"] == RACK_A1)
    ok(client.patch(f"{API}/racks/{RACK_A1}", json={"isBlocked": True}, headers={"If-Match": a1["rowVersion"]}))

    def remove(bin_id: int | None) -> Any:
        body = {
            "locationId": WH_MAIN,
            "reasonId": DAMAGE,
            "lines": [{"itemId": FILTER_ITEM, "binId": bin_id, "qtyChange": "-1"}],
        }
        return client.post(f"{API}/adjustments", json=body)

    any_bin = remove(None)
    assert any_bin.status_code == 400 and "outside blocked bins" in any_bin.json()["detail"]
    ok(remove(RACK_A1), 201)
    assert [b[2] for b in batches(db, WH_MAIN)] == [4]
