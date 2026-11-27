"""Bulk item price import, approval and the price change history: route -> service -> SQL (SQLite)."""

from collections.abc import Iterator
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user
from trishul_api.auth.deps import get_db
from trishul_api.config import Settings
from trishul_api.db.audit import set_audit_context
from trishul_api.db.models import Item, ItemPriceHistory, PriceListItem
from trishul_api.main import create_app
from trishul_api.modules.core.documents import storage

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "core.principal",
    "core.currency",
    "core.uom",
    "core.item_category",
    "core.item",
    "core.app_user",
    "core.employee",
    "core.audit_log",
    "core.system_setting",
    "sal.price_list",
    "sal.price_list_item",
    "inv.price_import",
    "inv.price_import_line",
    "inv.item_price_history",
]
COMPANY, BRANCH, TATA, OTHER = 1, 1, 1, 2
RETAIL, OTHER_LIST = 1, 2
ACTOR, APPROVER = 1, 2
OIL, AIR, FUEL, OLD, SECRET, SAP_PART = 501, 502, 503, 504, 505, 506
API = "/api/v1/inv/price-imports"
IMPORTER = {"inv.price.import", "inv.price.import.view"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEADER = ["Item Code *", "Item Name", "Selling Price", "Purchase Price", "MRP", "Reason"]


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Engine:
    monkeypatch.setattr(storage, "_ROOT", tmp_path)
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="T", legal_name="Trishul", trade_name="Trishul")
    insert_row(engine, "core.branch", id=BRANCH, company_id=COMPANY, code="HO", name="Head office")
    insert_row(engine, "core.currency", id=1, code="INR", name="Rupee")
    for uid, name in ((ACTOR, "store.keeper"), (APPROVER, "the.boss")):
        insert_row(engine, "core.app_user", id=uid, username=name, cognito_sub=name)
    insert_row(engine, "core.principal", id=TATA, code="TATA", name="Tata Hitachi")
    insert_row(engine, "core.principal", id=OTHER, code="OTHER", name="Other")
    insert_row(engine, "core.uom", id=1, code="NOS", name="Numbers", decimals=0)
    insert_row(
        engine, "core.system_setting", setting_key="INV_PRICE_MAX_CHANGE_PCT", setting_value="20", data_type="Number"
    )
    insert_row(engine, "core.item_category", id=31, code="SP", name="Spares", item_nature="Spare part")
    lists = {"currency_id": 1, "price_list_type": "Retail"}
    insert_row(engine, "sal.price_list", id=RETAIL, code="TH-RETAIL", name="TH retail", principal_id=TATA, **lists)
    insert_row(engine, "sal.price_list", id=OTHER_LIST, code="OT", name="Other list", principal_id=OTHER, **lists)
    base = {"company_id": COMPANY, "category_id": 31, "uom_id": 1, "item_type": "Stock", "principal_id": TATA}
    items = [
        (OIL, "SP001", "Oil Filter", 400, 600),
        (AIR, "SP002", "Air Filter", 700, 900),
        (FUEL, "SP003", "Fuel Filter", None, None),
        (OLD, "SP004", "Retired part", 10, 10),
        (SAP_PART, "0000534", "Case", None, 100),
    ]
    for iid, code, name, cost, mrp in items:
        insert_row(engine, "core.item", id=iid, item_code=code, description=name, standard_cost=cost, mrp=mrp, **base)
    engine_update(engine, update(Item).where(Item.id == OLD).values(is_active=False))
    insert_row(engine, "core.item", id=SECRET, item_code="SECRET", description="x", **{**base, "principal_id": OTHER})
    insert_row(engine, "sal.price_list_item", id=1, price_list_id=RETAIL, item_id=OIL, unit_price=500, min_qty=1)
    insert_row(engine, "sal.price_list_item", id=2, price_list_id=RETAIL, item_id=AIR, unit_price=800, min_qty=1)
    insert_row(engine, "sal.price_list_item", id=3, price_list_id=RETAIL, item_id=AIR, unit_price=780, min_qty=10)
    return engine


