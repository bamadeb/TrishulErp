"""Purchases: order -> approval -> GRN (partial) -> invoice -> payment / credit note -> allocation (SQLite)."""

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
from trishul_api.db.models import LotBalance, StockLot
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company", "core.principal", "core.state", "core.branch", "core.location", "core.uom", "core.hsn_sac",
    "core.item_category", "core.item", "core.supplier", "core.currency", "core.number_series", "core.payment_terms",
    "core.lookup_type", "core.lookup_value", "core.app_user", "core.audit_log",
    "inv.bin", "inv.movement_type", "inv.uom_conversion", "inv.stock_lot", "inv.lot_balance", "inv.stock_balance",
    "inv.stock_move",
    "pur.purchase_order", "pur.purchase_order_line", "pur.grn", "pur.grn_line", "pur.supplier_invoice",
    "pur.supplier_invoice_line", "pur.supplier_payment", "pur.debit_note", "pur.debit_note_line",
    "pur.supplier_allocation",
]  # fmt: skip
COMPANY, ODISHA, BIHAR = 1, 1, 2
BRANCH = 1
STORE = 11
FILTER_ITEM, OIL_ITEM = 41, 42
SUPPLIER, FAR_SUPPLIER = 51, 52
NET30 = 3
DAMAGED = 71
ACTOR_ID = 1
ALL = {
    "pur.supplier.view", "pur.supplier.manage", "pur.po.view", "pur.po.manage", "pur.po.approve", "pur.po.close",
    "pur.grn.manage", "pur.account.view", "pur.invoice.manage", "pur.invoice.direct", "pur.payment.manage",
    "pur.credit_note.manage", "pur.allocation.manage", "pur.allocation.reverse",
}  # fmt: skip
API = "/api/v1/pur"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TREAD", legal_name="Trishul Tread Pvt. Ltd")
    insert_row(engine, "core.currency", id=1, code="INR", name="Rupee")
    insert_row(engine, "core.app_user", id=ACTOR_ID, username="buyer", cognito_sub="x")
    insert_row(engine, "core.state", id=ODISHA, gst_state_code="21", name="Odisha")
    insert_row(engine, "core.state", id=BIHAR, gst_state_code="10", name="Bihar")
    insert_row(engine, "core.branch", id=BRANCH, company_id=COMPANY, code="BBSR", name="Bhubaneswar",
               branch_type="Warehouse", state_id=ODISHA)  # fmt: skip
    insert_row(engine, "core.location", id=STORE, branch_id=BRANCH, code="BBSR-MAIN", name="Main store",
               location_type="Main store", is_stock_location=True)  # fmt: skip
    insert_row(engine, "core.uom", id=1, code="EA", name="Each", decimals=0)
    insert_row(engine, "core.item_category", id=1, code="SP", name="Spare parts", item_nature="Spare part")
    for iid, code in ((FILTER_ITEM, "KF70500"), (OIL_ITEM, "TL07110")):
        insert_row(engine, "core.item", id=iid, company_id=COMPANY, item_code=code, description=f"{code} item",
                   category_id=1, uom_id=1, item_type="Stock")  # fmt: skip
    insert_row(engine, "core.payment_terms", id=NET30, code="NET30", description="30 days", days_before_due=30)
    insert_row(engine, "core.supplier", id=SUPPLIER, company_id=COMPANY, code="TH", name="Tata Hitachi",
               supplier_type="OEM", state_id=ODISHA, payment_terms_id=NET30, opening_balance=Decimal(1000))  # fmt: skip
    insert_row(engine, "core.supplier", id=FAR_SUPPLIER, company_id=COMPANY, code="FAR", name="Patna Parts",
               supplier_type="Parts", state_id=BIHAR, opening_balance=Decimal(0))  # fmt: skip
    for doc, prefix in (("PURCHASE_ORDER", "PO/"), ("GRN", "GRN/"), ("SUPPLIER_INVOICE", "PI/"),
                        ("SUPPLIER_PAYMENT", "PV/"), ("SUPPLIER_CREDIT_NOTE", "SCN/")):  # fmt: skip
        insert_row(engine, "core.number_series", company_id=COMPANY, branch_id=BRANCH, document_type=doc,
                   prefix=prefix, next_number=1, padding=3)  # fmt: skip
    for code, direction in (("GRN", "In"), ("PURCHASE_RETURN", "Out")):
        insert_row(engine, "inv.movement_type", code=code, name=code.title(), direction=direction)
    insert_row(engine, "core.lookup_type", id=9, code="RETURN_REASON", name="Return Reason")
    insert_row(engine, "core.lookup_value", id=DAMAGED, lookup_type_id=9, code="DAMAGED", label="Damaged")
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


