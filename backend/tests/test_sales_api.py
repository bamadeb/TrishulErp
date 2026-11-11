"""Sales: quotation -> order (approval, credit) -> delivery (FIFO batches) -> invoice -> receipt / advance (SQLite)."""

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
from trishul_api.db.models import CreditLimitChange, LotBalance, StockLot
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company", "core.principal", "core.state", "core.branch", "core.location", "core.uom", "core.hsn_sac",
    "core.item_category", "core.item", "core.customer", "core.customer_site", "core.number_series",
    "core.payment_terms", "core.app_user", "core.audit_log",
    "acc.gstin_registration",
    "inv.bin", "inv.movement_type", "inv.stock_lot", "inv.lot_balance", "inv.stock_balance", "inv.stock_move",
    "sal.credit_status", "sal.credit_limit_change", "sal.price_list", "sal.price_list_item", "sal.quotation",
    "sal.quotation_version", "sal.quotation_line", "sal.sales_order", "sal.sales_order_line", "sal.delivery_note",
    "sal.delivery_note_line", "sal.sales_invoice", "sal.sales_invoice_line", "sal.receipt",
    "sal.customer_allocation",
]  # fmt: skip
COMPANY, ODISHA, BIHAR = 1, 1, 2
BRAND = 1
BRANCH = 1
STORE = 11
FILTER_ITEM, OIL_ITEM, LABOUR = 41, 42, 43
CUSTOMER, FAR_CUSTOMER, LIMITED = 51, 52, 53
NET30 = 3
ACTOR_ID = 1
ALL = {
    "sal.customer.view", "sal.customer.manage", "sal.quotation.view", "sal.quotation.manage",
    "sal.quotation.approve", "sal.order.view", "sal.order.manage", "sal.order.approve", "sal.order.close",
    "sal.delivery.manage", "sal.delivery.over_order", "sal.account.view", "sal.invoice.manage",
    "sal.invoice.direct", "sal.invoice.cancel", "sal.receipt.manage", "sal.allocation.manage",
    "sal.allocation.reverse", "sal.credit.override",
}  # fmt: skip
API = "/api/v1/sal"
TODAY = date.today().isoformat()


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TREAD", legal_name="Trishul Tread Pvt. Ltd")
    insert_row(engine, "core.app_user", id=ACTOR_ID, username="seller", cognito_sub="x")
    insert_row(engine, "core.principal", id=BRAND, code="TATA_HITACHI", name="Tata Hitachi")
    insert_row(engine, "core.state", id=ODISHA, gst_state_code="21", name="Odisha")
    insert_row(engine, "core.state", id=BIHAR, gst_state_code="10", name="Bihar")
    insert_row(engine, "core.branch", id=BRANCH, company_id=COMPANY, code="BBSR", name="Bhubaneswar",
               branch_type="Warehouse", state_id=ODISHA)  # fmt: skip
    insert_row(engine, "core.location", id=STORE, branch_id=BRANCH, code="BBSR-MAIN", name="Main store",
               location_type="Main store", is_stock_location=True)  # fmt: skip
    insert_row(engine, "core.uom", id=1, code="EA", name="Each", decimals=0)
    insert_row(engine, "core.item_category", id=1, code="SP", name="Spare parts", item_nature="Spare part")
    for iid, code, kind in ((FILTER_ITEM, "KF70500", "Stock"), (OIL_ITEM, "TL07110", "Stock"),
                            (LABOUR, "LABOUR", "Service")):  # fmt: skip
        insert_row(engine, "core.item", id=iid, company_id=COMPANY, item_code=code, description=f"{code} item",
                   category_id=1, uom_id=1, item_type=kind)  # fmt: skip
    insert_row(engine, "core.payment_terms", id=NET30, code="NET30", description="30 days", days_before_due=30)
    for cid, code, state, limit in ((CUSTOMER, "C1", ODISHA, None), (FAR_CUSTOMER, "C2", BIHAR, None),
                                    (LIMITED, "C3", ODISHA, Decimal(1000))):  # fmt: skip
        insert_row(engine, "core.customer", id=cid, company_id=COMPANY, code=code, name=f"Customer {code}",
                   customer_type="Contractor", primary_phone="9437000000", billing_state_id=state,
                   billing_address=f"{code} road", payment_terms_id=NET30, credit_limit=limit,
                   opening_balance=Decimal(0), gst_registration_type="Regular")  # fmt: skip
    for doc, prefix in (("QUOTATION", "QT/"), ("SALES_ORDER", "SO/"), ("DELIVERY_NOTE", "DN/"),
                        ("SALES_INVOICE", "SI/"), ("CUSTOMER_RECEIPT", "RV/")):  # fmt: skip
        insert_row(engine, "core.number_series", company_id=COMPANY, branch_id=BRANCH, document_type=doc,
                   prefix=prefix, next_number=1, padding=3)  # fmt: skip
    for code, direction in (("SALE", "Out"), ("SALES_RETURN", "In")):
        insert_row(engine, "inv.movement_type", code=code, name=code.title(), direction=direction)
    # Stock: the filter in two GRN batches (older one cheaper), the oil in one.
    for lot_id, item, grn, grn_date, qty, cost in (
        (1, FILTER_ITEM, "GRN/A", date(2026, 1, 10), 6, 800),
        (2, FILTER_ITEM, "GRN/B", date(2026, 3, 1), 10, 900),
        (3, OIL_ITEM, "GRN/C", date(2026, 2, 1), 20, 400),
    ):
        insert_row(engine, "inv.stock_lot", id=lot_id, company_id=COMPANY, item_id=item, lot_no=f"LOT{lot_id}",
                   source_type="GRN", grn_no=grn, grn_date=grn_date, received_location_id=STORE,
                   unit_cost=Decimal(cost), qty_received=Decimal(qty))  # fmt: skip
        insert_row(engine, "inv.lot_balance", stock_lot_id=lot_id, item_id=item, location_id=STORE,
                   qty_on_hand=Decimal(qty))  # fmt: skip
    for item, qty in ((FILTER_ITEM, 16), (OIL_ITEM, 20)):
        insert_row(engine, "inv.stock_balance", item_id=item, location_id=STORE, qty_on_hand=Decimal(qty))
    return engine


