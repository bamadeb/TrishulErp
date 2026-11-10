from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy import select

from trishul_api.auth import CurrentUserDep, DbSession, ScopeDep, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE, problem_response
from trishul_api.common.schemas import Page
from trishul_api.db.models import LookupType, LookupValue
from trishul_api.modules.inv.masters_schemas import LookupOption
from trishul_api.modules.pur.account_schemas import (
    AccountQuery,
    AllocationCreate,
    AllocationOut,
    AllocationQuery,
    AllocationReverse,
    CreditNoteCreate,
    CreditNoteDetail,
    CreditNoteListItem,
    InvoiceCreate,
    InvoiceDetail,
    InvoiceListItem,
    InvoiceQuery,
    PaymentCreate,
    PaymentDetail,
    PaymentListItem,
)
from trishul_api.modules.pur.account_service import RETURN_REASON, AccountService
from trishul_api.modules.pur.common import (
    ACCOUNT_USERS,
    ALLOCATION_MANAGE,
    ALLOCATION_REVERSE,
    CREDIT_NOTE_MANAGE,
    GRN_MANAGE,
    INVOICE_DIRECT,
    INVOICE_MANAGE,
    PAYMENT_MANAGE,
    PO_APPROVE,
    PO_CLOSE,
    PO_MANAGE,
    PO_VIEW,
    SUPPLIER_MANAGE,
    SUPPLIER_PICKERS,
    SUPPLIER_VIEW,
)
from trishul_api.modules.pur.grn_schemas import (
    GrnCreate,
    GrnDetail,
    GrnListItem,
    GrnQuery,
    UninvoicedLine,
    UninvoicedQuery,
)
from trishul_api.modules.pur.grn_service import GrnService
from trishul_api.modules.pur.po_schemas import (
    OutstandingLine,
    OutstandingQuery,
    PoCreate,
    PoDetail,
    PoListItem,
    PoNote,
    PoQuery,
)
from trishul_api.modules.pur.po_service import PurchaseOrderService
from trishul_api.modules.pur.supplier_schemas import (
    StatementQuery,
    SupplierCreate,
    SupplierDetail,
    SupplierFormOptions,
    SupplierOpenItems,
    SupplierOut,
    SupplierQuery,
    SupplierStatement,
    SupplierUpdate,
)
from trishul_api.modules.pur.supplier_service import SupplierService

router = APIRouter(prefix="/pur", tags=["purchases"])

PO_USERS = (PO_VIEW, PO_MANAGE, PO_APPROVE, PO_CLOSE, GRN_MANAGE, *ACCOUNT_USERS)
GRN_USERS = (GRN_MANAGE, PO_VIEW, PO_MANAGE, "inv.stock.view", *ACCOUNT_USERS)

CAN_PICK_SUPPLIER = Depends(require_permission(*SUPPLIER_PICKERS))
CAN_SEE_SUPPLIER = Depends(require_permission(SUPPLIER_VIEW, SUPPLIER_MANAGE, *ACCOUNT_USERS))
CAN_MANAGE_SUPPLIER = Depends(require_permission(SUPPLIER_MANAGE))
CAN_SEE_PO = Depends(require_permission(*PO_USERS))
CAN_MANAGE_PO = Depends(require_permission(PO_MANAGE))
CAN_APPROVE_PO = Depends(require_permission(PO_APPROVE))
CAN_CLOSE_PO = Depends(require_permission(PO_CLOSE))
CAN_CANCEL_PO = Depends(require_permission(PO_MANAGE, PO_CLOSE))
CAN_SEE_GRN = Depends(require_permission(*GRN_USERS))
CAN_RECEIVE = Depends(require_permission(GRN_MANAGE))
CAN_SEE_ACCOUNTS = Depends(require_permission(*ACCOUNT_USERS))
CAN_INVOICE = Depends(require_permission(INVOICE_MANAGE, INVOICE_DIRECT))
CAN_PAY = Depends(require_permission(PAYMENT_MANAGE))
CAN_CREDIT = Depends(require_permission(CREDIT_NOTE_MANAGE))
CAN_ALLOCATE = Depends(require_permission(ALLOCATION_MANAGE))
CAN_REVERSE = Depends(require_permission(ALLOCATION_REVERSE))

RowVersionDep = Annotated[bytes, Depends(if_match_row_version)]
SupplierId = Annotated[int, Path(alias="supplierId", gt=0)]
PoId = Annotated[int, Path(alias="poId", gt=0)]
UPDATE_RESPONSES = {**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES}
POSTING_RESPONSES: dict[int | str, dict[str, Any]] = {
    409: problem_response("A duplicate number, or stock / amounts changed while saving; reload and try again.")
}
ACTION_RESPONSES: dict[int | str, dict[str, Any]] = {
    **NOT_FOUND_RESPONSE,
    409: problem_response("The order's status doesn't allow this."),
}


