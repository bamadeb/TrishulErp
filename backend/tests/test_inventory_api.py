"""Item and inventory management: route -> service -> ledger -> SQL (SQLite).

The point of the module: stock is kept per GRN batch, so the age of stock counts from its original GRN
date wherever it is moved, and the ageing report values each batch at its actual GRN cost.
"""

from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import LotBalance, StockBalance, StockLot, StockMove
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.principal",
    "core.branch",
    "core.location",
    "core.uom",
    "core.hsn_sac",
    "acc.gst_rate",
    "core.item_category",
    "core.item",
    "core.supplier",
    "core.currency",
    "core.number_series",
    "core.lookup_type",
    "core.lookup_value",
    "core.app_user",
    "core.audit_log",
    "inv.bin",
    "inv.movement_type",
    "inv.uom_conversion",
    "inv.stock_lot",
    "inv.lot_balance",
    "inv.stock_balance",
    "inv.stock_move",
    "inv.stock_transfer",
    "inv.stock_transfer_line",
    "inv.stock_adjustment",
    "inv.stock_adjustment_line",
    "pur.grn",
    "pur.grn_line",
    "pur.purchase_order",
    "pur.purchase_order_line",
    "pur.supplier_item_price",
    "sal.price_list",
    "sal.price_list_item",
]
COMPANY = 1
WAREHOUSE, BRANCH, OTHER_BRANCH = 1, 2, 3
WH_MAIN, BR_MAIN, OTHER_MAIN = 11, 12, 13  # locations
RACK_A1, RACK_A2, RACK_B1 = 21, 22, 23
NOS, BOX = 1, 2
SPARES, FILTERS = 31, 32  # category, subcategory
FILTER_ITEM, OIL_ITEM = 41, 42
SUPPLIER = 51
DAMAGE, FOUND = 61, 62  # adjustment reasons
ACTOR_ID = 1
ALL_PERMISSIONS = {
    "inv.item.view",
    "inv.item.manage",
    "inv.location.manage",
    "inv.stock.view",
    "inv.grn.manage",
    "inv.transfer.manage",
    "inv.stock.adjust",
    "pur.grn.manage",
}
API = "/api/v1/inv"
PUR = "/api/v1/pur"


def days_ago(days: int) -> date:
    return date.today() - timedelta(days=days)


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TRISHUL", legal_name="Trishul", trade_name="Trishul")
    insert_row(engine, "core.currency", id=1, code="INR", name="Rupee")
    insert_row(engine, "core.app_user", id=ACTOR_ID, username="store.keeper", cognito_sub="x")
    for bid, code, name, kind in (
        (WAREHOUSE, "BBSR", "Bhubaneswar", "Warehouse"),
        (BRANCH, "BHADRAK", "Bhadrak", "Branch"),
        (OTHER_BRANCH, "ANGUL", "Angul", "Branch"),
    ):
        insert_row(
            engine, "core.branch", id=bid, company_id=COMPANY, code=code, name=name, branch_type=kind, state_id=1
        )
    for lid, bid, code in (
        (WH_MAIN, WAREHOUSE, "WH-MAIN"),
        (BR_MAIN, BRANCH, "BR-MAIN"),
        (OTHER_MAIN, OTHER_BRANCH, "AN-MAIN"),
    ):
        store = {"code": code, "name": f"{code} store", "location_type": "Main store", "is_stock_location": True}
        insert_row(engine, "core.location", id=lid, branch_id=bid, **store)
    for rid, lid, code in ((RACK_A1, WH_MAIN, "A1"), (RACK_A2, WH_MAIN, "A2"), (RACK_B1, BR_MAIN, "B1")):
        insert_row(engine, "inv.bin", id=rid, location_id=lid, code=code)
    insert_row(engine, "core.uom", id=NOS, code="NOS", name="Numbers", decimals=0)
    insert_row(engine, "core.uom", id=BOX, code="BOX", name="Box", decimals=0)
    spare = {"item_nature": "Spare part"}
    insert_row(engine, "core.item_category", id=SPARES, code="SP", name="Spare parts", default_uom_id=NOS, **spare)
    insert_row(engine, "core.item_category", id=FILTERS, code="FIL", name="Filters", parent_category_id=SPARES, **spare)
    for iid, code, category in ((FILTER_ITEM, "FLT-01", FILTERS), (OIL_ITEM, "OIL-15W40", SPARES)):
        item = {"item_code": code, "description": f"{code} item", "category_id": category, "uom_id": NOS}
        item |= {"item_type": "Stock", "standard_cost": Decimal("12.5")}
        insert_row(engine, "core.item", id=iid, company_id=COMPANY, **item)
    supplier = {"code": "TH", "name": "Tata Hitachi", "supplier_type": "OEM"}
    insert_row(engine, "core.supplier", id=SUPPLIER, company_id=COMPANY, **supplier)
    for document_type, prefix in (("GRN", "GRN/"), ("STOCK_TRANSFER", "ST/"), ("STOCK_ADJUSTMENT", "ADJ/")):
        series = {"document_type": document_type, "prefix": prefix, "next_number": 1, "padding": 4}
        insert_row(engine, "core.number_series", company_id=COMPANY, **series)
    movements = {"GRN": "In", "OPENING": "In", "TRANSFER_OUT": "Out", "TRANSFER_IN": "In"}
    movements |= {"ADJUST_IN": "In", "ADJUST_OUT": "Out"}
    for code, direction in movements.items():
        insert_row(engine, "inv.movement_type", code=code, name=code.title(), direction=direction)
    insert_row(engine, "core.lookup_type", id=8, code="ADJUSTMENT_REASON", name="Adjustment Reason")
    insert_row(engine, "core.lookup_value", id=DAMAGE, lookup_type_id=8, code="DAMAGE", label="Damage")
    insert_row(engine, "core.lookup_value", id=FOUND, lookup_type_id=8, code="FOUND", label="Found")
    return engine