def make_client(settings: Settings, db: Engine, permissions: set[str] = ALL) -> TestClient:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(id=ACTOR_ID, permissions=frozenset(permissions), branch_ids=None, principal_ids=None,
                      default_branch_id=BRANCH)  # fmt: skip
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


def d(value: Any) -> Any:
    return Decimal(str(value))


LINES = [
    {"itemId": FILTER_ITEM, "quantity": "10", "unitPrice": "1000", "discountPct": "10", "gstPct": "18"},
    {"itemId": OIL_ITEM, "quantity": "5", "unitPrice": "500", "gstPct": "18"},
]


def order(client: TestClient, customer: int = CUSTOMER, **changes: Any) -> dict[str, Any]:
    body = {"principalId": BRAND, "branchId": BRANCH, "customerId": customer, "lines": LINES} | changes
    result: dict[str, Any] = ok(client.post(f"{API}/sales-orders", json=body), 201)
    return result


def approved(client: TestClient, **changes: Any) -> dict[str, Any]:
    so = order(client, **changes)
    ok(client.post(f"{API}/sales-orders/{so['id']}/submit"))
    result: dict[str, Any] = ok(client.post(f"{API}/sales-orders/{so['id']}/approve", json={}))
    return result


def deliver(client: TestClient, so: dict[str, Any], quantities: dict[int, str], **changes: Any) -> dict[str, Any]:
    lines = [{"salesOrderLineId": line["id"], "quantity": quantities[line["itemId"]]}
             for line in so["lines"] if line["itemId"] in quantities]  # fmt: skip
    body = {"salesOrderId": so["id"], "locationId": STORE, "lines": lines} | changes
    result: dict[str, Any] = ok(client.post(f"{API}/deliveries", json=body), 201)
    return result


