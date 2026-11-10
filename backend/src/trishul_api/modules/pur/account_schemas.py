"""Supplier invoices, payments, credit notes and the allocations that settle invoices."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, UtcDateTime
from trishul_api.db.models import DebitNoteNoteType, SupplierPaymentPaymentMode

_MONEY = Field(ge=0, max_digits=18, decimal_places=2)
_PCT = Field(Decimal(0), ge=0, le=100, max_digits=5, decimal_places=2)
InvoiceState = Literal["Unpaid", "Partially paid", "Paid", "Overdue", "Cancelled"]


class AccountQuery(PageQuery):
    supplier_id: int | None = None
    branch_id: int | None = None
    from_date: dt.date | None = None
    to_date: dt.date | None = None


class InvoiceQuery(AccountQuery):
    state: InvoiceState | None = Field(None, description="Unpaid includes overdue ones.")
    purchase_order_id: int | None = None
    grn_id: int | None = None


# ---------------------------------------------------------------- supplier invoices


class InvoiceLineIn(InputModel):
    """Bill a GRN line (grnLineId), an order line not received yet (purchaseOrderLineId, needs
    pur.invoice.direct), or a direct line with an item or just a description (pur.invoice.direct)."""

    grn_line_id: int | None = None
    purchase_order_line_id: int | None = None
    item_id: int | None = None
    description: str | None = Field(None, max_length=200)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    discount_pct: Decimal = _PCT
    gst_pct: Decimal = Field(Decimal(18), ge=0, le=100, max_digits=5, decimal_places=2)

    @model_validator(mode="after")
    def _something_billed(self) -> "InvoiceLineIn":
        if not (self.grn_line_id or self.purchase_order_line_id or self.item_id or self.description):
            raise ValueError("a line needs a GRN line, an order line, an item or a description")
        return self


class InvoiceCreate(InputModel):
    supplier_id: int
    branch_id: int | None = Field(None, description="Default: the branch of the GRN or order billed.")
    supplier_invoice_no: str = Field(min_length=1, max_length=40, description="The supplier's own number.")
    supplier_invoice_date: dt.date
    due_date: dt.date | None = Field(None, description="Default: invoice date + the supplier's payment terms.")
    other_charges: Decimal = Field(Decimal(0), ge=0, max_digits=18, decimal_places=2)
    remarks: str | None = Field(None, max_length=300)
    lines: list[InvoiceLineIn] = Field(min_length=1, max_length=200)


class InvoiceListItem(ApiModel):
    id: int
    invoice_no: str
    supplier_invoice_no: str
    supplier_invoice_date: dt.date
    due_date: dt.date | None
    supplier_id: int
    supplier_name: str
    branch_name: str
    po_no: str | None
    grn_no: str | None
    is_direct: bool
    total: Decimal
    allocated: Decimal
    outstanding: Decimal
    state: InvoiceState
    overdue_days: int
    created_at: UtcDateTime


class InvoiceLineOut(ApiModel):
    id: int
    grn_line_id: int | None
    grn_no: str | None
    purchase_order_line_id: int | None
    item_id: int | None
    item_code: str | None
    description: str | None
    quantity: Decimal
    unit_price: Decimal
    discount_pct: Decimal
    gst_pct: Decimal
    taxable_value: Decimal
    tax_amount: Decimal
    line_total: Decimal


class AllocationOut(ApiModel):
    id: int
    supplier_id: int
    supplier_name: str
    supplier_invoice_id: int
    invoice_no: str
    supplier_invoice_no: str
    invoice_total: Decimal
    invoice_outstanding: Decimal
    supplier_payment_id: int | None
    payment_no: str | None
    payment_reference: str | None
    debit_note_id: int | None
    credit_note_no: str | None
    amount: Decimal
    allocated_on: dt.date
    allocated_by: str | None
    is_active: bool
    reversed_at: UtcDateTime | None
    reversed_by: str | None
    reversal_reason: str | None


class InvoiceDetail(InvoiceListItem):
    branch_id: int
    purchase_order_id: int | None
    grn_id: int | None
    place_of_supply: str
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    other_charges: Decimal
    round_off: Decimal
    remarks: str | None
    posted_by: str | None
    lines: list[InvoiceLineOut]
    allocations: list[AllocationOut]


# ---------------------------------------------------------------- payments


class AllocationIn(InputModel):
    supplier_invoice_id: int
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class PaymentCreate(InputModel):
    supplier_id: int
    branch_id: int
    payment_date: dt.date
    payment_mode: SupplierPaymentPaymentMode = Field(description="NEFT / RTGS = bank transfer.")
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    reference_no: str | None = Field(None, max_length=40, description="UTR, cheque or UPI reference.")
    bank_name: str | None = Field(None, max_length=100)
    cheque_date: dt.date | None = None
    remarks: str | None = Field(None, max_length=300)
    allocations: list[AllocationIn] = Field(
        default_factory=list, max_length=200, description="Invoices this pays now; the rest stays as advance."
    )


class PaymentListItem(ApiModel):
    id: int
    payment_no: str
    payment_date: dt.date
    supplier_id: int
    supplier_name: str
    branch_name: str
    payment_mode: SupplierPaymentPaymentMode
    reference_no: str | None
    amount: Decimal
    allocated: Decimal
    unallocated: Decimal
    status: str
    created_at: UtcDateTime


class PaymentDetail(PaymentListItem):
    company_name: str
    supplier_code: str
    supplier_address: str | None
    supplier_gstin: str | None
    bank_name: str | None
    cheque_date: dt.date | None
    remarks: str | None
    posted_by: str | None
    amount_in_words: str
    allocations: list[AllocationOut]


# ---------------------------------------------------------------- credit notes


class CreditNoteLineIn(InputModel):
    item_id: int | None = None
    description: str | None = Field(None, max_length=200)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    gst_pct: Decimal = Field(Decimal(18), ge=0, le=100, max_digits=5, decimal_places=2)
    grn_line_id: int | None = Field(None, description="Returns: the GRN line (its batch) the goods go back from.")
    stock_lot_id: int | None = Field(None, description="Returns: the batch to take; default the GRN line's.")
    bin_id: int | None = Field(None, description="Returns: the rack to take from; default any.")

    @model_validator(mode="after")
    def _item_or_text(self) -> "CreditNoteLineIn":
        if not (self.item_id or self.description):
            raise ValueError("a line needs an item or a description")
        return self


class CreditNoteCreate(InputModel):
    supplier_id: int
    branch_id: int
    note_type: DebitNoteNoteType
    note_date: dt.date
    supplier_note_no: str | None = Field(None, max_length=40, description="The supplier's credit note number.")
    supplier_note_date: dt.date | None = None
    supplier_invoice_id: int | None = Field(None, description="The invoice it corrects; it is set against it.")
    grn_id: int | None = None
    location_id: int | None = Field(None, description="Purchase return: where the goods leave from.")
    reason_id: int | None = Field(None, description="From the RETURN_REASON list.")
    remarks: str | None = Field(None, max_length=300)
    lines: list[CreditNoteLineIn] = Field(min_length=1, max_length=200)


class CreditNoteListItem(ApiModel):
    id: int
    debit_note_no: str
    note_date: dt.date
    note_type: DebitNoteNoteType
    supplier_id: int
    supplier_name: str
    supplier_note_no: str | None
    invoice_no: str | None
    total: Decimal
    allocated: Decimal
    unallocated: Decimal
    status: str
    created_at: UtcDateTime


class CreditNoteLineOut(ApiModel):
    id: int
    item_id: int | None
    item_code: str | None
    description: str | None
    quantity: Decimal
    unit_price: Decimal
    gst_pct: Decimal
    taxable_value: Decimal
    tax_amount: Decimal
    line_total: Decimal
    lot_no: str | None
    grn_no: str | None
    bin_code: str | None


class CreditNoteDetail(CreditNoteListItem):
    branch_name: str | None
    location_name: str | None
    supplier_note_date: dt.date | None
    supplier_invoice_id: int | None
    grn_id: int | None
    reason: str | None
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    remarks: str | None
    posted_by: str | None
    lines: list[CreditNoteLineOut]
    allocations: list[AllocationOut]


# ---------------------------------------------------------------- allocations


class AllocationQuery(PageQuery):
    supplier_id: int | None = None
    supplier_invoice_id: int | None = None
    supplier_payment_id: int | None = None
    debit_note_id: int | None = None
    include_reversed: bool = True


class AllocationCreate(InputModel):
    """Set a payment or a credit note (one of them) against one or more invoices of the same supplier."""

    supplier_payment_id: int | None = None
    debit_note_id: int | None = None
    allocations: list[AllocationIn] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _one_source(self) -> "AllocationCreate":
        if (self.supplier_payment_id is None) == (self.debit_note_id is None):
            raise ValueError("give either supplierPaymentId or debitNoteId")
        return self


class AllocationReverse(InputModel):
    reason: str = Field(min_length=3, max_length=300)