def _suppliers(db: DbSession, actor: CurrentUserDep) -> SupplierService:
    return SupplierService(db, actor)


def _orders(db: DbSession, actor: CurrentUserDep) -> PurchaseOrderService:
    return PurchaseOrderService(db, actor)


def _grns(db: DbSession, actor: CurrentUserDep) -> GrnService:
    return GrnService(db, actor)


def _accounts(db: DbSession, actor: CurrentUserDep) -> AccountService:
    return AccountService(db, actor)


Suppliers = Annotated[SupplierService, Depends(_suppliers)]
Orders = Annotated[PurchaseOrderService, Depends(_orders)]
Grns = Annotated[GrnService, Depends(_grns)]
Accounts = Annotated[AccountService, Depends(_accounts)]


# ---------------------------------------------------------------- suppliers


@router.get("/suppliers", summary="Suppliers with their balance, searched and paged", dependencies=[CAN_PICK_SUPPLIER])
def list_suppliers(query: Annotated[SupplierQuery, Query()], suppliers: Suppliers) -> Page[SupplierOut]:
    return suppliers.search(query)


@router.get(
    "/suppliers/form-options",
    summary="States and payment terms for the supplier form",
    dependencies=[CAN_PICK_SUPPLIER],
)
def get_supplier_form_options(suppliers: Suppliers) -> SupplierFormOptions:
    return suppliers.form_options()


@router.get(
    "/suppliers/{supplierId}",
    summary="One supplier with balances",
    dependencies=[CAN_SEE_SUPPLIER],
    responses=NOT_FOUND_RESPONSE,
)
def get_supplier(supplier_id: SupplierId, suppliers: Suppliers) -> SupplierDetail:
    return suppliers.get(supplier_id)


@router.get(
    "/suppliers/{supplierId}/statement",
    summary="Supplier transaction statement with opening and closing balance",
    dependencies=[CAN_SEE_ACCOUNTS],
    responses=NOT_FOUND_RESPONSE,
)
def get_supplier_statement(
    supplier_id: SupplierId, query: Annotated[StatementQuery, Query()], suppliers: Suppliers
) -> SupplierStatement:
    return suppliers.statement(supplier_id, query)


@router.get(
    "/suppliers/{supplierId}/open-items",
    summary="Outstanding invoices and unallocated payments / credit notes of a supplier",
    dependencies=[CAN_SEE_ACCOUNTS],
    responses=NOT_FOUND_RESPONSE,
)
def get_supplier_open_items(supplier_id: SupplierId, suppliers: Suppliers) -> SupplierOpenItems:
    return suppliers.open_items(supplier_id)


@router.post("/suppliers", summary="Add a supplier", status_code=201, dependencies=[CAN_MANAGE_SUPPLIER])
def create_supplier(data: SupplierCreate, scope: ScopeDep, suppliers: Suppliers) -> SupplierDetail:
    return suppliers.create(data, scope)


@router.patch(
    "/suppliers/{supplierId}", summary="Change or deactivate a supplier", dependencies=[CAN_MANAGE_SUPPLIER],
    responses=UPDATE_RESPONSES,
)  # fmt: skip
def update_supplier(
    supplier_id: SupplierId, data: SupplierUpdate, row_version: RowVersionDep, suppliers: Suppliers
) -> SupplierDetail:
    return suppliers.update(supplier_id, row_version, data)


# ---------------------------------------------------------------- purchase orders


@router.get("/purchase-orders", summary="Purchase orders, filtered (inquiry)", dependencies=[CAN_SEE_PO])
def list_purchase_orders(query: Annotated[PoQuery, Query()], orders: Orders) -> Page[PoListItem]:
    return orders.search(query)


@router.get(
    "/outstanding-po-lines", summary="Order lines still to be received (outstanding orders)", dependencies=[CAN_SEE_PO]
)
def list_outstanding_po_lines(query: Annotated[OutstandingQuery, Query()], orders: Orders) -> Page[OutstandingLine]:
    return orders.outstanding(query)


@router.get(
    "/purchase-orders/{poId}", summary="One purchase order", dependencies=[CAN_SEE_PO], responses=NOT_FOUND_RESPONSE
)
def get_purchase_order(po_id: PoId, orders: Orders) -> PoDetail:
    return orders.get(po_id)