def make_client(settings: Settings, db: Engine, permissions: set[str] = ALL_PERMISSIONS) -> TestClient:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(
        id=ACTOR_ID,
        permissions=frozenset(permissions),
        branch_ids=frozenset({WAREHOUSE, BRANCH}),
        principal_ids=None,
        default_branch_id=WAREHOUSE,
    )
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=ACTOR_ID, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with make_client(settings, db) as test_client:
        yield test_client


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def grn(client: TestClient, *lines: dict[str, Any], grn_date: date, location: int = WH_MAIN) -> dict[str, Any]:
    body = {"locationId": location, "supplierId": SUPPLIER, "grnDate": grn_date.isoformat(), "lines": list(lines)}
    result: dict[str, Any] = ok(client.post(f"{PUR}/grns", json=body), 201)
    return result


def line(item: int = FILTER_ITEM, quantity: str = "5", cost: str = "10", **extra: Any) -> dict[str, Any]:
    return {"itemId": item, "quantity": quantity, "unitCost": cost, **extra}


def batches(db: Engine, location: int) -> list[tuple[str, date, Any, int | None]]:
    """(lot no, GRN date, qty, rack) at a location, oldest first; empty balances left out."""
    with Session(db) as s:
        rows = s.execute(
            select(StockLot.lot_no, StockLot.grn_date, LotBalance.qty_on_hand, LotBalance.bin_id)
            .join(StockLot, StockLot.id == LotBalance.stock_lot_id)
            .where(LotBalance.location_id == location, LotBalance.qty_on_hand > 0)
            .order_by(StockLot.grn_date, StockLot.id, LotBalance.bin_id)
        ).all()
        return [(r[0], r[1], d(r[2]), r[3]) for r in rows]


def d(value: Any) -> Any:  # Any: compares equal to ints in the expectations below
    return Decimal(str(value))


# ---------------------------------------------------------------- masters