def order(client: TestClient, supplier: int = SUPPLIER, **changes: Any) -> dict[str, Any]:
    body = {
        "supplierId": supplier,
        "deliveryLocationId": STORE,
        "expectedDate": (date.today() + timedelta(days=7)).isoformat(),
        "otherCharges": "100",
        "lines": [
            {"itemId": FILTER_ITEM, "quantity": "10", "unitPrice": "1000", "discountPct": "10", "gstPct": "18"},
            {"itemId": OIL_ITEM, "quantity": "5", "unitPrice": "500", "gstPct": "18"},
        ],
    } | changes
    result: dict[str, Any] = ok(client.post(f"{API}/purchase-orders", json=body), 201)
    return result


def approved(client: TestClient, **changes: Any) -> dict[str, Any]:
    po = order(client, **changes)
    ok(client.post(f"{API}/purchase-orders/{po['id']}/submit"))
    result: dict[str, Any] = ok(client.post(f"{API}/purchase-orders/{po['id']}/approve", json={}))
    return result


def receive(client: TestClient, po: dict[str, Any], quantities: dict[int, str], **changes: Any) -> dict[str, Any]:
    lines = [
        {"itemId": line["itemId"], "quantity": quantities[line["itemId"]], "unitCost": line["netPrice"],
         "purchaseOrderLineId": line["id"]}
        for line in po["lines"] if line["itemId"] in quantities
    ]  # fmt: skip
    body = {"locationId": STORE, "supplierId": po["supplierId"], "purchaseOrderId": po["id"],
            "grnDate": date.today().isoformat(), "lines": lines} | changes  # fmt: skip
    result: dict[str, Any] = ok(client.post(f"{API}/grns", json=body), 201)
    return result


def invoice_from(client: TestClient, grn: dict[str, Any], number: str, **changes: Any) -> dict[str, Any]:
    open_lines = ok(client.get(f"{API}/uninvoiced-grn-lines", params={"supplierId": SUPPLIER, "grnId": grn["id"]}))
    lines = [
        {"grnLineId": row["grnLineId"], "quantity": row["qtyToInvoice"], "unitPrice": row["unitPrice"],
         "discountPct": row["discountPct"], "gstPct": row["gstPct"]}
        for row in open_lines
    ]  # fmt: skip
    body = {"supplierId": SUPPLIER, "supplierInvoiceNo": number, "supplierInvoiceDate": date.today().isoformat(),
            "lines": lines} | changes  # fmt: skip
    result: dict[str, Any] = ok(client.post(f"{API}/supplier-invoices", json=body), 201)
    return result


# ---------------------------------------------------------------- orders


