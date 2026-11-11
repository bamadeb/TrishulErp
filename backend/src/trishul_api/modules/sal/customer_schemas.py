"""Customer accounts for sales: balances, credit terms, customer branches, statement and open items."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion

_GSTIN = r"^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]$"
_PHONE = r"^[0-9+\-() ]{6,15}$"


class CustomerAccountQuery(PageQuery):
    status: Literal["active", "inactive", "all"] = "active"
    with_balance: bool = Field(False, description="Only customers with an outstanding balance.")
    over_limit: bool = Field(False, description="Only customers above their credit limit.")


class CustomerAccount(ApiModel):
    id: int
    code: str
    name: str
    customer_type: str
    gstin: str | None
    primary_phone: str
    billing_state_name: str | None
    payment_terms_id: int | None
    payment_terms: str | None
    credit_limit: Decimal | None = Field(description="Empty: no limit.")
    balance: Decimal = Field(description="What the customer owes (negative: advance received).")
    branch_count: int
    is_active: bool


class CustomerAccountDetail(CustomerAccount):
    billing_address: str | None
    email: str | None
    pan: str | None
    opening_balance: Decimal
    opening_balance_date: dt.date | None
    invoiced: Decimal
    received: Decimal
    unallocated: Decimal = Field(description="Receipts not yet set against an invoice (advances).")
    overdue: Decimal = Field(description="Outstanding on invoices past their due date.")
    available_credit: Decimal | None
    open_orders: int
    row_version: RowVersion


class CreditTermsUpdate(InputModel):
    """Only the fields sent are changed. A change of limit or terms is logged with the reason."""

    payment_terms_id: int | None = None
    credit_limit: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2, description="Empty: no limit.")
    opening_balance: Decimal | None = Field(
        None, max_digits=18, decimal_places=2, description="Owed at go-live (+) or advance held (-)."
    )
    opening_balance_date: dt.date | None = None
    reason: str = Field(min_length=3, max_length=300)


class CustomerBranchOut(ApiModel):
    id: int
    customer_id: int
    site_code: str | None
    site_name: str
    address: str = Field(description="Delivery address.")
    billing_address: str | None
    state_id: int | None
    state_name: str | None
    billing_state_id: int | None
    gstin: str | None
    site_contact_name: str | None
    site_contact_phone: str | None
    email: str | None
    is_default: bool
    is_active: bool
    row_version: RowVersion


class _BranchFields(InputModel):
    site_code: str | None = Field(None, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9_./-]*$")
    billing_address: str | None = Field(None, max_length=500)
    state_id: int | None = Field(None, description="State of the delivery address (place of supply).")
    billing_state_id: int | None = None
    gstin: str | None = Field(None, pattern=_GSTIN)
    site_contact_name: str | None = Field(None, max_length=100)
    site_contact_phone: str | None = Field(None, pattern=_PHONE)
    email: str | None = Field(None, max_length=120)
    is_default: bool | None = None


class CustomerBranchCreate(_BranchFields):
    site_name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=500, description="Delivery address.")


class CustomerBranchUpdate(_BranchFields):
    """Only the fields sent are changed."""

    site_name: str | None = Field(None, min_length=1, max_length=120)
    address: str | None = Field(None, min_length=1, max_length=500)
    is_active: bool | None = None


class SalesOption(ApiModel):
    id: int
    code: str
    name: str


class DispatchLocationOption(ApiModel):
    id: int
    code: str
    name: str
    branch_id: int
    branch_name: str


class SalesFormOptions(ApiModel):
    brands: list[SalesOption]
    branches: list[SalesOption]
    locations: list[DispatchLocationOption] = Field(description="Stock locations goods may be dispatched from.")
    payment_terms: list[SalesOption]
    states: list[SalesOption]
    default_branch_id: int | None
    default_brand_id: int | None


class CustomerStatementQuery(ApiModel):
    from_date: dt.date | None = None
    to_date: dt.date | None = None


CustomerStatementEntryType = Literal["Sales order", "Delivery", "Invoice", "Receipt"]


class CustomerStatementEntry(ApiModel):
    date: dt.date
    entry_type: CustomerStatementEntryType
    document_id: int
    document_no: str
    reference: str | None
    description: str
    debit: Decimal = Field(description="Adds to what the customer owes (invoices).")
    credit: Decimal = Field(description="Reduces it (receipts).")
    balance: Decimal | None = Field(description="Running balance; empty for orders and deliveries.")
    memo_amount: Decimal | None = Field(description="Value of an order, for information.")


class CustomerStatement(ApiModel):
    customer_id: int
    customer_name: str
    from_date: dt.date | None
    to_date: dt.date
    opening_balance: Decimal
    closing_balance: Decimal
    total_debit: Decimal
    total_credit: Decimal
    entries: list[CustomerStatementEntry]


class OpenSalesInvoice(ApiModel):
    id: int
    invoice_no: str
    invoice_date: dt.date
    due_date: dt.date | None
    sales_order_id: int | None
    total: Decimal
    allocated: Decimal
    outstanding: Decimal
    overdue_days: int


class OpenReceipt(ApiModel):
    id: int
    receipt_no: str
    receipt_date: dt.date
    receipt_type: str
    sales_order_id: int | None
    order_no: str | None
    reference_no: str | None
    amount: Decimal
    allocated: Decimal
    unallocated: Decimal


class CustomerOpenItems(ApiModel):
    customer_id: int
    invoices: list[OpenSalesInvoice]
    receipts: list[OpenReceipt]


class SaleStockAt(ApiModel):
    location_id: int
    location_name: str
    branch_name: str
    qty_on_hand: Decimal


class ItemSaleInfo(ApiModel):
    item_id: int
    item_code: str
    description: str
    item_type: str
    principal_id: int | None
    uom_id: int
    uom_code: str
    hsn_code: str | None
    mrp: Decimal | None
    price: Decimal | None = Field(description="From the active price list for the brand (or a common one).")
    price_list: str | None
    stock: list[SaleStockAt]