def engine_update(engine: Engine, statement: Any) -> None:
    with Session(engine) as s:
        s.execute(statement)
        s.commit()


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
    return TestClient(app, raise_server_exceptions=False)  # no `with`: that would close the database


@pytest.fixture
def client(settings: Settings, db: Engine) -> TestClient:
    return make_client(settings, db, IMPORTER)


def workbook(rows: list[list[Any]], header: list[str] = HEADER) -> bytes:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def upload(client: TestClient, content: bytes, *, name: str = "prices.xlsx", **form: Any) -> Any:
    data = {"reason": "Price revision Nov 2026", "priceListId": str(RETAIL), **form}
    return client.post(API, files={"file": (name, content, XLSX)}, data={k: v for k, v in data.items() if v})


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


ROWS: list[list[Any]] = [
    ["SP001", "Oil Filter", 550, "", "", ""],  # +10%
    ["sp002", "Air Filter", 750, 720, "", "Supplier cut"],  # -6.25% selling, +2.86% purchase
    ["SP003", "Fuel Filter", 450, "", "", ""],  # no price yet: added, no % to check
    ["SP001", "", 560, "", "", ""],  # SP001 twice -> both rows are duplicates
    ["NOPE", "", 10, "", "", ""],  # not in the item master
    ["SP004", "", 10, "", "", ""],  # inactive
    ["SECRET", "", 10, "", "", ""],  # a brand the user can't see: as if missing
    ["SP002", "", "", "", "", ""],  # repeats SP002 too, and has no price
]


def lines_of(client: TestClient, batch_id: int, **query: str) -> dict[int, Any]:
    params = "&".join(f"{k}={v}" for k, v in {"pageSize": "100", **query}.items())
    return {x["rowNumber"]: x for x in ok(client.get(f"{API}/{batch_id}/lines?{params}"))["items"]}


def test_upload_compares_prices_and_changes_nothing(client: TestClient, db: Engine) -> None:
    rows = [r for i, r in enumerate(ROWS) if i not in (3, 7)]  # without the duplicate rows
    batch = ok(upload(client, workbook(rows)), 201)
    assert batch["status"] == "Pending" and batch["batchNo"].startswith("PRC-") and batch["canConfirm"]
    assert batch["priceListName"] == "TH retail" and batch["fileLayout"] == "Template"
    counts = [batch[k] for k in ("totalRows", "validCount", "invalidCount", "changedCount", "overLimitCount")]
    assert counts == [6, 3, 3, 3, 0]

    lines = lines_of(client, batch["id"])
    assert (lines[2]["oldSelling"], lines[2]["newSelling"], lines[2]["maxChangePct"]) == (
        "500.0000",
        "550.0000",
        "10.00",
    )
    assert (
        lines[3]["itemCode"] == "SP002"
        and lines[3]["oldPurchase"] == "700.0000"
        and lines[3]["maxChangePct"] == "-6.25"
    )
    assert lines[3]["oldSelling"] == "800.0000"  # the lowest-quantity row of the list
    assert lines[4]["oldSelling"] is None and lines[4]["maxChangePct"] is None
    assert "not in the item master" in lines[5]["messages"][0]
    assert lines[6]["messages"] == ["Item SP004 is inactive."]
    assert "not in the item master" in lines[7]["messages"][0]
    assert set(lines_of(client, batch["id"], status="Decrease")) == {3}
    with Session(db) as s:
        assert s.scalar(select(PriceListItem.unit_price).where(PriceListItem.id == 1)) == 500
        assert s.scalars(select(ItemPriceHistory)).all() == []


def test_duplicates_and_missing_prices_are_flagged(client: TestClient) -> None:
    batch = ok(upload(client, workbook(ROWS)), 201)
    assert (batch["duplicateCount"], batch["changedCount"], batch["invalidCount"]) == (3, 1, 4)
    lines = lines_of(client, batch["id"])
    assert lines[2]["action"] == lines[5]["action"] == "Duplicate"
    assert "rows 2, 5" in lines[2]["messages"][0]
    assert lines[9]["action"] == "Error" and "No price given" in lines[9]["messages"][0]  # SP002 again, no price
    assert lines[3]["action"] == "Duplicate"  # SP002 is on rows 3 and 9