def test_order_totals_split_gst_by_state_and_follow_the_approval_flow(client: TestClient) -> None:
    po = order(client)
    # 10 x 1000 less 10% = 9000, 5 x 500 = 2500; GST 18% = 2070; + 100 other charges.
    assert (po["poNo"], po["status"]) == ("PO/001", "Draft")
    assert (d(po["subtotal"]), d(po["taxTotal"]), d(po["total"])) == (11500, 2070, 13670)
    assert (d(po["cgst"]), d(po["sgst"]), d(po["igst"])) == (1035, 1035, 0)  # same state: CGST + SGST
    assert d(po["lines"][0]["netPrice"]) == 900
    assert po["paymentTerms"] == "30 days"  # the supplier's terms

    far = order(client, supplier=FAR_SUPPLIER)
    assert (d(far["cgst"]), d(far["igst"])) == (0, 2070)  # another state: IGST

    # A GRN can't be posted against an order that isn't approved.
    lines = [{"itemId": FILTER_ITEM, "quantity": "1", "unitCost": "900", "purchaseOrderLineId": po["lines"][0]["id"]}]
    body = {"locationId": STORE, "supplierId": SUPPLIER, "purchaseOrderId": po["id"],
            "grnDate": date.today().isoformat(), "lines": lines}  # fmt: skip
    assert client.post(f"{API}/grns", json=body).status_code == 409

    url = f"{API}/purchase-orders/{po['id']}"
    changed = ok(client.put(url, json={"supplierId": SUPPLIER, "deliveryLocationId": STORE, "lines": [
        {"itemId": OIL_ITEM, "quantity": "2", "unitPrice": "500", "gstPct": "18"}]},
        headers={"If-Match": f'"{po["rowVersion"]}"'}))  # fmt: skip
    assert d(changed["total"]) == 1180 and len(changed["lines"]) == 1
    submitted = ok(client.post(f"{url}/submit"))
    assert submitted["status"] == "Pending approval"
    assert client.put(url, json={"supplierId": SUPPLIER, "deliveryLocationId": STORE, "lines": [
        {"itemId": OIL_ITEM, "quantity": "1", "unitPrice": "1"}]},
        headers={"If-Match": f'"{submitted["rowVersion"]}"'}).status_code == 409  # fmt: skip
    assert client.post(f"{url}/reject", json={}).status_code == 400  # a reason is needed
    assert ok(client.post(f"{url}/reject", json={"note": "Wrong price"}))["status"] == "Draft"
    ok(client.post(f"{url}/submit"))
    done = ok(client.post(f"{url}/approve", json={"note": "OK"}))
    assert (done["status"], done["approvedBy"]) == ("Approved", "buyer")


def test_only_approvers_approve(client: TestClient, settings: Settings, db: Engine) -> None:
    po = order(client)
    ok(client.post(f"{API}/purchase-orders/{po['id']}/submit"))
    restricted = make_client(settings, db, ALL - {"pur.po.approve"})  # not closed: see test_direct_invoices
    assert restricted.post(f"{API}/purchase-orders/{po['id']}/approve", json={}).status_code == 403


def test_partial_receipts_update_the_order_and_the_outstanding_list(client: TestClient, db: Engine) -> None:
    po = approved(client)
    filter_line = po["lines"][0]
    grn = receive(client, po, {FILTER_ITEM: "4"})
    assert (grn["poNo"], d(grn["totalQty"]), d(grn["totalValue"])) == ("PO/001", 4, 3600)
    after = ok(client.get(f"{API}/purchase-orders/{po['id']}"))
    assert after["status"] == "Part received"
    assert [(d(row["qtyReceived"]), d(row["qtyPending"])) for row in after["lines"]] == [(4, 6), (0, 5)]
    outstanding = ok(client.get(f"{API}/outstanding-po-lines"))["items"]
    assert [(o["itemCode"], d(o["qtyPending"]), d(o["pendingValue"])) for o in outstanding] == [
        ("KF70500", 6, 5400),
        ("TL07110", 5, 2500),
    ]
    # No more than is pending.
    too_much = {"locationId": STORE, "supplierId": SUPPLIER, "purchaseOrderId": po["id"],
                "grnDate": date.today().isoformat(),
                "lines": [{"itemId": FILTER_ITEM, "quantity": "7", "unitCost": "900",
                           "purchaseOrderLineId": filter_line["id"]}]}  # fmt: skip
    assert client.post(f"{API}/grns", json=too_much).status_code == 400

    receive(client, po, {FILTER_ITEM: "6", OIL_ITEM: "5"})
    assert ok(client.get(f"{API}/purchase-orders/{po['id']}"))["status"] == "Received"
    assert ok(client.get(f"{API}/outstanding-po-lines"))["total"] == 0
    assert len(ok(client.get(f"{API}/purchase-orders/{po['id']}"))["grns"]) == 2
    with Session(db) as s:
        assert sorted(d(q) for q in s.scalars(select(LotBalance.qty_on_hand))) == [4, 5, 6]  # one batch per GRN line

    # A received order can't be cancelled; an open one is closed instead.
    assert client.post(f"{API}/purchase-orders/{po['id']}/cancel", json={"note": "x"}).status_code == 409
    other = approved(client)
    receive(client, other, {OIL_ITEM: "1"})
    closed = ok(client.post(f"{API}/purchase-orders/{other['id']}/close", json={"note": "Rest not available"}))
    assert closed["status"] == "Closed"
    assert ok(client.get(f"{API}/purchase-orders", params={"outstandingOnly": True}))["total"] == 0


