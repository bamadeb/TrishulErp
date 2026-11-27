"""Warehouse storage, phase 1: racks with generated bins, flexible locations, bin rules and stock by bin."""

# ruff: noqa: F811  (the inventory fixtures are imported, then used as test arguments)

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.db.models import Bin

from .test_inventory_api import (  # noqa: F401  (fixtures)
    API,
    BR_MAIN,
    FILTER_ITEM,
    OIL_ITEM,
    PUR,
    RACK_A1,
    RACK_A2,
    SUPPLIER,
    WH_MAIN,
    client,
    db,
    line,
    ok,
)

TODAY = date.today()


def add_rack(client: TestClient, location: int = WH_MAIN, **body: Any) -> dict[str, Any]:
    data = {"shortCode": "r01", "levels": 2, "positions": 3, **body}
    result: dict[str, Any] = ok(client.post(f"{API}/locations/{location}/storage-racks", json=data))
    return result


def bins(client: TestClient, location: int = WH_MAIN, **query: Any) -> list[dict[str, Any]]:
    params = "&".join(f"{k}={v}" for k, v in {"status": "all", **query}.items())
    result: list[dict[str, Any]] = ok(client.get(f"{API}/locations/{location}/racks?{params}"))
    return result


def receive(client: TestClient, *lines: dict[str, Any], location: int = WH_MAIN) -> Any:
    body = {"locationId": location, "supplierId": SUPPLIER, "grnDate": TODAY.isoformat(), "lines": list(lines)}
    return client.post(f"{PUR}/grns", json=body)


def patch_bin(client: TestClient, bin_: dict[str, Any], **body: Any) -> Any:
    return client.patch(f"{API}/racks/{bin_['id']}", json=body, headers={"If-Match": bin_["rowVersion"]})


def patch_rack(client: TestClient, rack: dict[str, Any], **body: Any) -> Any:
    return client.patch(f"{API}/storage-racks/{rack['id']}", json=body, headers={"If-Match": rack["rowVersion"]})


def test_a_rack_generates_its_bins_with_codes(client: TestClient) -> None:
    rack = add_rack(client, name="Filters rack", binType="Shared")
    assert (rack["code"], rack["levels"], rack["positions"], rack["binCount"]) == ("WH-MAIN-R01", 2, 3, 6)
    assert (rack["occupiedBins"], rack["blockedBins"], Decimal(rack["qtyOnHand"])) == (0, 0, 0)

    in_rack = bins(client, storageRackId=rack["id"])
    assert [b["code"] for b in in_rack] == [
        "WH-MAIN-R01-L1-B01", "WH-MAIN-R01-L1-B02", "WH-MAIN-R01-L1-B03",
        "WH-MAIN-R01-L2-B01", "WH-MAIN-R01-L2-B02", "WH-MAIN-R01-L2-B03",
    ]  # fmt: skip
    first = in_rack[0]
    assert (first["levelNo"], first["positionNo"], first["binType"], first["storageRackCode"]) == (
        1, 1, "Shared", "WH-MAIN-R01",
    )  # fmt: skip
    assert [b["code"] for b in bins(client, loose="true")] == ["A1", "A2"]  # the old racks stay as loose bins
    assert (
        client.post(
            f"{API}/locations/{WH_MAIN}/storage-racks", json={"shortCode": "R01", "levels": 1, "positions": 1}
        ).status_code
        == 409
    )
    location = next(x for x in ok(client.get(f"{API}/locations")) if x["id"] == WH_MAIN)
    assert (location["storageRackCount"], location["rackCount"], location["requiresBin"]) == (1, 8, False)


def test_stock_goes_into_a_rack_bin_and_shows_by_rack(client: TestClient) -> None:
    rack = add_rack(client)
    target = bins(client, storageRackId=rack["id"])[4]  # L2-B02
    ok(receive(client, line(quantity="7", binId=target["id"]), line(OIL_ITEM, quantity="2")), 201)

    rack = ok(client.get(f"{API}/storage-racks/{rack['id']}"))
    assert (rack["occupiedBins"], Decimal(rack["qtyOnHand"])) == (1, 7)
    placed = bins(client, storageRackId=rack["id"])[4]
    assert (placed["itemCount"], Decimal(placed["qtyOnHand"])) == (1, 7)

    report = ok(client.get(f"{API}/reports/bin-stock?locationId={WH_MAIN}"))
    rows = {(r["binCode"], r["itemCode"]): r for r in report["items"]}
    assert rows[("WH-MAIN-R01-L2-B02", "FLT-01")]["storageRackCode"] == "WH-MAIN-R01"
    assert Decimal(rows[("WH-MAIN-R01-L2-B02", "FLT-01")]["value"]) == 70
    assert rows[(None, "OIL-15W40")]["binId"] is None  # kept at the location without a bin: allowed
    unplaced = ok(client.get(f"{API}/reports/bin-stock?withoutBin=true"))["items"]
    assert [r["itemCode"] for r in unplaced] == ["OIL-15W40"]
    by_rack = ok(client.get(f"{API}/reports/bin-stock?storageRackId={rack['id']}"))
    assert by_rack["total"] == 1


