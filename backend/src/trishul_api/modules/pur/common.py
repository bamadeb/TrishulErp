"""Shared pieces of the purchases module: permissions, money rounding, the GST split and lookups."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError, Forbidden
from trishul_api.db.models import Branch, Supplier, SupplierAllocation

SUPPLIER_VIEW = "pur.supplier.view"
SUPPLIER_MANAGE = "pur.supplier.manage"
PO_VIEW = "pur.po.view"
PO_MANAGE = "pur.po.manage"
PO_APPROVE = "pur.po.approve"
PO_CLOSE = "pur.po.close"
GRN_MANAGE = "pur.grn.manage"
ACCOUNT_VIEW = "pur.account.view"
INVOICE_MANAGE = "pur.invoice.manage"
INVOICE_DIRECT = "pur.invoice.direct"
PAYMENT_MANAGE = "pur.payment.manage"
CREDIT_NOTE_MANAGE = "pur.credit_note.manage"
ALLOCATION_MANAGE = "pur.allocation.manage"
ALLOCATION_REVERSE = "pur.allocation.reverse"

#: May pick a supplier from the list: purchase users, and inventory users entering opening stock or prices.
SUPPLIER_PICKERS = (
    SUPPLIER_VIEW,
    SUPPLIER_MANAGE,
    PO_VIEW,
    PO_MANAGE,
    GRN_MANAGE,
    ACCOUNT_VIEW,
    INVOICE_MANAGE,
    PAYMENT_MANAGE,
    CREDIT_NOTE_MANAGE,
    "inv.item.manage",
    "inv.grn.manage",
)
#: Supplier money: invoices, payments, credit notes, allocations, statements.
ACCOUNT_USERS = (ACCOUNT_VIEW, INVOICE_MANAGE, INVOICE_DIRECT, PAYMENT_MANAGE, CREDIT_NOTE_MANAGE, ALLOCATION_MANAGE)

ZERO = Decimal(0)
_PAISE = Decimal("0.01")
_RUPEE = Decimal("1")


def money(value: Decimal) -> Decimal:
    return value.quantize(_PAISE, ROUND_HALF_UP)


def rupees(value: Decimal) -> Decimal:
    return value.quantize(_RUPEE, ROUND_HALF_UP)


@dataclass(frozen=True)
class LineAmounts:
    taxable: Decimal
    tax: Decimal
    total: Decimal


def line_amounts(quantity: Decimal, unit_price: Decimal, discount_pct: Decimal, gst_pct: Decimal) -> LineAmounts:
    """Taxable value after the discount, GST on it, and the line total (to the paisa)."""
    taxable = money(quantity * unit_price * (Decimal(100) - discount_pct) / Decimal(100))
    tax = money(taxable * gst_pct / Decimal(100))
    return LineAmounts(taxable=taxable, tax=tax, total=taxable + tax)


@dataclass(frozen=True)
class GstSplit:
    cgst: Decimal
    sgst: Decimal
    igst: Decimal


def split_gst(tax: Decimal, *, inter_state: bool) -> GstSplit:
    """IGST between states; CGST + SGST (half each) within one state."""
    if inter_state:
        return GstSplit(cgst=ZERO, sgst=ZERO, igst=money(tax))
    half = money(tax / 2)
    return GstSplit(cgst=half, sgst=money(tax) - half, igst=ZERO)


def is_inter_state(db: Session, supplier: Supplier, branch_id: int) -> bool:
    """A supplier with no state on record is treated as local (CGST + SGST)."""
    branch_state = db.scalar(select(Branch.state_id).where(Branch.id == branch_id))
    return supplier.state_id is not None and branch_state is not None and supplier.state_id != branch_state


def branch_state(db: Session, branch_id: int) -> int:
    state_id = db.scalar(select(Branch.state_id).where(Branch.id == branch_id))
    if state_id is None:
        raise ApiError("The branch has no state set.")
    return int(state_id)


def active_supplier(db: Session, supplier_id: int, field: str = "supplierId") -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None or not supplier.is_active:
        raise ApiError("Choose an active supplier.", errors={field: [f"Unknown or inactive supplier {supplier_id}."]})
    return supplier


def check_branch(actor: CurrentUser, branch_id: int) -> None:
    if not actor.can_use_branch(branch_id):
        raise Forbidden("You do not have access to this branch.")


def active_branch(db: Session, actor: CurrentUser, branch_id: int, field: str = "branchId") -> Branch:
    branch = db.get(Branch, branch_id)
    if branch is None or not branch.is_active:
        raise ApiError("Choose an active branch.", errors={field: [f"Unknown or inactive branch {branch_id}."]})
    check_branch(actor, branch.id)
    return branch


def allocated_to_invoice(db: Session, invoice_id: int) -> Decimal:
    return Decimal(
        db.scalar(
            select(func.coalesce(func.sum(SupplierAllocation.amount), 0)).where(
                SupplierAllocation.supplier_invoice_id == invoice_id, SupplierAllocation.is_active
            )
        )
        or 0
    )