def test_direct_grn_without_an_order(client: TestClient) -> None:
    body = {"locationId": STORE, "supplierId": SUPPLIER, "grnDate": date.today().isoformat(),
            "lines": [{"itemId": OIL_ITEM, "quantity": "3", "unitCost": "450"}]}  # fmt: skip
    grn = ok(client.post(f"{API}/grns", json=body), 201)
    assert (grn["purchaseOrderId"], d(grn["totalValue"])) == (None, 1350)
    lines = ok(client.get(f"{API}/uninvoiced-grn-lines", params={"supplierId": SUPPLIER}))
    assert [(d(row["qtyToInvoice"]), d(row["unitPrice"]), d(row["gstPct"])) for row in lines] == [(3, 450, 18)]


# ---------------------------------------------------------------- invoices, payments, credit notes


def test_invoice_bills_each_grn_line_once_and_never_twice_per_number(client: TestClient) -> None:
    po = approved(client)
    grn = receive(client, po, {FILTER_ITEM: "10", OIL_ITEM: "5"})
    invoice = invoice_from(client, grn, "TH/INV/1", otherCharges="100.40")
    # 9000 + 2500 = 11500; GST 2070; + 100.40 = 13670.40 -> 13670 (round off -0.40)
    assert (invoice["invoiceNo"], d(invoice["total"]), d(invoice["roundOff"])) == ("PI/001", 13670, Decimal("-0.40"))
    assert invoice["dueDate"] == (date.today() + timedelta(days=30)).isoformat()  # NET30
    assert (invoice["state"], d(invoice["outstanding"]), invoice["grnNo"]) == ("Unpaid", 13670, "GRN/001")
    assert ok(client.get(f"{API}/uninvoiced-grn-lines", params={"supplierId": SUPPLIER})) == []
    assert [d(row["qtyInvoiced"]) for row in ok(client.get(f"{API}/purchase-orders/{po['id']}"))["lines"]] == [10, 5]

    again = {"supplierId": SUPPLIER, "supplierInvoiceNo": "th/inv/1", "supplierInvoiceDate": date.today().isoformat(),
             "lines": [{"description": "Freight", "quantity": "1", "unitPrice": "10"}]}  # fmt: skip
    assert client.post(f"{API}/supplier-invoices", json=again).status_code == 409  # same number, any case
    twice = {**again, "supplierInvoiceNo": "TH/INV/2",
             "lines": [{"grnLineId": grn["lines"][0]["id"], "quantity": "1", "unitPrice": "900"}]}  # fmt: skip
    assert client.post(f"{API}/supplier-invoices", json=twice).status_code == 400  # GRN line already billed


