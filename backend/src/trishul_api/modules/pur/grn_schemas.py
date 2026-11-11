"""Goods receipt (GRN): direct, or against an approved purchase order (partial and repeated receipts)."""

import datetime as dt
from decimal import Decimal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, UtcDateTime


class GrnQuery(PageQuery):
    branch_id: int | None = None
    location_id: int | None = None
    supplier_id: int | None = None
    purchase_order_id: int | None = None
    from_date: dt.date | None = None
    to_date: dt.date | None = None


class GrnLineIn(InputModel):
    item_id: int
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3, description="Accepted, in the unit received.")
    rejected_qty: Decimal = Field(Decimal(0), ge=0, max_digits=18, decimal_places=3)
    uom_id: int | None = Field(None, description="Unit received in; converted to the stock unit. Default: stock unit.")
    unit_cost: Decimal = Field(ge=0, max_digits=18, decimal_places=4, description="Per unit received.")
    bin_id: int | None = Field(None, description="Rack the stock is put away in.")
    rejection_reason: str | None = Field(None, max_length=200)
    purchase_order_line_id: int | None = Field(None, description="The order line this receives against.")


class GrnCreate(InputModel):
    location_id: int = Field(description="Where the goods are received (branch / warehouse location).")
    supplier_id: int
    purchase_order_id: int | None = Field(None, description="Leave out for a direct GRN.")
    grn_date: dt.date = Field(description="Inventory age starts from this date.")
    supplier_invoice_no: str | None = Field(None, max_length=40)
    supplier_invoice_date: dt.date | None = None
    vehicle_no: str | None = Field(None, max_length=20)
    lr_no: str | None = Field(None, max_length=40)
    remarks: str | None = Field(None, max_length=300)
    lines: list[GrnLineIn] = Field(min_length=1, max_length=200)


class GrnListItem(ApiModel):
    id: int
    grn_no: str
    grn_date: dt.date
    branch_id: int
    branch_name: str
    location_id: int
    location_name: str
    supplier_id: int
    supplier_name: str
    purchase_order_id: int | None
    po_no: str | None
    supplier_invoice_no: str | None
    line_count: int
    total_qty: Decimal
    total_value: Decimal
    status: str
    created_at: UtcDateTime


class GrnLineOut(ApiModel):
    id: int
    item_id: int
    item_code: str
    item_description: str
    uom_code: str
    entry_qty: Decimal | None
    entry_uom_code: str | None
    qty_received: Decimal
    qty_accepted: Decimal
    qty_rejected: Decimal
    qty_invoiced: Decimal
    unit_cost: Decimal = Field(description="Per stock unit.")
    value: Decimal
    bin_code: str | None
    rejection_reason: str | None
    purchase_order_line_id: int | None
    stock_lot_id: int | None
    lot_no: str | None
    qty_remaining: Decimal = Field(description="Of this GRN batch still in stock, wherever it is now.")


class GrnDetail(GrnListItem):
    supplier_invoice_date: dt.date | None
    vehicle_no: str | None
    lr_no: str | None
    remarks: str | None
    created_by: str | None
    lines: list[GrnLineOut]


class UninvoicedQuery(ApiModel):
    supplier_id: int
    grn_id: int | None = None


class UninvoicedLine(ApiModel):
    """A GRN line not (fully) invoiced yet: what a supplier invoice can bill."""

    grn_id: int
    grn_no: str
    grn_date: dt.date
    grn_line_id: int
    purchase_order_id: int | None
    po_no: str | None
    purchase_order_line_id: int | None
    item_id: int
    item_code: str
    item_description: str
    uom_code: str
    qty_accepted: Decimal
    qty_invoiced: Decimal
    qty_to_invoice: Decimal
    unit_cost: Decimal
    discount_pct: Decimal = Field(description="From the order line, if any.")
    unit_price: Decimal = Field(description="Price before discount: the order's, else the GRN cost.")
    gst_pct: Decimal = Field(description="From the order line; 18 for a direct GRN.")
