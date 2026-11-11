import datetime as dt
from decimal import Decimal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models import SalesOrderCreditCheckStatus, SalesOrderStatus
from trishul_api.modules.sal.lines import MONEY, ItemLineIn, PricedLineOut


class OrderQuery(PageQuery):
    status: SalesOrderStatus | None = None
    customer_id: int | None = None
    branch_id: int | None = None
    item_id: int | None = Field(None, description="Orders with a line for this item.")
    from_date: dt.date | None = None
    to_date: dt.date | None = None
    outstanding_only: bool = Field(False, description="Approved orders with quantity still to deliver.")
    prepaid_only: bool = False


class OrderCreate(InputModel):
    principal_id: int = Field(description="Brand: one brand per order.")
    branch_id: int = Field(description="The selling branch (its number series).")
    customer_id: int
    customer_site_id: int | None = Field(None, description="The customer's branch.")
    order_date: dt.date | None = Field(None, description="Default today.")
    customer_po_no: str | None = Field(None, max_length=40)
    customer_po_date: dt.date | None = None
    expected_delivery_date: dt.date | None = None
    payment_terms_id: int | None = Field(None, description="Default: the customer's terms.")
    bill_to_address: str | None = Field(None, max_length=500, description="Default: the branch's or customer's.")
    ship_to_address: str | None = Field(None, max_length=500, description="Default: the branch's address.")
    is_prepaid: bool = Field(False, description="The customer pays in advance (advances are adjusted on invoices).")
    other_charges: Decimal = MONEY
    remarks: str | None = Field(None, max_length=500)
    lines: list[ItemLineIn] = Field(min_length=1, max_length=200)


class OrderNote(InputModel):
    note: str | None = Field(None, max_length=300, description="Why (needed to reject, close or cancel).")


class OrderApprove(OrderNote):
    override_credit: bool = Field(False, description="Approve over the credit limit (needs sal.credit.override).")


class OrderListItem(ApiModel):
    id: int
    order_no: str
    order_date: dt.date
    expected_delivery_date: dt.date | None
    customer_id: int
    customer_name: str
    customer_site_name: str | None
    branch_id: int
    branch_name: str
    principal_name: str
    customer_po_no: str | None
    status: SalesOrderStatus
    is_prepaid: bool
    total: Decimal
    advance_received: Decimal
    qty_ordered: Decimal
    qty_delivered: Decimal
    qty_invoiced: Decimal
    created_at: UtcDateTime


class OrderLineOut(PricedLineOut):
    qty_delivered: Decimal
    qty_invoiced: Decimal
    qty_to_deliver: Decimal


class OrderDocument(ApiModel):
    id: int
    number: str
    date: dt.date
    amount: Decimal | None
    status: str


class OrderDetail(OrderListItem):
    principal_id: int
    customer_site_id: int | None
    quotation_id: int | None
    quotation_no: str | None
    company_name: str
    company_address: str | None
    branch_address: str | None
    customer_code: str
    customer_gstin: str | None
    customer_phone: str | None
    bill_to_address: str | None
    ship_to_address: str | None
    place_of_supply: str | None
    customer_po_date: dt.date | None
    payment_terms_id: int | None
    payment_terms: str | None
    subtotal: Decimal = Field(description="Taxable value (after discounts).")
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    tax_total: Decimal
    other_charges: Decimal
    remarks: str | None
    credit_check_status: SalesOrderCreditCheckStatus
    credit_approved_by: str | None
    created_by: str | None
    submitted_by: str | None
    submitted_at: UtcDateTime | None
    approved_by: str | None
    approved_at: UtcDateTime | None
    approval_note: str | None
    closed_by: str | None
    closed_at: UtcDateTime | None
    close_reason: str | None
    invoiced_amount: Decimal
    advance_adjusted: Decimal = Field(description="Advances set against this order's invoices.")
    advance_remaining: Decimal
    customer_balance: Decimal
    credit_limit: Decimal | None
    lines: list[OrderLineOut]
    deliveries: list[OrderDocument]
    invoices: list[OrderDocument]
    advances: list[OrderDocument]
    row_version: RowVersion


class OutstandingOrderQuery(PageQuery):
    customer_id: int | None = None
    branch_id: int | None = None
    item_id: int | None = None
    sales_order_id: int | None = None
    overdue_only: bool = Field(False, description="Past the expected delivery date.")


class OutstandingOrderLine(ApiModel):
    sales_order_id: int
    order_no: str
    order_date: dt.date
    expected_delivery_date: dt.date | None
    status: SalesOrderStatus
    customer_id: int
    customer_name: str
    branch_name: str
    line_id: int
    item_id: int
    item_code: str
    description: str
    uom_code: str | None
    qty_ordered: Decimal
    qty_delivered: Decimal
    qty_to_deliver: Decimal
    net_price: Decimal
    pending_value: Decimal
    days_open: int