def test_categories_nest_and_items_default_their_unit(client: TestClient) -> None:
    lubricants = {"code": "lub", "name": "Lubricants", "itemNature": "Lubricant", "defaultUomId": NOS}
    parent = ok(client.post(f"{API}/item-categories", json=lubricants), 201)
    engine_oil = {"code": "ENG", "name": "Engine oil", "parentCategoryId": parent["id"]}
    child = ok(client.post(f"{API}/item-categories", json=engine_oil), 201)
    assert (parent["code"], child["path"], child["level"]) == ("LUB", "Lubricants / Engine oil", 1)

    new_item = {"itemCode": "eo-1", "description": "Engine oil 5L", "categoryId": child["id"], "uomId": BOX}
    item = ok(client.post(f"{API}/items", json=new_item), 201)
    assert (item["itemCode"], item["uomCode"], item["categoryName"]) == ("EO-1", "BOX", "Engine oil")
    assert client.post(f"{API}/items", json={**new_item, "itemCode": "EO-1"}).status_code == 409

    # Without a unit the item takes its category's default unit.
    defaulted = ok(
        client.post(f"{API}/items", json={"itemCode": "LB-2", "description": "Grease", "categoryId": parent["id"]}), 201
    )
    assert defaulted["uomCode"] == "NOS"

    # Filtering on a category includes its subcategories.
    in_spares = ok(client.get(f"{API}/items", params={"categoryId": SPARES}))["items"]
    assert {i["itemCode"] for i in in_spares} == {"FLT-01", "OIL-15W40"}

    # A category can't be moved under its own subcategory.
    loop = client.patch(
        f"{API}/item-categories/{parent['id']}",
        json={"parentCategoryId": child["id"]},
        headers={"If-Match": f'"{parent["rowVersion"]}"'},
    )
    assert loop.status_code == 400 and "parentCategoryId" in loop.json()["errors"]


def test_hsn_codes_carry_their_gst_rate_and_items_pick_them(client: TestClient) -> None:
    filter_code = {"code": "84212900", "description": "Filters", "gstPct": "18"}
    filters = ok(client.post(f"{API}/hsn-codes", json=filter_code), 201)
    oils = ok(client.post(f"{API}/hsn-codes", json={"code": "27101980", "gstPct": "18"}), 201)
    labour = ok(client.post(f"{API}/hsn-codes", json={"code": "998719", "codeType": "SAC", "gstPct": "18"}), 201)
    assert (filters["codeType"], Decimal(filters["gstPct"]), filters["itemCount"]) == ("HSN", 18, 0)
    assert labour["codeType"] == "SAC"
    assert client.post(f"{API}/hsn-codes", json={"code": "84212900", "gstPct": "18"}).status_code == 409
    assert client.post(f"{API}/hsn-codes", json={"code": "84A1", "gstPct": "18"}).status_code == 422  # digits only

    # Same % reuses one GST rate; a new % adds one. The code can't change, its rate can.
    changed = ok(client.patch(f"{API}/hsn-codes/{oils['id']}", json={"gstPct": "28"},
                              headers={"If-Match": f'"{oils["rowVersion"]}"'}))  # fmt: skip
    assert Decimal(changed["gstPct"]) == 28

    item = ok(client.post(f"{API}/items", json={"itemCode": "KF70500", "description": "Filter kit",
                                                "categoryId": SPARES, "hsnSacId": filters["id"]}), 201)  # fmt: skip
    assert item["hsnCode"] == "84212900"
    codes = {h["code"]: h["itemCount"] for h in ok(client.get(f"{API}/hsn-codes"))}
    assert codes == {"27101980": 0, "84212900": 1, "998719": 0}
    options = ok(client.get(f"{API}/items/form-options"))["hsnCodes"]
    assert [o["code"] for o in options] == ["27101980", "84212900", "998719"]


def test_rack_codes_are_unique_across_locations(client: TestClient) -> None:
    assert client.post(f"{API}/locations/{BR_MAIN}/racks", json={"code": "a1"}).status_code == 409  # A1 is at WH-MAIN
    rack = ok(client.post(f"{API}/locations/{BR_MAIN}/racks", json={"code": "b2", "rack": "B", "shelf": "2"}))
    assert (rack["code"], rack["locationCode"]) == ("B2", "BR-MAIN")
    locations = ok(client.get(f"{API}/locations"))
    assert {loc["code"]: loc["rackCount"] for loc in locations} == {"WH-MAIN": 2, "BR-MAIN": 2}  # not AN-MAIN


