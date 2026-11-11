from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, ScopeDep, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE, problem_response
from trishul_api.common.schemas import Page
from trishul_api.modules.sal.account_schemas import (
    CustomerAllocationCreate,
    CustomerAllocationOut,
    CustomerAllocationQuery,
    CustomerAllocationReverse,
    ReceiptCreate,
    ReceiptDetail,
    ReceiptListItem,
    ReceiptQuery,
    SalesInvoiceCancel,
    SalesInvoiceCreate,
    SalesInvoiceDetail,
    SalesInvoiceListItem,
    SalesInvoiceQuery,
)
from trishul_api.modules.sal.account_service import SalesAccountService
from trishul_api.modules.sal.common import (
    ACCOUNT_USERS,
    ALLOCATION_MANAGE,
    ALLOCATION_REVERSE,
    CUSTOMER_MANAGE,
    DELIVERY_MANAGE,
    INVOICE_CANCEL,
    INVOICE_DIRECT,
    INVOICE_MANAGE,
    ORDER_APPROVE,
    ORDER_CLOSE,
    ORDER_MANAGE,
    ORDER_VIEW,
    QUOTATION_APPROVE,
    QUOTATION_MANAGE,
    QUOTATION_VIEW,
    RECEIPT_MANAGE,
    SALES_USERS,
)
from trishul_api.modules.sal.customer_schemas import (
    CreditTermsUpdate,
    CustomerAccount,
    CustomerAccountDetail,
    CustomerAccountQuery,
    CustomerBranchCreate,
    CustomerBranchOut,
    CustomerBranchUpdate,
    CustomerOpenItems,
    CustomerStatement,
    CustomerStatementQuery,
    ItemSaleInfo,
    SalesFormOptions,
)
from trishul_api.modules.sal.customer_service import CustomerAccountService
from trishul_api.modules.sal.delivery_schemas import (
    DeliveryCancel,
    DeliveryConfirm,
    DeliveryCreate,
    DeliveryDetail,
    DeliveryListItem,
    DeliveryQuery,
    UninvoicedDeliveryLine,
    UninvoicedDeliveryQuery,
)
from trishul_api.modules.sal.delivery_service import DeliveryService
from trishul_api.modules.sal.order_schemas import (
    OrderApprove,
    OrderCreate,
    OrderDetail,
    OrderListItem,
    OrderNote,
    OrderQuery,
    OutstandingOrderLine,
    OutstandingOrderQuery,
)
from trishul_api.modules.sal.order_service import SalesOrderService
from trishul_api.modules.sal.quotation_schemas import (
    ConvertQuotation,
    QuotationCreate,
    QuotationDetail,
    QuotationListItem,
    QuotationNote,
    QuotationQuery,
)
from trishul_api.modules.sal.quotation_service import QuotationService

router = APIRouter(prefix="/sal", tags=["sales"])

QUOTATION_USERS = (QUOTATION_VIEW, QUOTATION_MANAGE, QUOTATION_APPROVE, ORDER_MANAGE)
ORDER_USERS = (ORDER_VIEW, ORDER_MANAGE, ORDER_APPROVE, ORDER_CLOSE, DELIVERY_MANAGE, *ACCOUNT_USERS)
DELIVERY_USERS = (DELIVERY_MANAGE, ORDER_VIEW, ORDER_MANAGE, *ACCOUNT_USERS)