def invoice_all(client: TestClient, customer: int = CUSTOMER, **changes: Any) -> dict[str, Any]:
    rows = ok(client.get(f"{API}/uninvoiced-delivery-lines", params={"customerId": customer}))
    lines = [
        {"deliveryNoteLineId": r["deliveryNoteLineId"], "quantity": r["qtyToInvoice"], "unitPrice": r["unitPrice"],
         "discountPct": r["discountPct"], "gstPct": r["gstPct"]}
        for r in rows
    ]  # fmt: skip
    body = {"customerId": customer, "lines": lines} | changes
    result: dict[str, Any] = ok(client.post(f"{API}/invoices", json=body), 201)
    return result


def stock(db: Engine) -> list[tuple[str, Decimal]]:
    with Session(db) as s:
        rows = s.execute(select(StockLot.lot_no, LotBalance.qty_on_hand).join(LotBalance).order_by(StockLot.id))
        return [(lot, d(q)) for lot, q in rows]


# ---------------------------------------------------------------- quotations


def test_quotation_totals_revision_and_conversion_to_an_order(client: TestClient) -> None:
    body = {"principalId": BRAND, "branchId": BRANCH, "customerId": CUSTOMER, "otherCharges": "100", "lines": LINES}
    quote = ok(client.post(f"{API}/quotations", json=body), 201)
    # 10 x 1000 = 10000 less 10% = 9000; 5 x 500 = 2500; GST 18% on 11500 = 2070; + 100 freight.
    assert (quote["quotationNo"], quote["state"], quote["currentVersion"]) == ("QT/001", "Draft", 1)
    assert (d(quote["subtotal"]), d(quote["discountTotal"]), d(quote["taxableValue"])) == (12500, 1000, 11500)
    assert (d(quote["cgst"]), d(quote["sgst"]), d(quote["igst"]), d(quote["total"])) == (1035, 1035, 0, 13670)
    assert quote["validUntil"] == (date.today() + timedelta(days=30)).isoformat()

    url = f"{API}/quotations/{quote['id']}"
    assert ok(client.post(f"{url}/submit"))["state"] == "Submitted"  # the submitter may approve discounts
    revised = ok(client.post(f"{url}/revise", json={"note": "Customer asked for 12 filters"}))
    assert (revised["state"], revised["currentVersion"], len(revised["lines"])) == ("Draft", 2, 2)
    changed = ok(client.put(url, json=body | {"lines": [LINES[0] | {"quantity": "12"}, LINES[1]]},
                            headers={"If-Match": f'"{revised["rowVersion"]}"'}))  # fmt: skip
    assert d(changed["total"]) == 13670 + 1800 + 324  # 2 more filters at 900 + GST
    assert [(v["versionNo"], d(v["total"])) for v in changed["versions"]] == [(2, d(changed["total"])), (1, 13670)]

    ok(client.post(f"{url}/submit"))
    assert client.post(f"{url}/convert", json={}).status_code == 409  # not accepted yet
    ok(client.post(f"{url}/accept", json={"note": "PO by mail"}))
    so = ok(client.post(f"{url}/convert", json={"customerPoNo": "PO-77"}))
    assert (so["orderNo"], so["status"], so["quotationNo"], so["customerPoNo"]) == (
        "SO/001",
        "Draft",
        "QT/001",
        "PO-77",
    )
    assert [(line["itemCode"], d(line["quantity"])) for line in so["lines"]] == [("KF70500", 12), ("TL07110", 5)]
    assert d(so["total"]) == d(changed["total"])
    after = ok(client.get(url))
    assert (after["state"], after["orderNo"]) == ("Converted", "SO/001")


