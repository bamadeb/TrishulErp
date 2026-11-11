import datetime as dt
from decimal import Decimal

from pydantic import Field, model_validator

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, UtcDateTime
from trishul_api.db.models import DeliveryNoteStatus
from trishul_api.modules.sal.lines import GST, PCT, QTY


class DeliveryQuery(PageQuery):
    status: DeliveryNoteStatus | None = None
    customer_id: int | None = None
    sales_order_id: int | None = None
    branch_id: int | None = None
    location_id: int | None = None
    from_date: dt.date | None = None
    to_date: dt.date | None = None
    direct_only: bool = Field(False, description="Deliveries without a sales order.")
    uninvoiced_only: bool = Field(False, description="With quantity not invoiced yet.")


class DeliveryLineIn(InputModel):
    """Against an order: salesOrderLineId (the item and price come from it). Direct: itemId and,
    optionally, the price to invoice at."""

    sales_order_line_id: int | None = None
    item_id: int | None = None
    quantity: Decimal = QTY
    bin_id: int | None = Field(None, description="Rack to take from; default any rack of the location.")
    stock_lot_id: int | None = Field(None, description="Batch to take; default oldest GRN date first.")
    description: str | None = Field(None, max_length=300)
    unit_price: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=4, description="Direct only.")
    discount_pct: Decimal = PCT
    gst_pct: Decimal = GST

    @model_validator(mode="after")
    def _what(self) -> "DeliveryLineIn":
        if self.sales_order_line_id is None and self.item_id is None:
            raise ValueError("a line needs an order line or an item")
        return self


class DeliveryCreate(InputModel):
    sales_order_id: int | None = Field(None, description="Empty for a direct delivery.")
    principal_id: int | None = Field(None, description="Direct only (else the order's).")
    branch_id: int | None = Field(None, description="Direct only (else the order's).")
    customer_id: int | None = Field(None, description="Direct only (else the order's).")
    customer_site_id: int | None = Field(None, description="Default: the order's customer branch.")
    location_id: int = Field(description="Stock location the goods are dispatched from.")
    delivery_date: dt.date | None = Field(None, description="Default today.")
    ship_to_address: str | None = Field(None, max_length=500)
    delivery_reference: str | None = Field(None, max_length=40)
    vehicle_no: str | None = Field(None, max_length=20)
    transporter: str | None = Field(None, max_length=100)
    lr_no: str | None = Field(None, max_length=40)
    received_by_name: str | None = Field(None, max_length=100, description="Recipient.")
    recipient_phone: str | None = Field(None, max_length=15)
    remarks: str | None = Field(None, max_length=500)
    over_deliver: bool = Field(False, description="Deliver more than is outstanding (needs sal.delivery.over_order).")
    lines: list[DeliveryLineIn] = Field(min_length=1, max_length=200)


class DeliveryConfirm(InputModel):
    received_by_name: str = Field(min_length=1, max_length=100)
    delivered_at: dt.datetime | None = Field(None, description="Default now.")


class DeliveryCancel(InputModel):
    reason: str = Field(min_length=3, max_length=300)


class DeliveryListItem(ApiModel):
    id: int
    delivery_no: str
    delivery_date: dt.date
    customer_id: int
    customer_name: str
    customer_site_name: str | None
    sales_order_id: int | None
    order_no: str | None
    branch_name: str
    location_name: str
    principal_name: str
    status: DeliveryNoteStatus
    total_qty: Decimal
    qty_invoiced: Decimal
    created_at: UtcDateTime


class DeliveryBatch(ApiModel):
    lot_no: str
    grn_no: str
    grn_date: dt.date
    bin_code: str | None
    quantity: Decimal


class DeliveryLineOut(ApiModel):
    id: int
    sales_order_line_id: int | None
    item_id: int
    item_code: str
    description: str
    uom_code: str | None
    quantity: Decimal
    qty_invoiced: Decimal
    qty_to_invoice: Decimal
    unit_price: Decimal | None
    discount_pct: Decimal
    gst_pct: Decimal
    unit_cost: Decimal | None
    batches: list[DeliveryBatch]


class DeliveryInvoice(ApiModel):
    id: int
    invoice_no: str
    invoice_date: dt.date
    total: Decimal
    status: str


class DeliveryDetail(DeliveryListItem):
    principal_id: int
    branch_id: int
    location_id: int
    customer_site_id: int | None
    company_name: str
    company_address: str | None
    branch_address: str | None
    location_address: str | None
    customer_code: str
    customer_gstin: str | None
    customer_phone: str | None
    ship_to_address: str | None
    delivery_reference: str | None
    vehicle_no: str | None
    transporter: str | None
    lr_no: str | None
    received_by_name: str | None
    recipient_phone: str | None
    remarks: str | None
    dispatched_at: UtcDateTime | None
    delivered_at: UtcDateTime | None
    posted_by: str | None
    cancelled_by: str | None
    cancelled_at: UtcDateTime | None
    cancel_reason: str | None
    lines: list[DeliveryLineOut]
    invoices: list[DeliveryInvoice]


class UninvoicedDeliveryQuery(ApiModel):
    customer_id: int
    delivery_note_id: int | None = None
    sales_order_id: int | None = None


class UninvoicedDeliveryLine(ApiModel):
    delivery_note_line_id: int
    delivery_note_id: int
    delivery_no: str
    delivery_date: dt.date
    sales_order_id: int | None
    order_no: str | None
    sales_order_line_id: int | None
    principal_id: int
    branch_id: int
    item_id: int
    item_code: str
    description: str
    uom_code: str | None
    qty_delivered: Decimal
    qty_invoiced: Decimal
    qty_to_invoice: Decimal
    unit_price: Decimal | None = Field(description="From the order line, or set on a direct delivery.")
    discount_pct: Decimal
    gst_pct: Decimal