def test_confirm_applies_in_one_go_and_records_history(client: TestClient, db: Engine) -> None:
    rows = [ROWS[0], ROWS[1], ROWS[2], ["SP001", "", "", "", 650, ""]]  # SP001 twice again
    rows = [ROWS[1], ROWS[2], ["SP001", "", 550, 420, 650, "MRP revision"]]
    batch = ok(upload(client, workbook(rows)), 201)
    done = ok(client.post(f"{API}/{batch['id']}/confirm", json={}))
    assert done["status"] == "Completed" and done["updatedCount"] == 3 and done["confirmedByName"] == "store.keeper"

    with Session(db) as s:
        prices = dict(s.execute(select(PriceListItem.id, PriceListItem.unit_price)).all())
        assert prices[1] == 550 and prices[2] == 750 and prices[3] == 780  # the qty-10 price is untouched
        fuel = s.scalar(select(PriceListItem).where(PriceListItem.item_id == FUEL))
        assert fuel is not None and fuel.unit_price == 450 and fuel.min_qty == 1  # added to the list
        oil = s.get(Item, OIL)
        assert oil is not None and (oil.standard_cost, oil.mrp) == (420, 650)
        history = {h.item_id: h for h in s.scalars(select(ItemPriceHistory))}
        assert set(history) == {OIL, AIR, FUEL}
        h = history[OIL]
        assert (h.old_selling, h.new_selling, h.old_purchase, h.new_purchase, h.old_mrp, h.new_mrp) == (
            500, 550, 400, 420, 600, 650,
        )  # fmt: skip
        assert (h.source, h.import_id, h.reason, h.changed_by_user_id) == ("Import", batch["id"], "MRP revision", ACTOR)
        assert (history[AIR].reason, history[AIR].old_mrp, history[AIR].new_mrp) == ("Supplier cut", None, None)
        assert history[FUEL].reason == "Price revision Nov 2026"  # the upload's reason
        assert history[FUEL].price_list_id == RETAIL

    log = ok(client.get(f"/api/v1/inv/items/{OIL}/price-history"))["items"]
    assert log[0]["batchNo"] == batch["batchNo"] and log[0]["changedByName"] == "store.keeper"
    assert client.post(f"{API}/{batch['id']}/confirm", json={}).status_code == 409  # only once


def test_the_same_file_again_needs_an_explicit_tick(client: TestClient, db: Engine) -> None:
    content = workbook([ROWS[0]])
    first = ok(upload(client, content), 201)
    ok(client.post(f"{API}/{first['id']}/confirm", json={}))
    same_prices = ok(upload(client, content), 201)
    assert same_prices["repeatOfBatchNo"] == first["batchNo"]
    assert same_prices["status"] == "Completed" and same_prices["changedCount"] == 0  # already these prices

    engine_update(db, update(PriceListItem).where(PriceListItem.id == 1).values(unit_price=500))  # back again
    again = ok(upload(client, content), 201)
    assert again["status"] == "Pending" and again["repeatOfBatchNo"] == first["batchNo"]
    refused = client.post(f"{API}/{again['id']}/confirm", json={})
    assert refused.status_code == 409 and first["batchNo"] in refused.json()["detail"]
    assert ok(client.get(f"{API}/{again['id']}"))["status"] == "Pending"  # still waiting
    assert ok(client.post(f"{API}/{again['id']}/confirm", json={"importAgain": True}))["status"] == "Completed"