def test_location_can_be_added_under_a_branch_but_not_one_the_user_lacks(client: TestClient) -> None:
    quarantine = {"branchId": BRANCH, "code": "br-q", "name": "Quarantine", "locationType": "Quarantine"}
    created = ok(client.post(f"{API}/locations", json=quarantine), 201)
    assert (created["branchName"], created["code"]) == ("Bhadrak", "BR-Q")
    assert client.post(f"{API}/locations", json={"branchId": OTHER_BRANCH, "code": "X", "name": "X"}).status_code == 403


# ---------------------------------------------------------------- GRN and ageing


def test_grn_creates_a_batch_per_line_aged_from_the_grn_date(client: TestClient, db: Engine) -> None:
    box_of_ten = {"itemId": FILTER_ITEM, "fromUomId": BOX, "toUomId": NOS, "factor": "10"}
    ok(client.post(f"{API}/uom-conversions", json=box_of_ten), 201)
    received = grn(
        client,
        line(quantity="2", cost="500", uomId=BOX, binId=RACK_A1),  # 2 boxes of 10 at 500 a box
        line(item=OIL_ITEM, quantity="3", cost="400", rejectedQty="1", rejectionReason="Leaking"),
        grn_date=days_ago(100),
    )
    assert received["grnNo"] == "GRN/0001" and received["status"] == "Posted"
    filters, oil = received["lines"]
    assert (d(filters["qtyAccepted"]), d(filters["unitCost"]), filters["entryUomCode"]) == (20, 50, "BOX")
    assert (d(oil["qtyReceived"]), d(oil["qtyAccepted"]), d(oil["qtyRejected"])) == (4, 3, 1)
    assert d(filters["qtyRemaining"]) == 20 and filters["lotNo"].startswith("LOT")

    assert [(b[1], b[2], b[3]) for b in batches(db, WH_MAIN)] == [
        (days_ago(100), 20, RACK_A1),
        (days_ago(100), 3, None),
    ]
    item = ok(client.get(f"{API}/items/{FILTER_ITEM}"))
    assert (d(item["qtyOnHand"]), d(item["stockValue"]), d(item["lastPurchaseCost"])) == (20, 1000, 50)

    stock = ok(client.get(f"{API}/stock", params={"itemId": FILTER_ITEM}))["items"]
    assert [(s["ageDays"], s["bucket"], s["binCode"], s["grnNo"]) for s in stock] == [
        (100, "91-180 days", "A1", "GRN/0001")
    ]
    with Session(db) as s:
        totals = s.execute(select(StockBalance.bin_id, StockBalance.qty_on_hand, StockBalance.avg_cost)).all()
        assert sorted((r[0] or 0, d(r[1]), d(r[2])) for r in totals) == [(0, 3, 400), (RACK_A1, 20, 50)]


def test_transfer_keeps_the_original_grn_date_and_moves_the_oldest_first(client: TestClient, db: Engine) -> None:
    grn(client, line(quantity="5", cost="10"), grn_date=days_ago(200))
    grn(client, line(quantity="5", cost="20"), grn_date=days_ago(10))

    body = {
        "fromLocationId": WH_MAIN,
        "toLocationId": BR_MAIN,
        "lines": [{"itemId": FILTER_ITEM, "quantity": "7", "toBinId": RACK_B1}],
    }
    transfer = ok(client.post(f"{API}/transfers", json=body), 201)
    assert transfer["transferNo"] == "ST/0001" and transfer["fromBranchName"] == "Bhubaneswar"
    assert [(b["grnDate"], d(b["quantity"]), b["binCode"]) for b in transfer["batches"]] == [
        (days_ago(200).isoformat(), 5, "B1"),
        (days_ago(10).isoformat(), 2, "B1"),
    ]
    assert d(transfer["totalValue"]) == 5 * 10 + 2 * 20

    # At the branch the stock is as old as it was in the warehouse; the newer batch stays partly behind.
    assert [(b[1], b[2]) for b in batches(db, BR_MAIN)] == [(days_ago(200), 5), (days_ago(10), 2)]
    assert [(b[1], b[2]) for b in batches(db, WH_MAIN)] == [(days_ago(10), 3)]

    report = ok(client.get(f"{API}/reports/ageing", params={"groupBy": "location"}))
    assert report["buckets"] == ["0-30 days", "31-60 days", "61-90 days", "91-180 days", "Above 180 days"]
    by_location = {row["code"]: row for row in report["rows"]}
    branch = by_location["BR-MAIN"]
    assert [(d(c["qty"]), d(c["value"])) for c in branch["buckets"]] == [(2, 40), (0, 0), (0, 0), (0, 0), (5, 50)]
    assert branch["oldestAgeDays"] == 200
    newest = by_location["WH-MAIN"]["buckets"][0]
    assert (d(newest["qty"]), d(newest["value"])) == (3, 60)
    assert (d(report["totalQty"]), d(report["totalValue"])) == (10, 150)

    with Session(db) as s:
        moves = s.scalars(select(StockMove).where(StockMove.source_document_type == "STOCK_TRANSFER")).all()
        assert sorted(d(m.quantity) for m in moves) == [-5, -2, 2, 5]


