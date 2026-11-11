"""Shared pieces of the sales module: permissions, customer / branch / brand checks, GST place of supply,
the customer balance and the credit check.

Amounts follow the purchases module: taxable = qty x price less discount %, GST % on it, split CGST + SGST
when the place of supply is the branch's state and IGST otherwise. The place of supply is the state of the
customer branch delivered to, else the customer's billing state, else the branch's own state.

Customer balance = opening balance + posted invoices - posted receipts (advances included). A credit limit
left empty means no limit. Over the limit, approving an order or posting an invoice needs
sal.credit.override and an explicit override, which is recorded on the document.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError, Conflict, Forbidden
from trishul_api.db.models import (
    Branch,
    CreditStatus,
    Customer,
    CustomerAllocation,
    CustomerSite,
    Item,
    Principal,
    Receipt,
    SalesInvoice,
)
from trishul_api.modules.pur.common import ZERO, line_amounts, money, rupees, split_gst

__all__ = ["ZERO", "line_amounts", "money", "rupees", "split_gst"]

CUSTOMER_VIEW = "sal.customer.view"
CUSTOMER_MANAGE = "sal.customer.manage"
QUOTATION_VIEW = "sal.quotation.view"
QUOTATION_MANAGE = "sal.quotation.manage"
QUOTATION_APPROVE = "sal.quotation.approve"
ORDER_VIEW = "sal.order.view"
ORDER_MANAGE = "sal.order.manage"
ORDER_APPROVE = "sal.order.approve"
ORDER_CLOSE = "sal.order.close"
DELIVERY_MANAGE = "sal.delivery.manage"
DELIVERY_OVER_ORDER = "sal.delivery.over_order"
ACCOUNT_VIEW = "sal.account.view"
INVOICE_MANAGE = "sal.invoice.manage"
INVOICE_DIRECT = "sal.invoice.direct"
INVOICE_CANCEL = "sal.invoice.cancel"
RECEIPT_MANAGE = "sal.receipt.manage"
ALLOCATION_MANAGE = "sal.allocation.manage"
ALLOCATION_REVERSE = "sal.allocation.reverse"
CREDIT_OVERRIDE = "sal.credit.override"

#: Customer money: invoices, receipts, allocations, statements.
ACCOUNT_USERS = (ACCOUNT_VIEW, INVOICE_MANAGE, INVOICE_DIRECT, INVOICE_CANCEL, RECEIPT_MANAGE, ALLOCATION_MANAGE)
#: Anyone working in sales: may pick customers, their branches and see the dropdowns.
SALES_USERS = (
    CUSTOMER_VIEW,
    CUSTOMER_MANAGE,
    QUOTATION_VIEW,
    QUOTATION_MANAGE,
    QUOTATION_APPROVE,
    ORDER_VIEW,
    ORDER_MANAGE,
    ORDER_APPROVE,
    ORDER_CLOSE,
    DELIVERY_MANAGE,
    *ACCOUNT_USERS,
)


def err(field: str, message: str) -> ApiError:
    return ApiError(message, errors={field: [message]})


def require(actor: CurrentUser, permission: str, message: str = "You do not have permission for this action.") -> None:
    if not actor.can(permission):
        raise Forbidden(message)


def active_customer(db: Session, customer_id: int, field: str = "customerId") -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None or not customer.is_active:
        raise err(field, "Choose an active customer.")
    return customer


def customer_branch(
    db: Session, customer: Customer, site_id: int | None, field: str = "customerSiteId"
) -> CustomerSite | None:
    """The customer branch (core.customer_site) after checking it belongs to the customer."""
    if site_id is None:
        return None
    site = db.get(CustomerSite, site_id)
    if site is None or site.customer_id != customer.id or not site.is_active:
        raise err(field, "That branch is not an active branch of this customer.")
    return site


def active_branch(db: Session, actor: CurrentUser, branch_id: int, field: str = "branchId") -> Branch:
    branch = db.get(Branch, branch_id)
    if branch is None or not branch.is_active:
        raise err(field, "Choose an active branch.")
    if not actor.can_use_branch(branch.id):
        raise Forbidden("You do not have access to this branch.")
    return branch


def active_principal(db: Session, actor: CurrentUser, principal_id: int, field: str = "principalId") -> Principal:
    principal = db.get(Principal, principal_id)
    if principal is None or not principal.is_active:
        raise err(field, "Choose a brand.")
    if not actor.can_see_principal(principal.id):
        raise Forbidden("You do not have access to this brand.")
    return principal


def check_item_brand(item: Item, principal_id: int, field: str) -> None:
    """One brand per document: common items (no brand) or items of the document's brand."""
    if item.principal_id is not None and item.principal_id != principal_id:
        raise err(field, f"{item.item_code} belongs to another brand; one document is for one brand.")