def test_discounts_need_approval_and_old_quotations_expire(client: TestClient, settings: Settings, db: Engine) -> None:
    body = {"principalId": BRAND, "branchId": BRANCH, "customerId": CUSTOMER, "lines": LINES}
    # Not entered with `with`: closing a second client would dispose the shared in-memory database.
    seller = make_client(settings, db, ALL - {"sal.quotation.approve"})
    quote = ok(seller.post(f"{API}/quotations", json=body), 201)
    assert ok(seller.post(f"{API}/quotations/{quote['id']}/submit"))["state"] == "Pending approval"
    assert seller.post(f"{API}/quotations/{quote['id']}/approve").status_code == 403
    approved_quote = ok(client.post(f"{API}/quotations/{quote['id']}/approve"))
    assert (approved_quote["state"], approved_quote["approvedBy"]) == ("Submitted", "seller")

    old = ok(client.post(f"{API}/quotations", json=body | {
        "quotationDate": (date.today() - timedelta(days=40)).isoformat(),
        "validUntil": (date.today() - timedelta(days=10)).isoformat()}), 201)  # fmt: skip
    assert ok(client.post(f"{API}/quotations/{old['id']}/submit"))["state"] == "Expired"
    assert client.post(f"{API}/quotations/{old['id']}/accept", json={}).status_code == 409
    expired = ok(client.get(f"{API}/quotations", params={"state": "Expired"}))["items"]
    assert [q["quotationNo"] for q in expired] == ["QT/002"]


# ---------------------------------------------------------------- orders and credit


def test_order_approval_checks_the_credit_limit(client: TestClient, settings: Settings, db: Engine) -> None:
    small = [{"itemId": OIL_ITEM, "quantity": "2", "unitPrice": "500", "gstPct": "18"}]  # 1180 > limit 1000
    so = order(client, customer=LIMITED, lines=small)
    assert (so["status"], so["paymentTerms"], d(so["total"])) == ("Draft", "30 days", 1180)
    url = f"{API}/sales-orders/{so['id']}"
    ok(client.post(f"{url}/submit"))
    blocked = client.post(f"{url}/approve", json={})
    assert blocked.status_code == 409 and "credit limit" in blocked.json()["detail"]
    manager = make_client(settings, db, ALL - {"sal.credit.override"})  # not closed: see above
    assert manager.post(f"{url}/approve", json={"overrideCredit": True}).status_code == 403
    done = ok(client.post(f"{url}/approve", json={"overrideCredit": True}))
    assert (done["status"], done["creditCheckStatus"], done["creditApprovedBy"]) == (
        "Approved", "Approved override", "seller"
    )  # fmt: skip

    within = approved(client)  # no limit: approved within
    assert within["creditCheckStatus"] == "Within limit"
    assert client.post(f"{API}/sales-orders/{within['id']}/cancel", json={}).status_code == 400  # reason needed


# ---------------------------------------------------------------- deliveries


def test_delivery_takes_the_oldest_batches_and_cancelling_puts_them_back(
    client: TestClient, settings: Settings, db: Engine
) -> None:
    so = approved(client)
    note = deliver(client, so, {FILTER_ITEM: "8"}, vehicleNo="OD02AB1234")
    assert (note["deliveryNo"], note["status"], note["orderNo"]) == ("DN/001", "Dispatched", "SO/001")
    line = note["lines"][0]
    assert [(b["grnNo"], d(b["quantity"])) for b in line["batches"]] == [("GRN/A", 6), ("GRN/B", 2)]
    assert d(line["unitCost"]) == 825  # (6 x 800 + 2 x 900) / 8
    assert stock(db) == [("LOT1", 0), ("LOT2", 8), ("LOT3", 20)]
    after = ok(client.get(f"{API}/sales-orders/{so['id']}"))
    assert after["status"] == "Part delivered"
    outstanding = ok(client.get(f"{API}/outstanding-order-lines"))["items"]
    assert [(o["itemCode"], d(o["qtyToDeliver"])) for o in outstanding] == [("KF70500", 2), ("TL07110", 5)]

    too_much = {"salesOrderId": so["id"], "locationId": STORE,
                "lines": [{"salesOrderLineId": so["lines"][0]["id"], "quantity": "3"}]}  # fmt: skip
    assert client.post(f"{API}/deliveries", json=too_much).status_code == 400
    clerk = make_client(settings, db, ALL - {"sal.delivery.over_order"})  # not closed: see above
    assert clerk.post(f"{API}/deliveries", json=too_much | {"overDeliver": True}).status_code == 403

    ok(client.post(f"{API}/deliveries/{note['id']}/confirm", json={"receivedByName": "Site store keeper"}))
    cancelled = ok(client.post(f"{API}/deliveries/{note['id']}/cancel", json={"reason": "Wrong items loaded"}))
    assert (cancelled["status"], cancelled["cancelledBy"]) == ("Cancelled", "seller")
    assert stock(db) == [("LOT1", 6), ("LOT2", 10), ("LOT3", 20)]  # same batches, same GRN dates
    back = ok(client.get(f"{API}/sales-orders/{so['id']}"))
    assert (back["status"], d(back["lines"][0]["qtyDelivered"])) == ("Approved", 0)