def test_rack_to_rack_transfer_within_one_location(client: TestClient, db: Engine) -> None:
    grn(client, line(quantity="4", binId=RACK_A1), grn_date=days_ago(40))
    same = {"fromLocationId": WH_MAIN, "toLocationId": WH_MAIN}
    no_rack = {**same, "lines": [{"itemId": FILTER_ITEM, "quantity": "1"}]}
    assert client.post(f"{API}/transfers", json=no_rack).status_code == 400  # must name both racks
    moved = {**same, "lines": [{"itemId": FILTER_ITEM, "quantity": "1", "fromBinId": RACK_A1, "toBinId": RACK_A2}]}
    ok(client.post(f"{API}/transfers", json=moved), 201)
    assert [(b[1], b[2], b[3]) for b in batches(db, WH_MAIN)] == [
        (days_ago(40), 3, RACK_A1),
        (days_ago(40), 1, RACK_A2),
    ]
    racks = ok(client.get(f"{API}/reports/ageing", params={"groupBy": "rack"}))["rows"]
    assert {(r["code"], r["buckets"][1]["qty"] and d(r["buckets"][1]["qty"])) for r in racks} == {("A1", 3), ("A2", 1)}


def test_cannot_move_more_than_is_in_stock(client: TestClient, db: Engine) -> None:
    grn(client, line(quantity="2"), grn_date=days_ago(5))
    body = {"fromLocationId": WH_MAIN, "toLocationId": BR_MAIN, "lines": [{"itemId": FILTER_ITEM, "quantity": "3"}]}
    response = client.post(f"{API}/transfers", json=body)
    assert response.status_code == 400
    assert "Only 2 of FLT-01" in response.json()["detail"]
    assert [b[2] for b in batches(db, WH_MAIN)] == [2]  # nothing moved
    assert ok(client.get(f"{API}/transfers"))["total"] == 0  # and no number used


def test_adjustments_take_the_oldest_batch_and_add_new_batches(client: TestClient, db: Engine) -> None:
    grn(client, line(quantity="3", cost="10"), grn_date=days_ago(90))
    grn(client, line(quantity="3", cost="30"), grn_date=days_ago(20))
    body = {
        "locationId": WH_MAIN,
        "reasonId": DAMAGE,
        "remarks": "Water damage",
        "lines": [
            {"itemId": FILTER_ITEM, "qtyChange": "-4"},
            {"itemId": OIL_ITEM, "qtyChange": "2", "binId": RACK_A2},  # found: new batch at standard cost
        ],
    }
    adjustment = ok(client.post(f"{API}/adjustments", json=body), 201)
    assert (adjustment["adjustmentNo"], adjustment["reason"], adjustment["postedBy"]) == (
        "ADJ/0001",
        "Damage",
        "store.keeper",
    )
    assert (d(adjustment["qtyIn"]), d(adjustment["qtyOut"])) == (2, 4)
    assert d(adjustment["valueChange"]) == -(3 * 10 + 1 * 30) + 2 * Decimal("12.5")
    assert [(b[1], b[2]) for b in batches(db, WH_MAIN)] == [(days_ago(20), 2), (date.today(), 2)]

    # Adding to a named batch keeps that batch's GRN date.
    lot_id = ok(client.get(f"{API}/stock", params={"itemId": FILTER_ITEM}))["items"][0]["stockLotId"]
    found = {"itemId": FILTER_ITEM, "qtyChange": "1", "stockLotId": lot_id}
    more = {"locationId": BR_MAIN, "reasonId": FOUND, "lines": [found]}
    ok(client.post(f"{API}/adjustments", json=more), 201)
    assert [(b[1], b[2]) for b in batches(db, BR_MAIN)] == [(days_ago(20), 1)]