CAN_USE_SALES = Depends(require_permission(*SALES_USERS))
CAN_MANAGE_CUSTOMERS = Depends(require_permission(CUSTOMER_MANAGE))
CAN_SEE_ACCOUNTS = Depends(require_permission(*ACCOUNT_USERS, "sal.customer.view", CUSTOMER_MANAGE))
CAN_SEE_QUOTATIONS = Depends(require_permission(*QUOTATION_USERS))
CAN_MANAGE_QUOTATIONS = Depends(require_permission(QUOTATION_MANAGE))
CAN_APPROVE_QUOTATIONS = Depends(require_permission(QUOTATION_APPROVE))
CAN_CONVERT_QUOTATIONS = Depends(require_permission(QUOTATION_MANAGE, ORDER_MANAGE))
CAN_SEE_ORDERS = Depends(require_permission(*ORDER_USERS))
CAN_MANAGE_ORDERS = Depends(require_permission(ORDER_MANAGE))
CAN_APPROVE_ORDERS = Depends(require_permission(ORDER_APPROVE))
CAN_CLOSE_ORDERS = Depends(require_permission(ORDER_CLOSE))
CAN_CANCEL_ORDERS = Depends(require_permission(ORDER_MANAGE, ORDER_CLOSE))
CAN_SEE_DELIVERIES = Depends(require_permission(*DELIVERY_USERS))
CAN_DELIVER = Depends(require_permission(DELIVERY_MANAGE))
CAN_SEE_MONEY = Depends(require_permission(*ACCOUNT_USERS))
CAN_INVOICE = Depends(require_permission(INVOICE_MANAGE, INVOICE_DIRECT))
CAN_CANCEL_INVOICE = Depends(require_permission(INVOICE_CANCEL))
CAN_RECEIVE = Depends(require_permission(RECEIPT_MANAGE))
CAN_ALLOCATE = Depends(require_permission(ALLOCATION_MANAGE))
CAN_REVERSE = Depends(require_permission(ALLOCATION_REVERSE))

RowVersionDep = Annotated[bytes, Depends(if_match_row_version)]
CustomerId = Annotated[int, Path(alias="customerId", gt=0)]
QuotationId = Annotated[int, Path(alias="quotationId", gt=0)]
OrderId = Annotated[int, Path(alias="orderId", gt=0)]
DeliveryId = Annotated[int, Path(alias="deliveryId", gt=0)]
InvoiceId = Annotated[int, Path(alias="invoiceId", gt=0)]
UPDATE_RESPONSES = {**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES}
POSTING_RESPONSES: dict[int | str, dict[str, Any]] = {
    409: problem_response("Over the credit limit, a duplicate number, or stock changed while saving.")
}
ACTION_RESPONSES: dict[int | str, dict[str, Any]] = {
    **NOT_FOUND_RESPONSE,
    409: problem_response("The document's status doesn't allow this (or the credit limit is exceeded)."),
}


def _customers(db: DbSession, actor: CurrentUserDep) -> CustomerAccountService:
    return CustomerAccountService(db, actor)


def _quotations(db: DbSession, actor: CurrentUserDep) -> QuotationService:
    return QuotationService(db, actor)


def _orders(db: DbSession, actor: CurrentUserDep) -> SalesOrderService:
    return SalesOrderService(db, actor)


def _deliveries(db: DbSession, actor: CurrentUserDep) -> DeliveryService:
    return DeliveryService(db, actor)


def _accounts(db: DbSession, actor: CurrentUserDep) -> SalesAccountService:
    return SalesAccountService(db, actor)


Customers = Annotated[CustomerAccountService, Depends(_customers)]
Quotations = Annotated[QuotationService, Depends(_quotations)]
Orders = Annotated[SalesOrderService, Depends(_orders)]
Deliveries = Annotated[DeliveryService, Depends(_deliveries)]
Accounts = Annotated[SalesAccountService, Depends(_accounts)]


# ---------------------------------------------------------------- lookups


@router.get(
    "/form-options", summary="Brands, branches, dispatch locations, terms and states", dependencies=[CAN_USE_SALES]
)
def get_sales_form_options(scope: ScopeDep, customers: Customers) -> SalesFormOptions:
    return customers.form_options(scope)