def test_direct_delivery_then_invoice(client: TestClient, db: Engine) -> None:
    body = {"principalId": BRAND, "branchId": BRANCH, "customerId": CUSTOMER, "locationId": STORE,
            "lines": [{"itemId": OIL_ITEM, "quantity": "4", "unitPrice": "450", "gstPct": "18"}]}  # fmt: skip
    note = ok(client.post(f"{API}/deliveries", json=body), 201)
    assert (note["salesOrderId"], d(note["totalQty"])) == (None, 4)
    assert stock(db)[2] == ("LOT3", 16)
    rows = ok(client.get(f"{API}/uninvoiced-delivery-lines", params={"customerId": CUSTOMER}))
    assert [(d(r["qtyToInvoice"]), d(r["unitPrice"])) for r in rows] == [(4, 450)]
    invoice = invoice_all(client)
    assert (invoice["sourceType"], invoice["deliveryNo"], d(invoice["total"])) == ("Delivery", "DN/001", 2124)
    assert stock(db)[2] == ("LOT3", 16)  # invoicing a delivery never takes stock again


# ---------------------------------------------------------------- invoices


def test_invoice_combines_deliveries_and_bills_each_line_once(client: TestClient) -> None:
    so = approved(client)
    first = deliver(client, so, {FILTER_ITEM: "4"})
    deliver(client, so, {FILTER_ITEM: "6", OIL_ITEM: "5"})
    invoice = invoice_all(client, otherCharges="100.40")
    # 9000 + 2500 = 11500; GST 2070; + 100.40 = 13670.40 -> 13670 (round off -0.40)
    assert (invoice["invoiceNo"], d(invoice["total"]), d(invoice["roundOff"])) == ("SI/001", 13670, Decimal("-0.40"))
    assert (invoice["deliveryNo"], invoice["orderNo"]) == (None, "SO/001")  # two deliveries, one order
    assert invoice["dueDate"] == (date.today() + timedelta(days=30)).isoformat()
    assert (invoice["state"], d(invoice["outstanding"])) == ("Unpaid", 13670)
    assert [line["deliveryNo"] for line in invoice["lines"]] == ["DN/001", "DN/002", "DN/002"]
    assert ok(client.get(f"{API}/sales-orders/{so['id']}"))["status"] == "Invoiced"
    assert ok(client.get(f"{API}/uninvoiced-delivery-lines", params={"customerId": CUSTOMER})) == []

    twice = {"customerId": CUSTOMER, "lines": [
        {"deliveryNoteLineId": first["lines"][0]["id"], "quantity": "1", "unitPrice": "900"}]}  # fmt: skip
    assert client.post(f"{API}/invoices", json=twice).status_code == 400
    assert client.post(f"{API}/deliveries/{first['id']}/cancel", json={"reason": "late"}).status_code == 409

    cancelled = ok(client.post(f"{API}/invoices/{invoice['id']}/cancel", json={"reason": "Wrong GSTIN"}))
    assert (cancelled["state"], cancelled["cancelledBy"]) == ("Cancelled", "seller")
    assert ok(client.get(f"{API}/sales-orders/{so['id']}"))["status"] == "Delivered"
    assert len(ok(client.get(f"{API}/uninvoiced-delivery-lines", params={"customerId": CUSTOMER}))) == 3