@router.post(
    "/purchase-orders", summary="Create a purchase order (draft)", status_code=201, dependencies=[CAN_MANAGE_PO]
)
def create_purchase_order(data: PoCreate, orders: Orders, response: Response) -> PoDetail:
    created = orders.create(data)
    response.headers["Location"] = f"purchase-orders/{created.id}"
    return created


@router.put(
    "/purchase-orders/{poId}", summary="Replace a draft purchase order", dependencies=[CAN_MANAGE_PO],
    responses={**UPDATE_RESPONSES, **ACTION_RESPONSES},
)  # fmt: skip
def update_purchase_order(po_id: PoId, data: PoCreate, row_version: RowVersionDep, orders: Orders) -> PoDetail:
    return orders.update(po_id, row_version, data)


@router.post(
    "/purchase-orders/{poId}/submit", summary="Send a draft for approval", dependencies=[CAN_MANAGE_PO],
    responses=ACTION_RESPONSES,
)  # fmt: skip
def submit_purchase_order(po_id: PoId, orders: Orders) -> PoDetail:
    return orders.submit(po_id)


@router.post(
    "/purchase-orders/{poId}/approve", summary="Approve an order", dependencies=[CAN_APPROVE_PO],
    responses=ACTION_RESPONSES,
)  # fmt: skip
def approve_purchase_order(po_id: PoId, data: PoNote, orders: Orders) -> PoDetail:
    return orders.approve(po_id, data)


@router.post(
    "/purchase-orders/{poId}/reject", summary="Send an order back to draft", dependencies=[CAN_APPROVE_PO],
    responses=ACTION_RESPONSES,
)  # fmt: skip
def reject_purchase_order(po_id: PoId, data: PoNote, orders: Orders) -> PoDetail:
    return orders.reject(po_id, data)


@router.post(
    "/purchase-orders/{poId}/close", summary="Close an outstanding order (the rest won't come)",
    dependencies=[CAN_CLOSE_PO], responses=ACTION_RESPONSES,
)  # fmt: skip
def close_purchase_order(po_id: PoId, data: PoNote, orders: Orders) -> PoDetail:
    return orders.close(po_id, data)


@router.post(
    "/purchase-orders/{poId}/cancel", summary="Cancel an order nothing was received against",
    dependencies=[CAN_CANCEL_PO], responses=ACTION_RESPONSES,
)  # fmt: skip
def cancel_purchase_order(po_id: PoId, data: PoNote, orders: Orders) -> PoDetail:
    return orders.cancel(po_id, data)


# ---------------------------------------------------------------- GRN


@router.get("/grns", summary="Goods receipts (GRN), newest first", dependencies=[CAN_SEE_GRN])
def list_grns(query: Annotated[GrnQuery, Query()], grns: Grns) -> Page[GrnListItem]:
    return grns.search(query)


@router.get(
    "/grns/{grnId}", summary="One GRN with its batches", dependencies=[CAN_SEE_GRN], responses=NOT_FOUND_RESPONSE
)
def get_grn(grn_id: Annotated[int, Path(alias="grnId", gt=0)], grns: Grns) -> GrnDetail:
    return grns.get(grn_id)


@router.post(
    "/grns", summary="Receive goods (direct or against an order); stock is added, aged from the GRN date",
    status_code=201, dependencies=[CAN_RECEIVE], responses=POSTING_RESPONSES,
)  # fmt: skip
def create_grn(data: GrnCreate, grns: Grns, response: Response) -> GrnDetail:
    created = grns.create(data)
    response.headers["Location"] = f"grns/{created.id}"
    return created


@router.get("/uninvoiced-grn-lines", summary="GRN lines of a supplier not invoiced yet", dependencies=[CAN_INVOICE])
def list_uninvoiced_grn_lines(query: Annotated[UninvoicedQuery, Query()], grns: Grns) -> list[UninvoicedLine]:
    return grns.uninvoiced(query)


# ---------------------------------------------------------------- supplier invoices


@router.get("/supplier-invoices", summary="Supplier invoices with what is outstanding", dependencies=[CAN_SEE_ACCOUNTS])
def list_supplier_invoices(query: Annotated[InvoiceQuery, Query()], accounts: Accounts) -> Page[InvoiceListItem]:
    return accounts.invoices(query)


