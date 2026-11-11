import datetime as dt
from decimal import Decimal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models import PurchaseOrderPoType, PurchaseOrderStatus

_QTY = Field(gt=0, max_digits=18, decimal_places=3)
_PCT = Field(Decimal(0), ge=0, le=100, max_digits=5, decimal_places=2)


class PoQuery(PageQuery):
    status: PurchaseOrderStatus | None = None
    supplier_id: int | None = None
    branch_id: int | None = None
    item_id: int | None = Field(None, description="Orders with a line for this item.")
    from_date: dt.date | None = None
    to_date: dt.date | None = None
    outstanding_only: bool = Field(False, description="Approved orders with quantity still to receive.")


class PoListItem(ApiModel):
    id: int
    po_no: str
    po_date: dt.date
    expected_date: dt.date | None
    supplier_id: int
    supplier_name: str
    branch_id: int
    branch_name: str
    location_name: str
    status: PurchaseOrderStatus
    total: Decimal
    line_count: int
    qty_ordered: Decimal
    qty_received: Decimal
    qty_pending: Decimal
    created_at: UtcDateTime


class PoLineIn(InputModel):
    item_id: int
    quantity: Decimal = _QTY
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4, description="Per stock unit, before GST.")
    discount_pct: Decimal = _PCT
    gst_pct: Decimal = Field(Decimal(18), ge=0, le=100, max_digits=5, decimal_places=2)
    description: str | None = Field(None, max_length=200)


class PoCreate(InputModel):
    supplier_id: int
    delivery_location_id: int = Field(description="The stock location goods are to be delivered to.")
    po_date: dt.date | None = Field(None, description="Default today.")
    expected_date: dt.date | None = None
    payment_terms_id: int | None = Field(None, description="Default: the supplier's terms.")
    po_type: PurchaseOrderPoType = "Local"
    other_charges: Decimal = Field(Decimal(0), ge=0, max_digits=18, decimal_places=2, description="Freight, packing.")
    oem_po_ref: str | None = Field(None, max_length=40)
    remarks: str | None = Field(None, max_length=500)
    lines: list[PoLineIn] = Field(min_length=1, max_length=200)


class PoNote(InputModel):
    note: str | None = Field(None, max_length=300, description="Why (needed to reject, close or cancel).")


class PoLineOut(ApiModel):
    id: int
    line_no: int
    item_id: int
    item_code: str
    item_description: str
    description: str | None
    uom_code: str
    quantity: Decimal
    unit_price: Decimal
    discount_pct: Decimal
    gst_pct: Decimal
    net_price: Decimal = Field(description="Unit price after discount, before GST: the cost a GRN takes.")
    taxable_value: Decimal
    tax_amount: Decimal
    line_total: Decimal
    qty_received: Decimal
    qty_invoiced: Decimal
    qty_pending: Decimal


class PoDocument(ApiModel):
    id: int
    number: str
    date: dt.date
    amount: Decimal
    status: str


class PoDetail(PoListItem):
    company_name: str
    company_address: str | None
    branch_address: str | None
    supplier_code: str
    supplier_gstin: str | None
    supplier_address: str | None
    supplier_phone: str | None
    delivery_location_id: int
    location_address: str | None
    payment_terms_id: int | None
    payment_terms: str | None
    place_of_supply: str
    po_type: PurchaseOrderPoType
    subtotal: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    tax_total: Decimal
    other_charges: Decimal
    oem_po_ref: str | None
    remarks: str | None
    created_by: str | None
    submitted_by: str | None
    submitted_at: UtcDateTime | None
    approved_by: str | None
    approved_at: UtcDateTime | None
    approval_note: str | None
    closed_by: str | None
    closed_at: UtcDateTime | None
    close_reason: str | None
    lines: list[PoLineOut]
    grns: list[PoDocument]
    invoices: list[PoDocument]
    row_version: RowVersion


class OutstandingQuery(PageQuery):
    supplier_id: int | None = None
    branch_id: int | None = None
    item_id: int | None = None
    overdue_only: bool = Field(False, description="Past the expected date.")


class OutstandingLine(ApiModel):
    purchase_order_id: int
    po_no: str
    po_date: dt.date
    expected_date: dt.date | None
    status: PurchaseOrderStatus
    supplier_id: int
    supplier_name: str
    branch_name: str
    line_id: int
    item_id: int
    item_code: str
    item_description: str
    uom_code: str
    qty_ordered: Decimal
    qty_received: Decimal
    qty_pending: Decimal
    net_price: Decimal
    pending_value: Decimal
    days_open: int