def test_direct_invoice_takes_stock_and_needs_permission(client: TestClient, settings: Settings, db: Engine) -> None:
    body = {"customerId": CUSTOMER, "principalId": BRAND, "branchId": BRANCH, "locationId": STORE, "lines": [
        {"itemId": OIL_ITEM, "quantity": "3", "unitPrice": "450", "gstPct": "18"},
        {"itemId": LABOUR, "description": "Fitting labour", "quantity": "1", "unitPrice": "1000", "gstPct": "18"},
    ]}  # fmt: skip
    clerk = make_client(settings, db, ALL - {"sal.invoice.direct"})  # not closed: see above
    assert clerk.post(f"{API}/invoices", json=body).status_code == 403
    assert client.post(f"{API}/invoices", json=body | {"locationId": None}).status_code == 400  # where from?
    invoice = ok(client.post(f"{API}/invoices", json=body), 201)
    assert (invoice["isDirect"], invoice["sourceType"], d(invoice["total"])) == (True, "Direct", 2773)
    assert stock(db)[2] == ("LOT3", 17)  # the service line takes no stock
    ok(client.post(f"{API}/invoices/{invoice['id']}/cancel", json={"reason": "Duplicate"}))
    assert stock(db)[2] == ("LOT3", 20)


def test_inter_state_customer_pays_igst_unless_its_branch_is_local(client: TestClient) -> None:
    far = order(client, customer=FAR_CUSTOMER)
    assert (d(far["cgst"]), d(far["igst"]), far["placeOfSupply"]) == (0, 2070, "Bihar")
    site = {"siteCode": "ctk", "siteName": "Cuttack site", "address": "Ring road, Cuttack", "stateId": ODISHA}
    branch = ok(client.post(f"{API}/customers/{FAR_CUSTOMER}/branches", json=site))
    assert (branch["siteCode"], branch["isDefault"], branch["stateName"]) == ("CTK", True, "Odisha")
    local = order(client, customer=FAR_CUSTOMER, customerSiteId=branch["id"])
    assert (d(local["cgst"]), d(local["igst"]), local["shipToAddress"]) == (1035, 0, "Ring road, Cuttack")
    duplicate = {"siteCode": "CTK", "siteName": "Other", "address": "x"}
    assert client.post(f"{API}/customers/{FAR_CUSTOMER}/branches", json=duplicate).status_code == 409
    assert client.post(f"{API}/customers/{CUSTOMER}/branches", json=duplicate).status_code == 200  # per customer


# ---------------------------------------------------------------- receipts, advances, statements


def test_prepaid_order_advance_is_adjusted_once(client: TestClient) -> None:
    so = approved(client, isPrepaid=True, lines=[{"itemId": OIL_ITEM, "quantity": "10", "unitPrice": "500",
                                                  "gstPct": "18"}])  # 5900  # fmt: skip
    advance = ok(client.post(f"{API}/receipts", json={
        "customerId": CUSTOMER, "branchId": BRANCH, "receiptDate": TODAY, "receiptType": "Order advance",
        "salesOrderId": so["id"], "paymentMode": "UPI", "amount": "5000", "referenceNo": "UPI-9"}), 201)  # fmt: skip
    assert (advance["receiptNo"], advance["orderNo"], d(advance["unallocated"])) == ("RV/001", "SO/001", 5000)
    assert d(ok(client.get(f"{API}/sales-orders/{so['id']}"))["advanceReceived"]) == 5000

    deliver(client, so, {OIL_ITEM: "6"})
    first = invoice_all(client)  # 6 x 500 + 18% = 3540, all from the advance
    assert (d(first["advanceAdjusted"]), first["state"]) == (3540, "Paid")
    deliver(client, so, {OIL_ITEM: "4"})
    second = invoice_all(client)  # 2360, only 1460 of the advance is left
    assert (d(second["advanceAdjusted"]), d(second["outstanding"]), second["state"]) == (1460, 900, "Partially paid")
    after = ok(client.get(f"{API}/sales-orders/{so['id']}"))
    assert (d(after["advanceAdjusted"]), d(after["advanceRemaining"]), d(after["invoicedAmount"])) == (5000, 0, 5900)
    assert after["status"] == "Invoiced"
    assert d(ok(client.get(f"{API}/customers/{CUSTOMER}"))["balance"]) == 900  # 5900 invoiced - 5000 received


