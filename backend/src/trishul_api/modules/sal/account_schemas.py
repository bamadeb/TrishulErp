"""Sales invoices, customer receipts (incl. order advances) and the allocations that settle invoices."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, UtcDateTime
from trishul_api.db.models import ReceiptPaymentMode, ReceiptReceiptType, SalesInvoiceInvoiceType
from trishul_api.modules.sal.lines import GST, MONEY, PCT, PRICE, QTY

SalesInvoiceState = Literal["Unpaid", "Partially paid", "Paid", "Overdue", "Cancelled"]


class SalesAccountQuery(PageQuery):
    customer_id: int | None = None
    branch_id: int | None = None
    from_date: dt.date | None = None
    to_date: dt.date | None = None


class SalesInvoiceQuery(SalesAccountQuery):
    state: SalesInvoiceState | None = Field(None, description="Unpaid includes overdue ones.")
    sales_order_id: int | None = None
    delivery_note_id: int | None = None
    direct_only: bool = False


# ---------------------------------------------------------------- invoices


class SalesInvoiceLineIn(InputModel):
    """Bill a delivery line (deliveryNoteLineId), or a direct line: an item (stock items are taken from the
    invoice's location) or just a description (a service, freight). Direct lines need sal.invoice.direct."""

    delivery_note_line_id: int | None = None
    item_id: int | None = None
    description: str | None = Field(None, max_length=300)
    quantity: Decimal = QTY
    unit_price: Decimal = PRICE
    discount_pct: Decimal = PCT
    gst_pct: Decimal = GST
    bin_id: int | None = Field(None, description="Direct stock line: rack to take from.")
    stock_lot_id: int | None = Field(None, description="Direct stock line: batch to take.")

    @model_validator(mode="after")
    def _something(self) -> "SalesInvoiceLineIn":
        if not (self.delivery_note_line_id or self.item_id or self.description):
            raise ValueError("a line needs a delivery line, an item or a description")
        return self


class SalesInvoiceCreate(InputModel):
    customer_id: int
    principal_id: int | None = Field(None, description="Default: the brand of the deliveries billed.")
    branch_id: int | None = Field(None, description="Default: the branch of the deliveries billed.")
    customer_site_id: int | None = Field(None, description="Default: the delivery's customer branch.")
    invoice_type: SalesInvoiceInvoiceType = "Tax invoice"
    invoice_date: dt.date | None = Field(None, description="Default today.")
    due_date: dt.date | None = Field(None, description="Default: invoice date + the customer's payment terms.")
    location_id: int | None = Field(None, description="Direct stock lines: where the goods leave from.")
    bill_to_address: str | None = Field(None, max_length=500)
    ship_to_address: str | None = Field(None, max_length=500)
    other_charges: Decimal = MONEY
    remarks: str | None = Field(None, max_length=500)
    adjust_advances: bool = Field(True, description="Set the orders' advances against this invoice.")
    override_credit: bool = Field(False, description="Post over the credit limit (needs sal.credit.override).")
    lines: list[SalesInvoiceLineIn] = Field(min_length=1, max_length=200)


class SalesInvoiceCancel(InputModel):
    reason: str = Field(min_length=3, max_length=300)


class SalesInvoiceListItem(ApiModel):
    id: int
    invoice_no: str
    invoice_date: dt.date
    due_date: dt.date | None
    customer_id: int
    customer_name: str
    branch_name: str
    principal_name: str
    order_no: str | None
    delivery_no: str | None
    source_type: str
    is_direct: bool
    total: Decimal
    allocated: Decimal
    outstanding: Decimal
    state: SalesInvoiceState
    overdue_days: int
    status: str
    created_at: UtcDateTime


class SalesInvoiceLineOut(ApiModel):
    id: int
    line_no: int
    delivery_note_line_id: int | None
    delivery_no: str | None
    sales_order_line_id: int | None
    order_no: str | None
    item_id: int | None
    item_code: str | None
    description: str
    hsn_code: str | None
    uom_code: str | None
    quantity: Decimal
    unit_price: Decimal
    discount_pct: Decimal
    gst_pct: Decimal
    taxable_value: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    line_total: Decimal


class CustomerAllocationOut(ApiModel):
    id: int
    customer_id: int
    customer_name: str
    sales_invoice_id: int
    invoice_no: str
    invoice_total: Decimal
    invoice_outstanding: Decimal
    receipt_id: int | None
    receipt_no: str | None
    receipt_type: str | None
    receipt_reference: str | None
    amount: Decimal
    allocated_on: dt.date
    allocated_by: str | None
    is_active: bool
    reversed_at: UtcDateTime | None
    reversed_by: str | None
    reversal_reason: str | None


class SalesInvoiceDetail(SalesInvoiceListItem):
    principal_id: int
    branch_id: int
    customer_site_id: int | None
    sales_order_id: int | None
    delivery_note_id: int | None
    invoice_type: SalesInvoiceInvoiceType
    company_name: str
    company_address: str | None
    branch_address: str | None
    our_gstin: str | None
    customer_code: str
    customer_gstin: str | None
    customer_phone: str | None
    bill_to_address: str | None
    ship_to_address: str | None
    place_of_supply: str
    location_name: str | None
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    other_charges: Decimal
    round_off: Decimal
    remarks: str | None
    advance_adjusted: Decimal
    amount_in_words: str
    posted_by: str | None
    credit_override_by: str | None
    cancelled_by: str | None
    cancelled_at: UtcDateTime | None
    cancel_reason: str | None
    lines: list[SalesInvoiceLineOut]
    allocations: list[CustomerAllocationOut]


# ---------------------------------------------------------------- receipts


class CustomerAllocationIn(InputModel):
    sales_invoice_id: int
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class ReceiptCreate(InputModel):
    customer_id: int
    branch_id: int
    receipt_date: dt.date
    receipt_type: ReceiptReceiptType = Field(
        description="Against invoice, Advance (on account) or Order advance (for a sales order)."
    )
    sales_order_id: int | None = Field(None, description="Order advance: the order it is for.")
    payment_mode: ReceiptPaymentMode
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    reference_no: str | None = Field(None, max_length=40, description="UTR, cheque or UPI reference.")
    bank_name: str | None = Field(None, max_length=100)
    cheque_date: dt.date | None = None
    remarks: str | None = Field(None, max_length=300)
    allocations: list[CustomerAllocationIn] = Field(
        default_factory=list, max_length=200, description="Invoices this settles now; the rest stays unallocated."
    )


class ReceiptQuery(SalesAccountQuery):
    receipt_type: ReceiptReceiptType | None = None
    sales_order_id: int | None = None
    unallocated_only: bool = False


class ReceiptListItem(ApiModel):
    id: int
    receipt_no: str
    receipt_date: dt.date
    receipt_type: ReceiptReceiptType
    customer_id: int
    customer_name: str
    branch_name: str
    sales_order_id: int | None
    order_no: str | None
    payment_mode: ReceiptPaymentMode
    reference_no: str | None
    amount: Decimal
    allocated: Decimal
    unallocated: Decimal
    status: str
    created_at: UtcDateTime


class ReceiptDetail(ReceiptListItem):
    company_name: str
    branch_address: str | None
    customer_code: str
    customer_address: str | None
    customer_gstin: str | None
    bank_name: str | None
    cheque_date: dt.date | None
    remarks: str | None
    posted_by: str | None
    amount_in_words: str
    allocations: list[CustomerAllocationOut]


# ---------------------------------------------------------------- allocations


class CustomerAllocationQuery(PageQuery):
    customer_id: int | None = None
    sales_invoice_id: int | None = None
    receipt_id: int | None = None
    include_reversed: bool = True


class CustomerAllocationCreate(InputModel):
    """Set a receipt against one or more invoices of the same customer."""

    receipt_id: int
    allocations: list[CustomerAllocationIn] = Field(min_length=1, max_length=200)


class CustomerAllocationReverse(InputModel):
    reason: str = Field(min_length=3, max_length=300)