def test_opening_stock_carries_its_original_grn_date(client: TestClient) -> None:
    old_grn = {"grnNo": "OLD/77", "grnDate": days_ago(400).isoformat()}
    filters = {"itemId": FILTER_ITEM, "quantity": "6", "unitCost": "15", "binId": RACK_A2, **old_grn}
    oil = {"itemId": OIL_ITEM, "quantity": "2", "unitCost": "300", **old_grn}
    lots = ok(client.post(f"{API}/opening-stock", json={"locationId": WH_MAIN, "lines": [filters, oil]}), 201)
    assert [(lot["sourceType"], lot["grnNo"], lot["ageDays"], d(lot["qtyOnHand"])) for lot in lots] == [
        ("Opening", "OLD/77", 400, 6),
        ("Opening", "OLD/77", 400, 2),
    ]
    by_grn = ok(client.get(f"{API}/reports/ageing", params={"groupBy": "grn"}))["rows"]
    assert [(r["code"], d(r["buckets"][4]["qty"]), d(r["buckets"][4]["value"])) for r in by_grn] == [("OLD/77", 8, 690)]
    tomorrow = {**filters, "grnDate": (date.today() + timedelta(days=1)).isoformat()}
    assert client.post(f"{API}/opening-stock", json={"locationId": WH_MAIN, "lines": [tomorrow]}).status_code == 400


def test_costs_are_hidden_from_users_who_only_look_items_up(client: TestClient, settings: Settings, db: Engine) -> None:
    grn(client, line(quantity="2", cost="100"), grn_date=days_ago(3))
    full = ok(client.get(f"{API}/items", params={"search": "FLT-01"}))["items"][0]
    assert d(full["stockValue"]) == 200
    # A service engineer: inv.item.view only. Stock yes, costs no. (No `with`: it would dispose the shared db.)
    engineer = make_client(settings, db, {"inv.item.view"})
    item = ok(engineer.get(f"{API}/items", params={"search": "FLT-01"}))["items"][0]
    assert d(item["qtyOnHand"]) == 2
    assert (item["stockValue"], item["standardCost"]) == (None, None)
    detail = ok(engineer.get(f"{API}/items/{FILTER_ITEM}"))
    assert (detail["stockValue"], detail["standardCost"], detail["lastPurchaseCost"]) == (None, None, None)


def test_ageing_by_item_and_branch_follows_the_users_branches(client: TestClient, db: Engine) -> None:
    grn(client, line(quantity="1", cost="100"), grn_date=days_ago(45))
    grn(client, line(item=OIL_ITEM, quantity="2", cost="50"), grn_date=days_ago(75), location=BR_MAIN)
    # Stock at a branch the user does not work in is neither shown nor counted.
    lot = {"company_id": COMPANY, "item_id": FILTER_ITEM, "lot_no": "LOTX", "source_type": "GRN", "grn_no": "X"}
    lot |= {"grn_date": days_ago(5), "received_location_id": OTHER_MAIN, "unit_cost": 1, "qty_received": 9}
    insert_row(db, "inv.stock_lot", id=900, **lot)
    insert_row(db, "inv.lot_balance", stock_lot_id=900, item_id=FILTER_ITEM, location_id=OTHER_MAIN, qty_on_hand=9)

    items = ok(client.get(f"{API}/reports/ageing", params={"groupBy": "item"}))["rows"]
    assert {(r["code"], d(r["qty"]), d(r["value"])) for r in items} == {("FLT-01", 1, 100), ("OIL-15W40", 2, 100)}
    branches = ok(client.get(f"{API}/reports/ageing", params={"groupBy": "branch"}))
    rows = {r["name"]: [d(c["qty"]) for c in r["buckets"]] for r in branches["rows"]}
    assert rows == {"Bhubaneswar": [0, 1, 0, 0, 0], "Bhadrak": [0, 0, 2, 0, 0]}
    assert [d(c["value"]) for c in branches["totals"]] == [0, 100, 100, 0, 0]
    elsewhere = {
        "locationId": OTHER_MAIN,
        "supplierId": SUPPLIER,
        "grnDate": days_ago(1).isoformat(),
        "lines": [line()],
    }
    assert client.post(f"{PUR}/grns", json=elsewhere).status_code == 400