def sale_item(db: Session, actor: CurrentUser, item_id: int, principal_id: int, field: str) -> Item:
    item = db.get(Item, item_id)
    if item is None or not item.is_active:
        raise err(field, "Choose an active item.")
    if item.principal_id is not None and not actor.can_see_principal(item.principal_id):
        raise err(field, "You do not have access to that item's brand.")
    check_item_brand(item, principal_id, field)
    return item


def place_of_supply(db: Session, customer: Customer, site: CustomerSite | None, branch_id: int) -> int:
    for state_id in (
        site.state_id if site else None,
        site.billing_state_id if site else None,
        customer.billing_state_id,
    ):
        if state_id is not None:
            return int(state_id)
    state_id = db.scalar(select(Branch.state_id).where(Branch.id == branch_id))
    if state_id is None:
        raise ApiError("The branch has no state set.")
    return int(state_id)


def is_inter_state(db: Session, branch_id: int, supply_state_id: int) -> bool:
    branch_state = db.scalar(select(Branch.state_id).where(Branch.id == branch_id))
    return branch_state is not None and branch_state != supply_state_id


def addresses(customer: Customer, site: CustomerSite | None) -> tuple[str | None, str | None]:
    """(billing, delivery) defaults: the branch's, else the customer's billing address for both."""
    billing = (site.billing_address if site else None) or customer.billing_address
    delivery = (site.address if site else None) or customer.billing_address
    return billing, delivery


# ---------------------------------------------------------------- balances


def invoiced_total(customer_id: Any) -> ColumnElement[Any]:
    return (
        select(func.coalesce(func.sum(SalesInvoice.total), 0))
        .where(SalesInvoice.customer_id == customer_id, SalesInvoice.status != "Cancelled",
               SalesInvoice.status != "Draft")
        .scalar_subquery()
    )  # fmt: skip


def received_total(customer_id: Any) -> ColumnElement[Any]:
    return (
        select(func.coalesce(func.sum(Receipt.amount), 0))
        .where(Receipt.customer_id == customer_id, Receipt.status == "Posted")
        .scalar_subquery()
    )


def balance_of(customer_id: Any) -> ColumnElement[Any]:
    return Customer.opening_balance + invoiced_total(customer_id) - received_total(customer_id)


def customer_balance(db: Session, customer: Customer) -> Decimal:
    invoiced = Decimal(db.scalar(select(invoiced_total(customer.id))) or 0)
    received = Decimal(db.scalar(select(received_total(customer.id))) or 0)
    return customer.opening_balance + invoiced - received


def allocated_to_invoice(db: Session, invoice_id: int) -> Decimal:
    return Decimal(
        db.scalar(
            select(func.coalesce(func.sum(CustomerAllocation.amount), 0)).where(
                CustomerAllocation.sales_invoice_id == invoice_id, CustomerAllocation.is_active
            )
        )
        or 0
    )


@dataclass(frozen=True)
class CreditCheck:
    within: bool
    balance: Decimal
    limit: Decimal | None
    after: Decimal
    blocked_status: str | None  # a credit status that stops invoicing

    @property
    def message(self) -> str:
        if self.blocked_status:
            return f"The customer's credit status is '{self.blocked_status}', which stops invoicing."
        assert self.limit is not None
        return (
            f"This takes the customer to {self.after:,.2f} against a credit limit of {self.limit:,.2f} "
            f"(balance now {self.balance:,.2f})."
        )


def credit_check(db: Session, customer: Customer, amount: Decimal, *, invoicing: bool = False) -> CreditCheck:
    balance = customer_balance(db, customer)
    after = balance + amount
    blocked = None
    if invoicing and customer.credit_status_id is not None:
        status = db.get(CreditStatus, customer.credit_status_id)
        if status is not None and status.disallow_invoicing:
            blocked = status.description
    limit = customer.credit_limit
    within = blocked is None and (limit is None or after <= limit)
    return CreditCheck(within=within, balance=balance, limit=limit, after=after, blocked_status=blocked)


def enforce_credit(actor: CurrentUser, check: CreditCheck, override: bool) -> bool:
    """True when the document goes through on an override (to be recorded)."""
    if check.within:
        return False
    if not override:
        hint = (
            " A user with credit override can approve it anyway."
            if not actor.can(CREDIT_OVERRIDE)
            else (" Tick 'override credit limit' to go ahead.")
        )
        raise Conflict(f"Over the credit limit. {check.message}{hint}")
    if not actor.can(CREDIT_OVERRIDE):
        raise Forbidden("Overriding the credit limit needs the credit override permission.")
    return True


def qty_text(value: Decimal) -> str:
    text = format(value.quantize(Decimal("0.001")), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text