@router.get(
    "/items/{itemId}/sale-info", summary="An item's unit, selling price and stock by location",
    dependencies=[CAN_USE_SALES], responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def get_item_sale_info(
    item_id: Annotated[int, Path(alias="itemId", gt=0)],
    customers: Customers,
    principal_id: Annotated[int | None, Query(alias="principalId")] = None,
) -> ItemSaleInfo:
    return customers.item_info(item_id, principal_id)


# ---------------------------------------------------------------- customers


@router.get("/customers", summary="Customers with their balance and credit limit", dependencies=[CAN_USE_SALES])
def list_customer_accounts(
    query: Annotated[CustomerAccountQuery, Query()], customers: Customers
) -> Page[CustomerAccount]:
    return customers.search(query)


@router.get(
    "/customers/{customerId}", summary="A customer's account: balance, credit, overdue, advances",
    dependencies=[CAN_USE_SALES], responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def get_customer_account(customer_id: CustomerId, customers: Customers) -> CustomerAccountDetail:
    return customers.get(customer_id)


@router.patch(
    "/customers/{customerId}/credit-terms", summary="Change credit limit, payment terms or opening balance",
    dependencies=[CAN_MANAGE_CUSTOMERS], responses=UPDATE_RESPONSES,
)  # fmt: skip
def update_customer_credit_terms(
    customer_id: CustomerId, data: CreditTermsUpdate, row_version: RowVersionDep, customers: Customers
) -> CustomerAccountDetail:
    return customers.update_terms(customer_id, row_version, data)


@router.get(
    "/customers/{customerId}/branches", summary="A customer's branches (delivery and billing addresses)",
    dependencies=[CAN_USE_SALES], responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def list_customer_branches(
    customer_id: CustomerId,
    customers: Customers,
    include_inactive: Annotated[bool, Query(alias="includeInactive")] = False,
) -> list[CustomerBranchOut]:
    return customers.branches(customer_id, include_inactive)


@router.post(
    "/customers/{customerId}/branches", summary="Add a branch to a customer", dependencies=[CAN_MANAGE_CUSTOMERS],
    responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def add_customer_branch(customer_id: CustomerId, data: CustomerBranchCreate, customers: Customers) -> CustomerBranchOut:
    return customers.create_branch(customer_id, data)


@router.patch(
    "/customer-branches/{branchId}", summary="Change or deactivate a customer branch",
    dependencies=[CAN_MANAGE_CUSTOMERS], responses=UPDATE_RESPONSES,
)  # fmt: skip
def update_customer_branch(
    branch_id: Annotated[int, Path(alias="branchId", gt=0)],
    data: CustomerBranchUpdate,
    row_version: RowVersionDep,
    customers: Customers,
) -> CustomerBranchOut:
    return customers.update_branch(branch_id, row_version, data)


@router.get(
    "/customers/{customerId}/statement", summary="Customer statement with opening and closing balance",
    dependencies=[CAN_SEE_ACCOUNTS], responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def get_customer_statement(
    customer_id: CustomerId, query: Annotated[CustomerStatementQuery, Query()], customers: Customers
) -> CustomerStatement:
    return customers.statement(customer_id, query)


@router.get(
    "/customers/{customerId}/open-items", summary="Outstanding invoices and unallocated receipts of a customer",
    dependencies=[CAN_SEE_ACCOUNTS], responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def get_customer_open_items(customer_id: CustomerId, customers: Customers) -> CustomerOpenItems:
    return customers.open_items(customer_id)


# ---------------------------------------------------------------- quotations


@router.get("/quotations", summary="Sales quotations, filtered", dependencies=[CAN_SEE_QUOTATIONS])
def list_quotations(query: Annotated[QuotationQuery, Query()], quotations: Quotations) -> Page[QuotationListItem]:
    return quotations.search(query)


@router.get(
    "/quotations/{quotationId}", summary="One quotation (current version) with its revisions",
    dependencies=[CAN_SEE_QUOTATIONS], responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def get_quotation(quotation_id: QuotationId, quotations: Quotations) -> QuotationDetail:
    return quotations.get(quotation_id)


@router.post("/quotations", summary="Create a quotation (draft)", status_code=201, dependencies=[CAN_MANAGE_QUOTATIONS])
def create_quotation(data: QuotationCreate, quotations: Quotations, response: Response) -> QuotationDetail:
    created = quotations.create(data)
    response.headers["Location"] = f"quotations/{created.id}"
    return created


@router.put(
    "/quotations/{quotationId}", summary="Replace a draft quotation", dependencies=[CAN_MANAGE_QUOTATIONS],
    responses={**UPDATE_RESPONSES, **ACTION_RESPONSES},
)  # fmt: skip
def update_quotation(
    quotation_id: QuotationId, data: QuotationCreate, row_version: RowVersionDep, quotations: Quotations
) -> QuotationDetail:
    return quotations.update(quotation_id, row_version, data)


@router.post(
    "/quotations/{quotationId}/submit", summary="Submit to the customer (discounts may need approval first)",
    dependencies=[CAN_MANAGE_QUOTATIONS], responses=ACTION_RESPONSES,
)  # fmt: skip
def submit_quotation(quotation_id: QuotationId, quotations: Quotations) -> QuotationDetail:
    return quotations.submit(quotation_id)


@router.post(
    "/quotations/{quotationId}/approve", summary="Approve a quotation's discounts",
    dependencies=[CAN_APPROVE_QUOTATIONS], responses=ACTION_RESPONSES,
)  # fmt: skip
def approve_quotation(quotation_id: QuotationId, quotations: Quotations) -> QuotationDetail:
    return quotations.approve(quotation_id)


@router.post(
    "/quotations/{quotationId}/send-back", summary="Send a quotation waiting for approval back to draft",
    dependencies=[CAN_APPROVE_QUOTATIONS], responses=ACTION_RESPONSES,
)  # fmt: skip
def send_back_quotation(quotation_id: QuotationId, data: QuotationNote, quotations: Quotations) -> QuotationDetail:
    return quotations.send_back(quotation_id, data)


@router.post(
    "/quotations/{quotationId}/accept", summary="Record that the customer accepted",
    dependencies=[CAN_MANAGE_QUOTATIONS], responses=ACTION_RESPONSES,
)  # fmt: skip
def accept_quotation(quotation_id: QuotationId, data: QuotationNote, quotations: Quotations) -> QuotationDetail:
    return quotations.accept(quotation_id, data)


@router.post(
    "/quotations/{quotationId}/reject", summary="Record that the customer rejected",
    dependencies=[CAN_MANAGE_QUOTATIONS], responses=ACTION_RESPONSES,
)  # fmt: skip
def reject_quotation(quotation_id: QuotationId, data: QuotationNote, quotations: Quotations) -> QuotationDetail:
    return quotations.reject(quotation_id, data)


@router.post(
    "/quotations/{quotationId}/revise", summary="Start a new revision (the old version is kept)",
    dependencies=[CAN_MANAGE_QUOTATIONS], responses=ACTION_RESPONSES,
)  # fmt: skip
def revise_quotation(quotation_id: QuotationId, data: QuotationNote, quotations: Quotations) -> QuotationDetail:
    return quotations.revise(quotation_id, data)


@router.post(
    "/quotations/{quotationId}/convert", summary="Turn an accepted quotation into a draft sales order",
    dependencies=[CAN_CONVERT_QUOTATIONS], responses=ACTION_RESPONSES,
)  # fmt: skip
def convert_quotation(quotation_id: QuotationId, data: ConvertQuotation, quotations: Quotations) -> OrderDetail:
    return quotations.convert(quotation_id, data)


# ---------------------------------------------------------------- sales orders


@router.get("/sales-orders", summary="Sales orders, filtered (inquiry)", dependencies=[CAN_SEE_ORDERS])
def list_sales_orders(query: Annotated[OrderQuery, Query()], orders: Orders) -> Page[OrderListItem]:
    return orders.search(query)


@router.get("/outstanding-order-lines", summary="Order lines still to be delivered", dependencies=[CAN_SEE_ORDERS])
def list_outstanding_order_lines(
    query: Annotated[OutstandingOrderQuery, Query()], orders: Orders
) -> Page[OutstandingOrderLine]:
    return orders.outstanding(query)


@router.get(
    "/sales-orders/{orderId}", summary="One sales order with deliveries, invoices and advances",
    dependencies=[CAN_SEE_ORDERS], responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def get_sales_order(order_id: OrderId, orders: Orders) -> OrderDetail:
    return orders.get(order_id)


@router.post("/sales-orders", summary="Create a sales order (draft)", status_code=201, dependencies=[CAN_MANAGE_ORDERS])
def create_sales_order(data: OrderCreate, orders: Orders, response: Response) -> OrderDetail:
    created = orders.create(data)
    response.headers["Location"] = f"sales-orders/{created.id}"
    return created


@router.put(
    "/sales-orders/{orderId}", summary="Replace a draft sales order", dependencies=[CAN_MANAGE_ORDERS],
    responses={**UPDATE_RESPONSES, **ACTION_RESPONSES},
)  # fmt: skip
def update_sales_order(order_id: OrderId, data: OrderCreate, row_version: RowVersionDep, orders: Orders) -> OrderDetail:
    return orders.update(order_id, row_version, data)


@router.post(
    "/sales-orders/{orderId}/submit", summary="Send a draft for approval", dependencies=[CAN_MANAGE_ORDERS],
    responses=ACTION_RESPONSES,
)  # fmt: skip
def submit_sales_order(order_id: OrderId, orders: Orders) -> OrderDetail:
    return orders.submit(order_id)


@router.post(
    "/sales-orders/{orderId}/approve", summary="Approve an order (checks the credit limit)",
    dependencies=[CAN_APPROVE_ORDERS], responses=ACTION_RESPONSES,
)  # fmt: skip
def approve_sales_order(order_id: OrderId, data: OrderApprove, orders: Orders) -> OrderDetail:
    return orders.approve(order_id, data)


@router.post(
    "/sales-orders/{orderId}/reject", summary="Send an order back to draft", dependencies=[CAN_APPROVE_ORDERS],
    responses=ACTION_RESPONSES,
)  # fmt: skip
def reject_sales_order(order_id: OrderId, data: OrderNote, orders: Orders) -> OrderDetail:
    return orders.reject(order_id, data)


@router.post(
    "/sales-orders/{orderId}/close", summary="Close an outstanding order (the rest won't be delivered)",
    dependencies=[CAN_CLOSE_ORDERS], responses=ACTION_RESPONSES,
)  # fmt: skip
def close_sales_order(order_id: OrderId, data: OrderNote, orders: Orders) -> OrderDetail:
    return orders.close(order_id, data)


@router.post(
    "/sales-orders/{orderId}/cancel", summary="Cancel an order nothing went out against",
    dependencies=[CAN_CANCEL_ORDERS], responses=ACTION_RESPONSES,
)  # fmt: skip
def cancel_sales_order(order_id: OrderId, data: OrderNote, orders: Orders) -> OrderDetail:
    return orders.cancel(order_id, data)


# ---------------------------------------------------------------- deliveries


@router.get("/deliveries", summary="Delivery notes, newest first", dependencies=[CAN_SEE_DELIVERIES])
def list_deliveries(query: Annotated[DeliveryQuery, Query()], deliveries: Deliveries) -> Page[DeliveryListItem]:
    return deliveries.search(query)


@router.get(
    "/deliveries/{deliveryId}", summary="One delivery note with the GRN batches taken",
    dependencies=[CAN_SEE_DELIVERIES], responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def get_delivery(delivery_id: DeliveryId, deliveries: Deliveries) -> DeliveryDetail:
    return deliveries.get(delivery_id)


@router.post(
    "/deliveries", summary="Deliver goods (against an order or direct); stock goes out at once",
    status_code=201, dependencies=[CAN_DELIVER], responses=POSTING_RESPONSES,
)  # fmt: skip
def create_delivery(data: DeliveryCreate, deliveries: Deliveries, response: Response) -> DeliveryDetail:
    created = deliveries.create(data)
    response.headers["Location"] = f"deliveries/{created.id}"
    return created


@router.post(
    "/deliveries/{deliveryId}/confirm", summary="Record that the customer received the goods",
    dependencies=[CAN_DELIVER], responses=ACTION_RESPONSES,
)  # fmt: skip
def confirm_delivery(delivery_id: DeliveryId, data: DeliveryConfirm, deliveries: Deliveries) -> DeliveryDetail:
    return deliveries.confirm(delivery_id, data)


@router.post(
    "/deliveries/{deliveryId}/cancel", summary="Cancel a delivery not invoiced yet (stock goes back to its batches)",
    dependencies=[CAN_DELIVER], responses=ACTION_RESPONSES,
)  # fmt: skip
def cancel_delivery(delivery_id: DeliveryId, data: DeliveryCancel, deliveries: Deliveries) -> DeliveryDetail:
    return deliveries.cancel(delivery_id, data)


@router.get(
    "/uninvoiced-delivery-lines", summary="Delivered lines of a customer not invoiced yet", dependencies=[CAN_INVOICE]
)
def list_uninvoiced_delivery_lines(
    query: Annotated[UninvoicedDeliveryQuery, Query()], deliveries: Deliveries
) -> list[UninvoicedDeliveryLine]:
    return deliveries.uninvoiced(query)


# ---------------------------------------------------------------- invoices


@router.get("/invoices", summary="Sales invoices with what is outstanding", dependencies=[CAN_SEE_MONEY])
def list_sales_invoices(query: Annotated[SalesInvoiceQuery, Query()], accounts: Accounts) -> Page[SalesInvoiceListItem]:
    return accounts.invoices(query)


@router.get(
    "/invoices/{invoiceId}", summary="One sales invoice with its allocations", dependencies=[CAN_SEE_MONEY],
    responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def get_sales_invoice(invoice_id: InvoiceId, accounts: Accounts) -> SalesInvoiceDetail:
    return accounts.invoice(invoice_id)


@router.post(
    "/invoices", summary="Invoice deliveries, or invoice directly (direct stock lines take stock)",
    status_code=201, dependencies=[CAN_INVOICE], responses=POSTING_RESPONSES,
)  # fmt: skip
def create_sales_invoice(data: SalesInvoiceCreate, accounts: Accounts, response: Response) -> SalesInvoiceDetail:
    created = accounts.create_invoice(data)
    response.headers["Location"] = f"invoices/{created.id}"
    return created


@router.post(
    "/invoices/{invoiceId}/cancel", summary="Cancel an invoice (allocations, quantities and stock are reversed)",
    dependencies=[CAN_CANCEL_INVOICE], responses=ACTION_RESPONSES,
)  # fmt: skip
def cancel_sales_invoice(invoice_id: InvoiceId, data: SalesInvoiceCancel, accounts: Accounts) -> SalesInvoiceDetail:
    return accounts.cancel_invoice(invoice_id, data)


# ---------------------------------------------------------------- receipts


@router.get("/receipts", summary="Customer receipts and order advances", dependencies=[CAN_SEE_MONEY])
def list_receipts(query: Annotated[ReceiptQuery, Query()], accounts: Accounts) -> Page[ReceiptListItem]:
    return accounts.receipts(query)


@router.get(
    "/receipts/{receiptId}", summary="One receipt with its allocations", dependencies=[CAN_SEE_MONEY],
    responses=NOT_FOUND_RESPONSE,
)  # fmt: skip
def get_receipt(receipt_id: Annotated[int, Path(alias="receiptId", gt=0)], accounts: Accounts) -> ReceiptDetail:
    return accounts.receipt(receipt_id)


@router.post(
    "/receipts", summary="Record a receipt or order advance, optionally allocated to invoices", status_code=201,
    dependencies=[CAN_RECEIVE], responses=POSTING_RESPONSES,
)  # fmt: skip
def create_receipt(data: ReceiptCreate, accounts: Accounts, response: Response) -> ReceiptDetail:
    created = accounts.create_receipt(data)
    response.headers["Location"] = f"receipts/{created.id}"
    return created


# ---------------------------------------------------------------- allocations


@router.get("/allocations", summary="Customer allocation inquiry, newest first", dependencies=[CAN_SEE_MONEY])
def list_customer_allocations(
    query: Annotated[CustomerAllocationQuery, Query()], accounts: Accounts
) -> Page[CustomerAllocationOut]:
    return accounts.allocations(query)


@router.post(
    "/allocations", summary="Set a receipt against invoices", status_code=201, dependencies=[CAN_ALLOCATE],
    responses=POSTING_RESPONSES,
)  # fmt: skip
def create_customer_allocations(data: CustomerAllocationCreate, accounts: Accounts) -> list[CustomerAllocationOut]:
    return accounts.allocate(data)


@router.post(
    "/allocations/{allocationId}/reverse", summary="Reverse a customer allocation (kept in the history)",
    dependencies=[CAN_REVERSE], responses=ACTION_RESPONSES,
)  # fmt: skip
def reverse_customer_allocation(
    allocation_id: Annotated[int, Path(alias="allocationId", gt=0)], data: CustomerAllocationReverse, accounts: Accounts
) -> CustomerAllocationOut:
    return accounts.reverse(allocation_id, data)