def test_movements_record_every_change_with_its_batch(client: TestClient) -> None:
    grn(client, line(quantity="2"), grn_date=days_ago(3))
    body = {"fromLocationId": WH_MAIN, "toLocationId": BR_MAIN, "lines": [{"itemId": FILTER_ITEM, "quantity": "2"}]}
    ok(client.post(f"{API}/transfers", json=body), 201)
    moves = ok(client.get(f"{API}/movements", params={"itemId": FILTER_ITEM}))["items"]
    assert [(m["movementCode"], d(m["quantity"]), m["grnDate"]) for m in moves] == [
        ("TRANSFER_IN", 2, days_ago(3).isoformat()),
        ("TRANSFER_OUT", -2, days_ago(3).isoformat()),
        ("GRN", 2, days_ago(3).isoformat()),
    ]


# ---------------------------------------------------------------- prices and permissions


def test_sales_and_purchase_prices_and_standard_cost(client: TestClient) -> None:
    price_list = ok(client.post(f"{API}/price-lists", json={"code": "retail", "name": "Retail 2026"}), 201)
    sales_url = f"{API}/items/{FILTER_ITEM}/sales-prices"
    ok(client.post(sales_url, json={"priceListId": price_list["id"], "unitPrice": "99"}))
    ok(client.post(sales_url, json={"priceListId": price_list["id"], "unitPrice": "90", "minQty": "10"}))
    assert client.post(sales_url, json={"priceListId": price_list["id"], "unitPrice": "1"}).status_code == 409
    supplier_price = {"supplierId": SUPPLIER, "price": "55", "supplierPartNo": "TH-9"}
    prices = ok(client.post(f"{API}/items/{FILTER_ITEM}/purchase-prices", json=supplier_price))
    assert [(d(p["minQty"]), d(p["unitPrice"])) for p in prices["salesPrices"]] == [(1, 99), (10, 90)]
    assert [(p["supplierName"], d(p["price"])) for p in prices["purchasePrices"]] == [("Tata Hitachi", 55)]
    assert d(prices["standardCost"]) == Decimal("12.5") and prices["averageCost"] is None

    item = ok(client.get(f"{API}/items/{FILTER_ITEM}"))
    updated = ok(client.patch(f"{API}/items/{FILTER_ITEM}", json={"standardCost": "14"},
                              headers={"If-Match": f'"{item["rowVersion"]}"'}))  # fmt: skip
    assert d(updated["standardCost"]) == 14


def test_view_only_users_cannot_post_stock(settings: Settings, db: Engine) -> None:
    with make_client(settings, db, {"inv.stock.view", "inv.item.view"}) as client:
        assert client.get(f"{API}/reports/ageing").status_code == 200
        assert client.get(f"{API}/items").status_code == 200
        body = {"locationId": WH_MAIN, "supplierId": SUPPLIER, "grnDate": days_ago(1).isoformat(), "lines": [line()]}
        assert client.post(f"{PUR}/grns", json=body).status_code == 403
        assert client.post(f"{API}/adjustments", json={}).status_code == 403
        assert client.post(f"{API}/items", json={}).status_code == 403


def test_store_users_without_the_report_permission_cannot_see_ageing(settings: Settings, db: Engine) -> None:
    with make_client(settings, db, {"inv.transfer.manage"}) as client:
        assert client.get(f"{API}/stock").status_code == 200  # to pick what to move
        assert client.get(f"{API}/reports/ageing").status_code == 403