def test_a_change_after_the_preview_is_not_applied(client: TestClient, db: Engine) -> None:
    batch = ok(upload(client, workbook([ROWS[0], ROWS[2]])), 201)
    engine_update(db, update(PriceListItem).where(PriceListItem.id == 1).values(unit_price=520))
    done = ok(client.post(f"{API}/{batch['id']}/confirm", json={}))
    assert done["status"] == "Partially Completed" and (done["updatedCount"], done["failedCount"]) == (1, 1)
    line = lines_of(client, batch["id"])[2]
    assert line["outcome"] == "Failed" and "changed since the preview" in line["messages"][-1]
    with Session(db) as s:
        assert s.scalar(select(PriceListItem.unit_price).where(PriceListItem.id == 1)) == 520


def test_big_changes_wait_for_approval(settings: Settings, db: Engine, client: TestClient) -> None:
    rows = [["SP001", "", 900, "", "", ""], ["SP003", "", 450, "", "", ""]]  # +80%: over the 20% limit
    batch = ok(upload(client, workbook(rows)), 201)
    assert batch["overLimitCount"] == 1
    waiting = ok(client.post(f"{API}/{batch['id']}/confirm", json={}))
    assert waiting["status"] == "Pending approval" and not waiting["canApprove"] and waiting["updatedCount"] == 0
    with Session(db) as s:
        assert s.scalar(select(PriceListItem.unit_price).where(PriceListItem.id == 1)) == 500

    assert client.post(f"{API}/{batch['id']}/approve", json={}).status_code == 403
    boss = make_client(settings, db, IMPORTER | {"inv.price.approve"}, user_id=APPROVER)
    assert ok(boss.get(f"{API}/{batch['id']}"))["canApprove"]
    done = ok(boss.post(f"{API}/{batch['id']}/approve", json={"note": "Agreed with OEM"}))
    assert done["status"] == "Completed" and done["approvedByName"] == "the.boss" and done["updatedCount"] == 2
    assert done["decisionNote"] == "Agreed with OEM"
    with Session(db) as s:
        assert s.scalar(select(PriceListItem.unit_price).where(PriceListItem.id == 1)) == 900
        h = s.scalar(select(ItemPriceHistory).where(ItemPriceHistory.item_id == OIL))
        assert h is not None and h.changed_by_user_id == APPROVER


def test_rejected_and_self_approved_imports(settings: Settings, db: Engine, client: TestClient) -> None:
    rows = [["SP001", "", 100, "", "", ""]]  # -80%
    batch = ok(upload(client, workbook(rows)), 201)
    ok(client.post(f"{API}/{batch['id']}/confirm", json={}))
    boss = make_client(settings, db, IMPORTER | {"inv.price.approve"}, user_id=APPROVER)
    rejected = ok(boss.post(f"{API}/{batch['id']}/reject", json={"note": "Too low"}))
    assert rejected["status"] == "Rejected" and rejected["rejectedByName"] == "the.boss"
    assert boss.post(f"{API}/{batch['id']}/approve", json={}).status_code == 409

    # someone who may approve applies straight away and is recorded as the approver
    mine = ok(upload(boss, workbook(rows)), 201)
    done = ok(boss.post(f"{API}/{mine['id']}/confirm", json={"importAgain": True}))
    assert done["status"] == "Completed" and done["approvedByName"] == "the.boss"


def test_the_limit_is_configurable(settings: Settings, db: Engine, client: TestClient) -> None:
    boss = make_client(settings, db, {"inv.price.approve"}, user_id=APPROVER)
    url = "/api/v1/inv/price-settings"
    current = ok(boss.get(url))
    assert current["maxChangePct"] == "20"
    assert boss.put(url, json={"maxChangePct": "100"}).status_code == 428  # If-Match is required
    saved = ok(boss.put(url, json={"maxChangePct": "100"}, headers={"If-Match": current["rowVersion"]}))
    assert saved["maxChangePct"] == "100"
    # SQLite does not bump row_version on update, so stand in for "someone saved it meanwhile" with another one
    stale = boss.put(url, json={"maxChangePct": "50"}, headers={"If-Match": "AAAAAAAAAAE="})
    assert stale.status_code == 409
    assert client.put(url, json={"maxChangePct": "5"}, headers={"If-Match": saved["rowVersion"]}).status_code == 403
    batch = ok(upload(client, workbook([["SP001", "", 900, "", "", ""]])), 201)
    assert batch["overLimitCount"] == 0 and Decimal(batch["maxChangePct"]) == 100


