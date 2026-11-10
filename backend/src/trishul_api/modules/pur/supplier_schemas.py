import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion
from trishul_api.db.models import SupplierGstRegistrationType, SupplierSupplierType

_GSTIN = r"^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]$"
_PAN = r"^[A-Z]{5}\d{4}[A-Z]$"
_IFSC = r"^[A-Z]{4}0[A-Z0-9]{6}$"


class SupplierQuery(PageQuery):
    status: Literal["active", "inactive", "all"] = "active"
    with_balance: bool = Field(False, description="Only suppliers with an outstanding balance.")


class SupplierOut(ApiModel):
    id: int
    code: str
    name: str
    supplier_type: SupplierSupplierType
    gstin: str | None
    pan: str | None
    phone: str | None
    email: str | None
    address: str | None
    contact_person: str | None
    state_id: int | None
    state_name: str | None
    payment_terms_id: int | None
    payment_terms: str | None
    balance: Decimal = Field(description="What we owe the supplier (negative: advance paid).")
    is_active: bool
    row_version: RowVersion


class SupplierDetail(SupplierOut):
    gst_registration_type: SupplierGstRegistrationType | None
    credit_limit: Decimal | None
    bank_name: str | None
    bank_account_no: str | None = Field(description="Masked except the last 4 digits.")
    ifsc: str | None
    opening_balance: Decimal
    opening_balance_date: dt.date | None
    invoiced: Decimal
    paid: Decimal
    credited: Decimal
    unallocated: Decimal = Field(description="Payments and credit notes not yet set against an invoice.")
    overdue: Decimal = Field(description="Outstanding on invoices past their due date.")


class _SupplierFields(InputModel):
    supplier_type: SupplierSupplierType | None = None
    gstin: str | None = Field(None, pattern=_GSTIN)
    gst_registration_type: SupplierGstRegistrationType | None = None
    pan: str | None = Field(None, pattern=_PAN)
    phone: str | None = Field(None, max_length=15)
    email: str | None = Field(None, max_length=120)
    address: str | None = Field(None, max_length=500)
    contact_person: str | None = Field(None, max_length=100)
    state_id: int | None = None
    payment_terms_id: int | None = None
    credit_limit: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    bank_name: str | None = Field(None, max_length=100)
    bank_account_no: str | None = Field(None, max_length=30, pattern=r"^\d{6,30}$")
    ifsc: str | None = Field(None, pattern=_IFSC)
    opening_balance: Decimal | None = Field(
        None, max_digits=18, decimal_places=2, description="Owed at go-live (+) or advance paid (-)."
    )
    opening_balance_date: dt.date | None = None


class SupplierCreate(_SupplierFields):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9_./-]*$")
    name: str = Field(min_length=1, max_length=200)


class SupplierUpdate(_SupplierFields):
    """Only the fields sent are changed."""

    name: str | None = Field(None, min_length=1, max_length=200)
    is_active: bool | None = None


class Option(ApiModel):
    id: int
    code: str
    name: str


class SupplierFormOptions(ApiModel):
    states: list[Option]
    payment_terms: list[Option]


class StatementQuery(ApiModel):
    from_date: dt.date | None = None
    to_date: dt.date | None = None


StatementEntryType = Literal["Purchase order", "GRN", "Invoice", "Payment", "Credit note"]


class StatementEntry(ApiModel):
    date: dt.date
    entry_type: StatementEntryType
    document_id: int
    document_no: str
    reference: str | None
    description: str
    debit: Decimal = Field(description="Reduces what we owe (payments, credit notes).")
    credit: Decimal = Field(description="Adds to what we owe (invoices).")
    balance: Decimal | None = Field(description="Running balance; empty for orders and GRNs (no money yet).")
    memo_amount: Decimal | None = Field(description="Value of an order or GRN, for information.")


class SupplierStatement(ApiModel):
    supplier_id: int
    supplier_name: str
    from_date: dt.date | None
    to_date: dt.date
    opening_balance: Decimal
    closing_balance: Decimal
    total_debit: Decimal
    total_credit: Decimal
    entries: list[StatementEntry]


class OpenInvoice(ApiModel):
    id: int
    invoice_no: str
    supplier_invoice_no: str
    supplier_invoice_date: dt.date
    due_date: dt.date | None
    total: Decimal
    allocated: Decimal
    outstanding: Decimal
    overdue_days: int


class OpenCredit(ApiModel):
    """A payment or credit note with an amount not yet set against invoices."""

    kind: Literal["Payment", "Credit note"]
    id: int
    document_no: str
    date: dt.date
    reference: str | None
    amount: Decimal
    allocated: Decimal
    unallocated: Decimal


class SupplierOpenItems(ApiModel):
    supplier_id: int
    invoices: list[OpenInvoice]
    credits: list[OpenCredit]