def test_receipts_allocate_and_the_statement_runs_the_balance(client: TestClient) -> None:
    body = {"customerId": CUSTOMER, "principalId": BRAND, "branchId": BRANCH, "locationId": STORE,
            "lines": [{"itemId": OIL_ITEM, "quantity": "2", "unitPrice": "500", "gstPct": "18"}]}  # fmt: skip
    invoice = ok(client.post(f"{API}/invoices", json=body), 201)  # 1180
    receipt = ok(client.post(f"{API}/receipts", json={
        "customerId": CUSTOMER, "branchId": BRANCH, "receiptDate": TODAY, "receiptType": "Against invoice",
        "paymentMode": "NEFT", "amount": "2000", "referenceNo": "UTR1",
        "allocations": [{"salesInvoiceId": invoice["id"], "amount": "1180"}]}), 201)  # fmt: skip
    assert (d(receipt["allocated"]), d(receipt["unallocated"])) == (1180, 820)
    assert receipt["amountInWords"] == "Rupees two thousand only"
    assert ok(client.get(f"{API}/invoices/{invoice['id']}"))["state"] == "Paid"

    account = ok(client.get(f"{API}/customers/{CUSTOMER}"))
    assert (d(account["balance"]), d(account["unallocated"])) == (-820, 820)
    statement = ok(client.get(f"{API}/customers/{CUSTOMER}/statement"))
    assert [(e["entryType"], e["balance"] and d(e["balance"])) for e in statement["entries"]] == [
        ("Invoice", 1180), ("Receipt", -820)
    ]  # fmt: skip
    assert client.post(f"{API}/receipts", json={
        "customerId": CUSTOMER, "branchId": BRANCH, "receiptDate": TODAY, "receiptType": "Advance",
        "paymentMode": "Cheque", "amount": "1"}).status_code == 400  # a cheque needs its number  # fmt: skip

    allocation = ok(client.get(f"{API}/allocations"))["items"][0]
    reversed_ = ok(client.post(f"{API}/allocations/{allocation['id']}/reverse", json={"reason": "Wrong invoice"}))
    assert (reversed_["isActive"], reversed_["reversedBy"]) == (False, "seller")
    assert ok(client.get(f"{API}/invoices/{invoice['id']}"))["state"] == "Unpaid"


def test_credit_terms_change_is_logged(client: TestClient, db: Engine) -> None:
    account = ok(client.get(f"{API}/customers/{CUSTOMER}"))
    changed = ok(client.patch(f"{API}/customers/{CUSTOMER}/credit-terms",
                              json={"creditLimit": "50000", "reason": "Annual review"},
                              headers={"If-Match": f'"{account["rowVersion"]}"'}))  # fmt: skip
    assert (d(changed["creditLimit"]), d(changed["availableCredit"])) == (50000, 50000)
    with Session(db) as s:
        logged = s.scalars(select(CreditLimitChange)).one()
        assert (logged.old_credit_limit, d(logged.new_credit_limit), logged.reason) == (None, 50000, "Annual review")
    options = ok(client.get(f"{API}/form-options"))
    assert ([b["code"] for b in options["brands"]], options["defaultBranchId"]) == (["TATA_HITACHI"], BRANCH)
    info = ok(client.get(f"{API}/items/{FILTER_ITEM}/sale-info"))
    assert [(s["locationName"], d(s["qtyOnHand"])) for s in info["stock"]] == [("Main store", 16)]