def test_direct_invoices_need_permission(settings: Settings, db: Engine) -> None:
    labour = {"description": "Machine repair labour", "quantity": "1", "unitPrice": "2000", "gstPct": "18"}
    body = {"supplierId": SUPPLIER, "branchId": BRANCH, "supplierInvoiceNo": "SVC-9",
            "supplierInvoiceDate": date.today().isoformat(), "lines": [labour]}  # fmt: skip
    # Not entered with `with`: closing a second client would dispose the shared in-memory database.
    restricted = make_client(settings, db, ALL - {"pur.invoice.direct"})
    assert restricted.post(f"{API}/supplier-invoices", json=body).status_code == 403
    with make_client(settings, db) as client:
        invoice = ok(client.post(f"{API}/supplier-invoices", json=body), 201)
        assert (invoice["isDirect"], d(invoice["total"])) == (True, 2360)


def test_payments_allocate_partly_and_the_rest_stays_an_advance(client: TestClient) -> None:
    grn = receive(client, approved(client), {FILTER_ITEM: "10", OIL_ITEM: "5"})
    invoice = invoice_from(client, grn, "TH/INV/1")  # 13570 (no other charges)
    first = [{"supplierInvoiceId": invoice["id"], "amount": "5000"}]
    payment = ok(client.post(f"{API}/supplier-payments", json={
        "supplierId": SUPPLIER, "branchId": BRANCH, "paymentDate": date.today().isoformat(), "paymentMode": "NEFT",
        "amount": "15000", "referenceNo": "UTR123", "allocations": first,
    }), 201)  # fmt: skip
    assert (payment["paymentNo"], d(payment["allocated"]), d(payment["unallocated"])) == ("PV/001", 5000, 10000)
    assert payment["amountInWords"] == "Rupees fifteen thousand only"
    part = ok(client.get(f"{API}/supplier-invoices/{invoice['id']}"))
    assert (part["state"], d(part["outstanding"])) == ("Partially paid", 8570)

    over = {"supplierPaymentId": payment["id"], "allocations": [{"supplierInvoiceId": invoice["id"], "amount": "9000"}]}
    assert client.post(f"{API}/allocations", json=over).status_code == 400  # more than is outstanding
    rest = {"supplierPaymentId": payment["id"], "allocations": [{"supplierInvoiceId": invoice["id"], "amount": "8570"}]}
    ok(client.post(f"{API}/allocations", json=rest), 201)
    assert ok(client.get(f"{API}/supplier-invoices/{invoice['id']}"))["state"] == "Paid"

    items = ok(client.get(f"{API}/suppliers/{SUPPLIER}/open-items"))
    assert items["invoices"] == []
    assert [(c["kind"], d(c["unallocated"])) for c in items["credits"]] == [("Payment", 1430)]  # advance
    # Opening 1000 + invoice 13570 - payment 15000 = -430 (we paid 430 ahead of the opening balance).
    assert d(ok(client.get(f"{API}/suppliers/{SUPPLIER}"))["balance"]) == -430
    assert client.post(f"{API}/supplier-payments", json={
        "supplierId": SUPPLIER, "branchId": BRANCH, "paymentDate": date.today().isoformat(), "paymentMode": "Cheque",
        "amount": "1"}).status_code == 400  # a cheque needs its number  # fmt: skip