@router.get(
    "/supplier-invoices/{invoiceId}", summary="One supplier invoice with its allocations",
    dependencies=[CAN_SEE_ACCOUNTS], responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def get_supplier_invoice(
    invoice_id: Annotated[int, Path(alias="invoiceId", gt=0)], accounts: Accounts
) -> InvoiceDetail:
    return accounts.invoice(invoice_id)


@router.post(
    "/supplier-invoices", summary="Record a supplier invoice (against GRNs, or direct with permission)",
    status_code=201, dependencies=[CAN_INVOICE], responses=POSTING_RESPONSES,
)  # fmt: skip
def create_supplier_invoice(data: InvoiceCreate, accounts: Accounts, response: Response) -> InvoiceDetail:
    created = accounts.create_invoice(data)
    response.headers["Location"] = f"supplier-invoices/{created.id}"
    return created


# ---------------------------------------------------------------- payments


@router.get("/supplier-payments", summary="Payments to suppliers", dependencies=[CAN_SEE_ACCOUNTS])
def list_supplier_payments(query: Annotated[AccountQuery, Query()], accounts: Accounts) -> Page[PaymentListItem]:
    return accounts.payments(query)


@router.get(
    "/supplier-payments/{paymentId}", summary="One payment (voucher) with its allocations",
    dependencies=[CAN_SEE_ACCOUNTS], responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def get_supplier_payment(
    payment_id: Annotated[int, Path(alias="paymentId", gt=0)], accounts: Accounts
) -> PaymentDetail:
    return accounts.payment(payment_id)


@router.post(
    "/supplier-payments", summary="Record a payment, optionally allocated to invoices", status_code=201,
    dependencies=[CAN_PAY], responses=POSTING_RESPONSES,
)  # fmt: skip
def create_supplier_payment(data: PaymentCreate, accounts: Accounts, response: Response) -> PaymentDetail:
    created = accounts.create_payment(data)
    response.headers["Location"] = f"supplier-payments/{created.id}"
    return created


# ---------------------------------------------------------------- credit notes


@router.get("/credit-notes", summary="Supplier credit notes", dependencies=[CAN_SEE_ACCOUNTS])
def list_credit_notes(query: Annotated[AccountQuery, Query()], accounts: Accounts) -> Page[CreditNoteListItem]:
    return accounts.credit_notes(query)


@router.get(
    "/credit-notes/{noteId}", summary="One supplier credit note", dependencies=[CAN_SEE_ACCOUNTS],
    responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def get_credit_note(note_id: Annotated[int, Path(alias="noteId", gt=0)], accounts: Accounts) -> CreditNoteDetail:
    return accounts.credit_note(note_id)


@router.post(
    "/credit-notes", summary="Record a supplier credit note; a purchase return takes the goods out of stock",
    status_code=201, dependencies=[CAN_CREDIT], responses=POSTING_RESPONSES,
)  # fmt: skip
def create_credit_note(data: CreditNoteCreate, accounts: Accounts, response: Response) -> CreditNoteDetail:
    created = accounts.create_credit_note(data)
    response.headers["Location"] = f"credit-notes/{created.id}"
    return created


@router.get("/return-reasons", summary="Reasons for a purchase return", dependencies=[CAN_CREDIT])
def list_return_reasons(db: DbSession) -> list[LookupOption]:
    rows = db.execute(
        select(LookupValue.id, LookupValue.code, LookupValue.label)
        .join(LookupType, LookupType.id == LookupValue.lookup_type_id)
        .where(LookupType.code == RETURN_REASON, LookupValue.is_active)
        .order_by(LookupValue.sort_order, LookupValue.label)
    ).mappings()
    return [LookupOption.model_validate(r) for r in rows.all()]


# ---------------------------------------------------------------- allocations


@router.get("/allocations", summary="Allocation inquiry, newest first", dependencies=[CAN_SEE_ACCOUNTS])
def list_allocations(query: Annotated[AllocationQuery, Query()], accounts: Accounts) -> Page[AllocationOut]:
    return accounts.allocations(query)


@router.post(
    "/allocations", summary="Set a payment or credit note against invoices", status_code=201,
    dependencies=[CAN_ALLOCATE], responses=POSTING_RESPONSES,
)  # fmt: skip
def create_allocations(data: AllocationCreate, accounts: Accounts) -> list[AllocationOut]:
    return accounts.allocate(data)


@router.post(
    "/allocations/{allocationId}/reverse", summary="Reverse an allocation (kept in the history)",
    dependencies=[CAN_REVERSE], responses=ACTION_RESPONSES,
)  # fmt: skip
def reverse_allocation(
    allocation_id: Annotated[int, Path(alias="allocationId", gt=0)], data: AllocationReverse, accounts: Accounts
) -> AllocationOut:
    return accounts.reverse(allocation_id, data)