def test_validation_of_prices_and_options(client: TestClient) -> None:
    rows = [["SP001", "", "abc", "", "", ""], ["SP002", "", -5, "", "", ""], ["SP003", "", "", "1,250.50", "", ""]]
    batch = ok(upload(client, workbook(rows)), 201)
    lines = lines_of(client, batch["id"])
    assert lines[2]["messages"] == ["Selling Price 'abc' is not a number."]
    assert lines[3]["messages"] == ["Selling Price cannot be negative."]
    assert lines[4]["newPurchase"] == "1250.5000" and lines[4]["action"] == "Change"

    no_list = ok(upload(client, workbook([ROWS[0]]), priceListId=""), 201)
    assert no_list["status"] == "Failed"  # a selling price needs a price list
    assert upload(client, workbook([ROWS[0]]), reason="").status_code in (400, 422)
    assert upload(client, workbook([ROWS[0]]), priceListId=str(OTHER_LIST)).status_code == 400  # not my brand
    assert ok(upload(client, workbook([["x"]], header=["Foo"])), 201)["status"] == "Failed"


def test_sap_price_file_updates_prices_within_the_brand(settings: Settings, db: Engine) -> None:
    client = make_client(settings, db, IMPORTER)
    sap = workbook(
        [
            [1, "534", "534", "CASE", "84314930", 120],
            [2, "0000999", "999", "NEW PART", "", 50],
            [3, "0000534", "", "", "", 0],
        ],
        header=["Sl No", "External ID (S4H)", "Material", "Description", "HSN Code", "ZAmount"],
    )
    files = {"file": ("sap.xlsx", sap, XLSX)}
    data = {"reason": "SAP price list", "sapPriceField": "MRP"}
    no_brand = ok(client.post(API, files=files, data=data), 201)
    assert no_brand["status"] == "Failed" and "brand" in no_brand["errorMessage"]

    batch = ok(client.post(API, files=files, data=data, headers={"X-Principal-Id": str(TATA)}), 201)
    assert batch["fileLayout"] == "SAP" and batch["sapPriceField"] == "MRP"
    lines = lines_of(client, batch["id"])
    assert lines[2]["itemCode"] == "0000534" and (lines[2]["oldMrp"], lines[2]["newMrp"]) == ("100.00", "120.00")
    assert "nothing is created" in lines[3]["messages"][0]  # unknown parts never become items
    assert "Zero or blank ZAmount" in lines[4]["messages"][0]


def test_error_report_template_and_permissions(settings: Settings, db: Engine, client: TestClient) -> None:
    batch = ok(upload(client, workbook(ROWS)), 201)
    report = client.get(f"{API}/{batch['id']}/error-report")
    sheet = load_workbook(BytesIO(report.content)).active
    assert sheet is not None
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0][:4] == ("Row", "Result", "Problems", "Item Code")
    assert [r[0] for r in rows[1:]] == [2, 3, 5, 6, 7, 8, 9]

    template = load_workbook(BytesIO(client.get(f"{API}/template").content))
    assert [c.value for c in template["Prices"][1]] == [
        "Sl No.", "External ID (S4H)", "Material", "Description", "HSN Code", "ZAmount",
    ]  # fmt: skip

    page = ok(client.get(f"{API}?search={batch['batchNo']}"))
    assert page["total"] == 1 and page["items"][0]["uploadedByName"] == "store.keeper"
    assert ok(client.get(f"{API}/uploaders")) == [{"id": ACTOR, "name": "store.keeper"}]

    viewer = make_client(settings, db, {"inv.price.import.view"})
    assert viewer.get(API).status_code == 200
    assert upload(viewer, workbook(ROWS)).status_code == 403
    assert make_client(settings, db, {"inv.item.manage"}).get(API).status_code == 403