def test_purchase_return_credit_note_takes_stock_back_and_settles_the_invoice(client: TestClient, db: Engine) -> None:
    grn = receive(client, approved(client), {FILTER_ITEM: "10"})
    invoice = invoice_from(client, grn, "TH/INV/1")  # 9000 + 1620 GST = 10620
    note = ok(client.post(f"{API}/credit-notes", json={
        "supplierId": SUPPLIER, "branchId": BRANCH, "noteType": "Purchase return", "noteDate": date.today().isoformat(),
        "supplierNoteNo": "TH/CN/7", "supplierInvoiceId": invoice["id"], "locationId": STORE, "reasonId": DAMAGED,
        "lines": [{"itemId": FILTER_ITEM, "quantity": "2", "unitPrice": "900", "gstPct": "18",
                   "grnLineId": grn["lines"][0]["id"]}],
    }), 201)  # fmt: skip
    assert (note["debitNoteNo"], d(note["total"]), note["reason"]) == ("SCN/001", 2124, "Damaged")
    assert (d(note["allocated"]), note["lines"][0]["grnNo"]) == (2124, "GRN/001")  # set against the invoice
    assert d(ok(client.get(f"{API}/supplier-invoices/{invoice['id']}"))["outstanding"]) == 10620 - 2124
    with Session(db) as s:
        stock = s.execute(select(StockLot.grn_no, LotBalance.qty_on_hand).join(LotBalance)).all()
        assert [(n, d(q)) for n, q in stock] == [("GRN/001", 8)]
    duplicate = {"supplierId": SUPPLIER, "branchId": BRANCH, "noteType": "Price difference",
                 "noteDate": date.today().isoformat(), "supplierNoteNo": "TH/CN/7",
                 "lines": [{"description": "Rate difference", "quantity": "1", "unitPrice": "100"}]}  # fmt: skip
    assert client.post(f"{API}/credit-notes", json=duplicate).status_code == 409


def test_reversing_an_allocation_keeps_the_history(client: TestClient, settings: Settings, db: Engine) -> None:
    grn = receive(client, approved(client), {OIL_ITEM: "2"})
    invoice = invoice_from(client, grn, "TH/INV/1")  # 1180
    ok(client.post(f"{API}/supplier-payments", json={
        "supplierId": SUPPLIER, "branchId": BRANCH, "paymentDate": date.today().isoformat(),
        "paymentMode": "Cash", "amount": "1180",
        "allocations": [{"supplierInvoiceId": invoice["id"], "amount": "1180"}]}), 201)  # fmt: skip
    allocation = ok(client.get(f"{API}/allocations"))["items"][0]
    reverse_url = f"{API}/allocations/{allocation['id']}/reverse"

    restricted = make_client(settings, db, ALL - {"pur.allocation.reverse"})  # not closed: see above
    assert restricted.post(reverse_url, json={"reason": "Wrong invoice"}).status_code == 403

    reversed_ = ok(client.post(reverse_url, json={"reason": "Wrong invoice"}))
    assert (reversed_["isActive"], reversed_["reversedBy"], reversed_["reversalReason"]) == (
        False,
        "buyer",
        "Wrong invoice",
    )
    assert ok(client.get(f"{API}/supplier-invoices/{invoice['id']}"))["state"] == "Unpaid"
    history = ok(client.get(f"{API}/allocations", params={"supplierInvoiceId": invoice["id"]}))["items"]
    assert [h["isActive"] for h in history] == [False]
    assert ok(client.get(f"{API}/allocations", params={"includeReversed": False}))["total"] == 0
    assert client.post(reverse_url, json={"reason": "again"}).status_code == 409


def test_statement_has_opening_and_closing_balances(client: TestClient) -> None:
    grn = receive(client, approved(client), {OIL_ITEM: "2"})
    invoice_from(client, grn, "TH/INV/1")  # 1180
    ok(client.post(f"{API}/supplier-payments", json={
        "supplierId": SUPPLIER, "branchId": BRANCH, "paymentDate": date.today().isoformat(), "paymentMode": "UPI",
        "amount": "500", "referenceNo": "UPI-1"}), 201)  # fmt: skip
    statement = ok(client.get(f"{API}/suppliers/{SUPPLIER}/statement"))
    assert [e["entryType"] for e in statement["entries"]] == ["Purchase order", "GRN", "Invoice", "Payment"]
    assert (d(statement["openingBalance"]), d(statement["closingBalance"])) == (1000, 1680)
    assert [e["balance"] and d(e["balance"]) for e in statement["entries"]] == [None, None, 2180, 1680]
    later = ok(client.get(f"{API}/suppliers/{SUPPLIER}/statement",
                          params={"fromDate": (date.today() + timedelta(days=1)).isoformat()}))  # fmt: skip
    assert (d(later["openingBalance"]), later["entries"]) == (1680, [])