def test_blocked_bins_and_racks_take_no_stock(client: TestClient) -> None:
    rack = add_rack(client)
    first = bins(client, storageRackId=rack["id"])[0]
    blocked = ok(patch_bin(client, first, isBlocked=True, blockedReason="Shelf damaged"))
    assert (blocked["isBlocked"], blocked["blockedReason"]) == (True, "Shelf damaged")
    refused = receive(client, line(binId=first["id"]))
    assert refused.status_code == 400 and "blocked (Shelf damaged)" in refused.json()["detail"]

    second = bins(client, storageRackId=rack["id"])[1]
    ok(patch_rack(client, rack, isBlocked=True, blockedReason="Being moved"))
    assert receive(client, line(binId=second["id"])).status_code == 400
    assert ok(receive(client, line(binId=RACK_A1)), 201)  # other bins are unaffected


def test_single_item_bins_and_capacity(client: TestClient) -> None:
    single = next(b for b in bins(client) if b["id"] == RACK_A1)
    single = ok(patch_bin(client, single, binType="Single item", maxQty="10"))
    ok(receive(client, line(quantity="6", binId=RACK_A1)), 201)
    other = receive(client, line(OIL_ITEM, quantity="1", binId=RACK_A1))
    assert other.status_code == 400 and "only one item" in other.json()["detail"]
    over = receive(client, line(quantity="5", binId=RACK_A1))
    assert over.status_code == 400 and "only 4 more fits" in over.json()["detail"]
    ok(receive(client, line(quantity="4", binId=RACK_A1)), 201)

    single = next(b for b in bins(client) if b["id"] == RACK_A1)
    assert patch_bin(client, single, maxQty="5").status_code == 400  # already holds 10
    assert patch_bin(client, single, isActive=False).status_code == 400  # holds stock


def test_a_location_may_require_bins_but_does_not_by_default(client: TestClient) -> None:
    ok(receive(client, line()), 201)  # flexible: no bin needed
    location = next(x for x in ok(client.get(f"{API}/locations")) if x["id"] == WH_MAIN)
    strict = ok(
        client.patch(
            f"{API}/locations/{WH_MAIN}", json={"requiresBin": True}, headers={"If-Match": location["rowVersion"]}
        )
    )
    assert strict["requiresBin"] is True
    refused = receive(client, line())
    assert refused.status_code == 400 and "keeps all stock in bins" in refused.json()["detail"]
    ok(receive(client, line(binId=RACK_A2)), 201)


def test_open_area_with_yard_spots(client: TestClient) -> None:
    yard = ok(
        client.post(
            f"{API}/locations",
            json={"branchId": 1, "code": "WH-YARD", "name": "Equipment yard", "locationType": "Open area"},
        ),
        201,
    )
    spot = ok(
        client.post(
            f"{API}/locations/{yard['id']}/racks",
            json={"code": "wh-y01-s03", "binType": "Area spot", "description": "Next to gate 2"},
        )
    )
    assert (spot["code"], spot["binType"], spot["storageRackId"]) == ("WH-Y01-S03", "Area spot", None)
    ok(receive(client, line(quantity="1", binId=spot["id"]), location=yard["id"]), 201)
    ok(receive(client, line(OIL_ITEM, quantity="1"), location=yard["id"]), 201)  # or just in the yard


def test_resizing_and_deactivating_a_rack(client: TestClient, db: Engine) -> None:
    rack = add_rack(client)  # 2 x 3
    last = bins(client, storageRackId=rack["id"])[5]  # L2-B03
    ok(receive(client, line(quantity="1", binId=last["id"])), 201)

    shrink = patch_rack(client, rack, positions=2)
    assert shrink.status_code == 400 and "WH-MAIN-R01-L2-B03" in shrink.json()["detail"]
    grown = ok(patch_rack(client, rack, levels=3))  # 3 x 3: three new bins
    assert grown["binCount"] == 9
    assert patch_rack(client, grown, isActive=False).status_code == 400  # still holds stock

    first = bins(client, storageRackId=rack["id"])[0]
    assert patch_bin(client, first, code="ELSEWHERE").status_code == 400  # a rack bin keeps its code

    # empty the bin by moving it to a loose bin, then shrink: the bins beyond the size are deactivated, not deleted
    move = {
        "fromLocationId": WH_MAIN, "toLocationId": WH_MAIN,
        "lines": [{"itemId": FILTER_ITEM, "quantity": "1", "fromBinId": last["id"], "toBinId": RACK_A2}],
    }  # fmt: skip
    ok(client.post(f"{API}/transfers", json=move), 201)
    rack = ok(client.get(f"{API}/storage-racks/{rack['id']}"))
    rack = ok(patch_rack(client, rack, positions=2, levels=2))
    assert rack["binCount"] == 4
    with Session(db) as s:
        all_bins = s.scalars(select(Bin).where(Bin.storage_rack_id == rack["id"])).all()
        assert (len(all_bins), sum(1 for b in all_bins if b.is_active)) == (9, 4)
    rack = ok(patch_rack(client, rack, positions=3))  # grows back: the same bins come back
    assert rack["binCount"] == 6
    with Session(db) as s:
        assert len(s.scalars(select(Bin).where(Bin.storage_rack_id == rack["id"])).all()) == 9


def test_branches_can_have_racks_too(client: TestClient) -> None:
    rack = add_rack(client, location=BR_MAIN, shortCode="S1", rackType="Shelf", levels=1, positions=2)
    assert rack["code"] == "BR-MAIN-S1"
    assert [b["code"] for b in bins(client, location=BR_MAIN, storageRackId=rack["id"])] == [
        "BR-MAIN-S1-L1-B01",
        "BR-MAIN-S1-L1-B02",
    ]
