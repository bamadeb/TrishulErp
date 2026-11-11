r"""Sales orders: create (directly or from an accepted quotation), change while a draft, send for approval,
approve (with the credit check) or send back, close or cancel.

    Draft --submit--> Pending approval --approve--> Approved --delivery--> Part delivered --> Delivered
                       \--reject--> Draft                       --invoice--> Part invoiced --> Invoiced
    Draft / Pending approval / Approved (nothing delivered) --cancel--> Cancelled
    Approved .. Part invoiced --close--> Closed (the rest won't be delivered)

Delivered quantities come from delivery notes, invoiced quantities from invoices; the status follows them
(refresh_status). A prepaid order takes advances (receipts of type 'Order advance'); invoices of the
order use them up (allocations), so the order shows what was received, adjusted and is left.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import Conflict, NotFound
from trishul_api.common.numbering import next_document_no
from trishul_api.common.paging import order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Branch,
    Company,
    Customer,
    CustomerAllocation,
    CustomerSite,
    DeliveryNote,
    Item,
    PaymentTerms,
    Principal,
    Quotation,
    Receipt,
    SalesInvoice,
    SalesInvoiceLine,
    SalesOrder,
    SalesOrderLine,
    State,
    Uom,
)
from trishul_api.modules.inv.common import now, visible_branch
from trishul_api.modules.sal.common import (
    ORDER_CLOSE,
    ZERO,
    active_branch,
    active_customer,
    active_principal,
    addresses,
    credit_check,
    customer_balance,
    customer_branch,
    enforce_credit,
    err,
    is_inter_state,
    money,
    place_of_supply,
    require,
)
from trishul_api.modules.sal.lines import ItemLineIn, net_price, price_lines
from trishul_api.modules.sal.order_schemas import (
    OrderApprove,
    OrderCreate,
    OrderDetail,
    OrderDocument,
    OrderLineOut,
    OrderListItem,
    OrderNote,
    OrderQuery,
    OutstandingOrderLine,
    OutstandingOrderQuery,
)

#: An order goods may still go out against.
OPEN_FOR_DELIVERY = ("Approved", "Part delivered", "Part invoiced", "Delivered", "Invoiced")
NOT_STARTED = ("Draft", "Pending approval")
FINAL = ("Closed", "Cancelled")


def refresh_status(db: Session, order: SalesOrder) -> None:
    """Status from the lines' delivered and invoiced quantities (draft, closed and cancelled orders keep theirs)."""
    if order.status in (*NOT_STARTED, *FINAL):
        return
    lines = db.scalars(select(SalesOrderLine).where(SalesOrderLine.sales_order_id == order.id)).all()
    if lines and all(line.qty_invoiced >= line.quantity for line in lines):
        order.status = "Invoiced"
    elif any(line.qty_invoiced > 0 for line in lines):
        order.status = "Part invoiced"
    elif lines and all(line.qty_delivered >= line.quantity for line in lines):
        order.status = "Delivered"
    elif any(line.qty_delivered > 0 for line in lines):
        order.status = "Part delivered"
    else:
        order.status = "Approved"


def order_advances(db: Session, order_id: int) -> tuple[Decimal, Decimal]:
    """(received, adjusted) on the order's advance receipts."""
    received = db.scalar(
        select(func.coalesce(func.sum(Receipt.amount), 0)).where(
            Receipt.sales_order_id == order_id, Receipt.status == "Posted"
        )
    )
    adjusted = db.scalar(
        select(func.coalesce(func.sum(CustomerAllocation.amount), 0))
        .join(Receipt, Receipt.id == CustomerAllocation.receipt_id)
        .where(Receipt.sales_order_id == order_id, Receipt.status == "Posted", CustomerAllocation.is_active)
    )
    return Decimal(received or 0), Decimal(adjusted or 0)


class SalesOrderService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ list and detail

    def _select(self) -> Select[*tuple[Any, ...]]:
        totals = (
            select(
                SalesOrderLine.sales_order_id,
                func.sum(SalesOrderLine.quantity).label("qty_ordered"),
                func.sum(SalesOrderLine.qty_delivered).label("qty_delivered"),
                func.sum(SalesOrderLine.qty_invoiced).label("qty_invoiced"),
            )
            .group_by(SalesOrderLine.sales_order_id)
            .subquery()
        )
        return (
            select(
                SalesOrder.id,
                SalesOrder.order_no,
                SalesOrder.order_date,
                SalesOrder.expected_delivery_date,
                SalesOrder.customer_id,
                Customer.name.label("customer_name"),
                CustomerSite.site_name.label("customer_site_name"),
                SalesOrder.branch_id,
                Branch.name.label("branch_name"),
                Principal.name.label("principal_name"),
                SalesOrder.customer_po_no,
                SalesOrder.status,
                SalesOrder.is_prepaid,
                SalesOrder.total,
                SalesOrder.advance_received,
                func.coalesce(totals.c.qty_ordered, 0).label("qty_ordered"),
                func.coalesce(totals.c.qty_delivered, 0).label("qty_delivered"),
                func.coalesce(totals.c.qty_invoiced, 0).label("qty_invoiced"),
                SalesOrder.created_at,
            )
            .join(Customer, Customer.id == SalesOrder.customer_id)
            .join(Branch, Branch.id == SalesOrder.branch_id)
            .join(Principal, Principal.id == SalesOrder.principal_id)
            .outerjoin(CustomerSite, CustomerSite.id == SalesOrder.customer_site_id)
            .outerjoin(totals, totals.c.sales_order_id == SalesOrder.id)
            .where(visible_branch(self._actor), *self._brands())
        )

    def _brands(self) -> list[Any]:
        if self._actor.principal_ids is None:
            return []
        return [SalesOrder.principal_id.in_(self._actor.principal_ids)]

    def search(self, query: OrderQuery) -> Page[OrderListItem]:
        statement = self._select()
        if query.status is not None:
            statement = statement.where(SalesOrder.status == query.status)
        if query.customer_id is not None:
            statement = statement.where(SalesOrder.customer_id == query.customer_id)
        if query.branch_id is not None:
            statement = statement.where(SalesOrder.branch_id == query.branch_id)
        if query.from_date is not None:
            statement = statement.where(SalesOrder.order_date >= query.from_date)
        if query.to_date is not None:
            statement = statement.where(SalesOrder.order_date <= query.to_date)
        if query.prepaid_only:
            statement = statement.where(SalesOrder.is_prepaid)
        if query.item_id is not None:
            statement = statement.where(
                exists().where(SalesOrderLine.sales_order_id == SalesOrder.id, SalesOrderLine.item_id == query.item_id)
            )
        if query.outstanding_only:
            statement = statement.where(
                SalesOrder.status.in_(OPEN_FOR_DELIVERY),
                exists().where(
                    SalesOrderLine.sales_order_id == SalesOrder.id,
                    SalesOrderLine.qty_delivered < SalesOrderLine.quantity,
                ),
            )
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    SalesOrder.order_no.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                    SalesOrder.customer_po_no.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {
                "orderDate": SalesOrder.order_date,
                "orderNo": SalesOrder.order_no,
                "customerName": Customer.name,
                "total": SalesOrder.total,
                "expectedDeliveryDate": SalesOrder.expected_delivery_date,
            },
            default="-orderDate",
            tiebreaker=SalesOrder.id.desc(),
        )
        return paginate(self._db, statement, query, OrderListItem)

    def get(self, order_id: int) -> OrderDetail:
        order = self._visible(order_id)
        created, submitted, approved, closed, credit = (aliased(AppUser) for _ in range(5))
        header = (
            self._db.execute(
                self._select()
                .add_columns(
                    SalesOrder.principal_id,
                    SalesOrder.customer_site_id,
                    SalesOrder.quotation_id,
                    Quotation.quotation_no,
                    Company.legal_name.label("company_name"),
                    Company.address.label("company_address"),
                    Branch.address.label("branch_address"),
                    Customer.code.label("customer_code"),
                    Customer.gstin.label("customer_gstin"),
                    Customer.primary_phone.label("customer_phone"),
                    SalesOrder.bill_to_address,
                    SalesOrder.ship_to_address,
                    State.name.label("place_of_supply"),
                    SalesOrder.customer_po_date,
                    SalesOrder.payment_terms_id,
                    PaymentTerms.description.label("payment_terms"),
                    SalesOrder.subtotal,
                    SalesOrder.cgst,
                    SalesOrder.sgst,
                    SalesOrder.igst,
                    SalesOrder.tax_total,
                    SalesOrder.other_charges,
                    SalesOrder.remarks,
                    SalesOrder.credit_check_status,
                    credit.username.label("credit_approved_by"),
                    created.username.label("created_by"),
                    submitted.username.label("submitted_by"),
                    SalesOrder.submitted_at,
                    approved.username.label("approved_by"),
                    SalesOrder.approved_at,
                    SalesOrder.approval_note,
                    closed.username.label("closed_by"),
                    SalesOrder.closed_at,
                    SalesOrder.close_reason,
                    SalesOrder.row_version,
                )
                .join(Company, Company.id == Branch.company_id)
                .outerjoin(Quotation, Quotation.id == SalesOrder.quotation_id)
                .outerjoin(State, State.id == SalesOrder.place_of_supply_state_id)
                .outerjoin(PaymentTerms, PaymentTerms.id == SalesOrder.payment_terms_id)
                .outerjoin(credit, credit.id == SalesOrder.credit_approved_by_user_id)
                .outerjoin(created, created.id == SalesOrder.created_by_user_id)
                .outerjoin(submitted, submitted.id == SalesOrder.submitted_by_user_id)
                .outerjoin(approved, approved.id == SalesOrder.approved_by_user_id)
                .outerjoin(closed, closed.id == SalesOrder.closed_by_user_id)
                .where(SalesOrder.id == order.id)
            )
            .mappings()
            .one()
        )
        lines = [
            OrderLineOut(
                id=line.id,
                line_no=line.line_no,
                item_id=line.item_id,
                item_code=code,
                description=line.description or description,
                uom_code=uom,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount_pct=line.discount_pct,
                gst_pct=line.gst_pct,
                net_price=net_price(line.unit_price, line.discount_pct),
                taxable_value=line.taxable_value,
                tax_amount=line.tax_amount,
                line_total=line.line_total,
                qty_delivered=line.qty_delivered,
                qty_invoiced=line.qty_invoiced,
                qty_to_deliver=max(line.quantity - line.qty_delivered, ZERO),
            )
            for line, code, description, uom in self._db.execute(
                select(SalesOrderLine, Item.item_code, Item.description, Uom.code)
                .join(Item, Item.id == SalesOrderLine.item_id)
                .outerjoin(Uom, Uom.id == SalesOrderLine.uom_id)
                .where(SalesOrderLine.sales_order_id == order.id)
                .order_by(SalesOrderLine.line_no)
            ).all()
        ]
        deliveries = [
            OrderDocument(id=i, number=n, date=d, amount=None, status=s)
            for i, n, d, s in self._db.execute(
                select(DeliveryNote.id, DeliveryNote.delivery_no, DeliveryNote.delivery_date, DeliveryNote.status)
                .where(DeliveryNote.sales_order_id == order.id)
                .order_by(DeliveryNote.delivery_date, DeliveryNote.id)
            ).all()
        ]
        invoice_rows = self._db.execute(
            select(SalesInvoice.id, SalesInvoice.invoice_no, SalesInvoice.invoice_date, SalesInvoice.total,
                   SalesInvoice.status)
            .where(
                or_(
                    SalesInvoice.sales_order_id == order.id,
                    exists().where(
                        SalesInvoiceLine.sales_invoice_id == SalesInvoice.id,
                        SalesInvoiceLine.sales_order_line_id.in_(
                            select(SalesOrderLine.id).where(SalesOrderLine.sales_order_id == order.id)
                        ),
                    ),
                )
            )
            .order_by(SalesInvoice.invoice_date, SalesInvoice.id)
        ).all()  # fmt: skip
        invoices = [OrderDocument(id=i, number=n, date=d, amount=t, status=s) for i, n, d, t, s in invoice_rows]
        invoiced_amount = Decimal(
            self._db.scalar(
                select(func.coalesce(func.sum(SalesInvoiceLine.line_total), 0))
                .join(SalesInvoice, SalesInvoice.id == SalesInvoiceLine.sales_invoice_id)
                .join(SalesOrderLine, SalesOrderLine.id == SalesInvoiceLine.sales_order_line_id)
                .where(SalesOrderLine.sales_order_id == order.id, SalesInvoice.status != "Cancelled")
            )
            or 0
        )
        advances = [
            OrderDocument(id=i, number=n, date=d, amount=a, status=s)
            for i, n, d, a, s in self._db.execute(
                select(Receipt.id, Receipt.receipt_no, Receipt.receipt_date, Receipt.amount, Receipt.status)
                .where(Receipt.sales_order_id == order.id)
                .order_by(Receipt.receipt_date, Receipt.id)
            ).all()
        ]
        received, adjusted = order_advances(self._db, order.id)
        customer = self._db.get(Customer, order.customer_id)
        assert customer is not None
        return OrderDetail.model_validate(
            {
                **header,
                "lines": lines,
                "deliveries": deliveries,
                "invoices": invoices,
                "advances": advances,
                "invoiced_amount": invoiced_amount,
                "advance_adjusted": adjusted,
                "advance_remaining": received - adjusted,
                "customer_balance": customer_balance(self._db, customer),
                "credit_limit": customer.credit_limit,
            }
        )

    def outstanding(self, query: OutstandingOrderQuery) -> Page[OutstandingOrderLine]:
        pending = SalesOrderLine.quantity - SalesOrderLine.qty_delivered
        price = SalesOrderLine.unit_price * (100 - SalesOrderLine.discount_pct) / 100
        statement: Select[*tuple[Any, ...]] = (
            select(
                SalesOrder.id.label("sales_order_id"),
                SalesOrder.order_no,
                SalesOrder.order_date,
                SalesOrder.expected_delivery_date,
                SalesOrder.status,
                SalesOrder.customer_id,
                Customer.name.label("customer_name"),
                Branch.name.label("branch_name"),
                SalesOrderLine.id.label("line_id"),
                SalesOrderLine.item_id,
                Item.item_code,
                func.coalesce(SalesOrderLine.description, Item.description).label("description"),
                Uom.code.label("uom_code"),
                SalesOrderLine.quantity.label("qty_ordered"),
                SalesOrderLine.qty_delivered,
                pending.label("qty_to_deliver"),
                price.label("net_price"),
                (pending * price).label("pending_value"),
            )
            .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
            .join(Customer, Customer.id == SalesOrder.customer_id)
            .join(Branch, Branch.id == SalesOrder.branch_id)
            .join(Item, Item.id == SalesOrderLine.item_id)
            .outerjoin(Uom, Uom.id == SalesOrderLine.uom_id)
            .where(SalesOrder.status.in_(OPEN_FOR_DELIVERY), pending > 0, visible_branch(self._actor), *self._brands())
        )
        if query.customer_id is not None:
            statement = statement.where(SalesOrder.customer_id == query.customer_id)
        if query.branch_id is not None:
            statement = statement.where(SalesOrder.branch_id == query.branch_id)
        if query.item_id is not None:
            statement = statement.where(SalesOrderLine.item_id == query.item_id)
        if query.sales_order_id is not None:
            statement = statement.where(SalesOrder.id == query.sales_order_id)
        if query.overdue_only:
            statement = statement.where(SalesOrder.expected_delivery_date < date.today())
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    SalesOrder.order_no.contains(term, autoescape=True),
                    Item.item_code.contains(term, autoescape=True),
                    Item.description.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {
                "orderDate": SalesOrder.order_date,
                "expectedDeliveryDate": SalesOrder.expected_delivery_date,
                "itemCode": Item.item_code,
            },
            default="orderDate",
            tiebreaker=SalesOrderLine.id.asc(),
        )
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = (
            self._db.execute(statement.offset((query.page - 1) * query.page_size).limit(query.page_size))
            .mappings()
            .all()
        )
        today = date.today()
        items = [
            OutstandingOrderLine.model_validate(
                {
                    **r,
                    "net_price": Decimal(r["net_price"]).quantize(Decimal("0.0001")),
                    "pending_value": money(Decimal(r["pending_value"])),
                    "days_open": (today - r["order_date"]).days,
                }
            )
            for r in rows
        ]
        return Page(items=items, total=total, page=query.page, page_size=query.page_size)

    # ------------------------------------------------------------------ create and change

    def create(self, data: OrderCreate, quotation_id: int | None = None) -> OrderDetail:
        branch = active_branch(self._db, self._actor, data.branch_id)
        order = SalesOrder(
            order_no=next_document_no(
                self._db, company_id=branch.company_id, document_type="SALES_ORDER", branch_id=branch.id
            ),
            branch_id=branch.id,
            quotation_id=quotation_id,
            status="Draft",
            finance_mode="Cash",
            credit_check_status="Not checked",
            advance_received=ZERO,
            subtotal=ZERO,
            tax_total=ZERO,
            total=ZERO,
            created_by_user_id=self._actor.id,
        )
        self._fill(order, data)
        self._db.add(order)
        self._db.flush()
        self._replace_lines(order, data.lines)
        self._commit()
        return self.get(order.id)

    def update(self, order_id: int, expected: bytes, data: OrderCreate) -> OrderDetail:
        """Replaces the whole order (header and lines). Only a draft can change."""
        order = self._visible(order_id)
        check_row_version(order.row_version, expected)
        if order.status != "Draft":
            raise Conflict(f"Only a draft order can be changed; this one is {order.status.lower()}.")
        if data.branch_id != order.branch_id:
            raise err("branchId", "The branch can't change (the order number belongs to it).")
        self._fill(order, data)
        self._replace_lines(order, data.lines)
        order.updated_at = now()
        order.updated_by_user_id = self._actor.id
        self._commit()
        return self.get(order.id)

    def _fill(self, order: SalesOrder, data: OrderCreate) -> None:
        principal = active_principal(self._db, self._actor, data.principal_id)
        customer = active_customer(self._db, data.customer_id)
        site = customer_branch(self._db, customer, data.customer_site_id)
        if data.payment_terms_id is not None and self._db.get(PaymentTerms, data.payment_terms_id) is None:
            raise err("paymentTermsId", "Choose payment terms from the list.")
        order_date = data.order_date or date.today()
        if data.expected_delivery_date is not None and data.expected_delivery_date < order_date:
            raise err("expectedDeliveryDate", "The expected delivery date is before the order date.")
        billing, delivery = addresses(customer, site)
        order.principal_id = principal.id
        order.customer_id = customer.id
        order.customer_site_id = site.id if site else None
        order.delivery_site_id = site.id if site else None
        order.order_date = order_date
        order.customer_po_no = data.customer_po_no
        order.customer_po_date = data.customer_po_date
        order.expected_delivery_date = data.expected_delivery_date
        order.payment_terms_id = data.payment_terms_id or customer.payment_terms_id
        order.bill_to_address = data.bill_to_address or billing
        order.ship_to_address = data.ship_to_address or delivery
        order.place_of_supply_state_id = place_of_supply(self._db, customer, site, order.branch_id)
        order.salesperson_employee_id = order.salesperson_employee_id or customer.salesman_employee_id
        order.is_prepaid = data.is_prepaid
        order.other_charges = data.other_charges
        order.remarks = data.remarks

    def _replace_lines(self, order: SalesOrder, lines: list[ItemLineIn]) -> None:
        old = self._db.scalars(select(SalesOrderLine).where(SalesOrderLine.sales_order_id == order.id)).all()
        for line in old:
            self._db.delete(line)
        self._db.flush()
        inter_state = is_inter_state(self._db, order.branch_id, order.place_of_supply_state_id or 0)
        totals = price_lines(self._db, self._actor, list(lines), order.principal_id, inter_state=inter_state)
        for number, priced in enumerate(totals.lines, start=1):
            assert priced.item is not None
            self._db.add(
                SalesOrderLine(
                    sales_order_id=order.id,
                    line_no=number * 10,
                    item_id=priced.item.id,
                    description=priced.description,
                    quantity=priced.quantity,
                    uom_id=priced.item.uom_id,
                    unit_price=priced.unit_price,
                    discount_pct=priced.discount_pct,
                    discount_amount=priced.discount,
                    gst_pct=priced.gst_pct,
                    hsn_sac_id=priced.item.hsn_sac_id,
                    taxable_value=priced.taxable,
                    tax_amount=priced.tax,
                    line_total=priced.total,
                    qty_delivered=ZERO,
                    qty_invoiced=ZERO,
                    created_by_user_id=self._actor.id,
                )
            )
        order.subtotal = totals.taxable
        order.tax_total = totals.tax
        order.cgst, order.sgst, order.igst = totals.cgst, totals.sgst, totals.igst
        order.total = totals.total(order.other_charges)

    # ------------------------------------------------------------------ workflow

    def submit(self, order_id: int) -> OrderDetail:
        order = self._visible(order_id)
        self._expect(order, ("Draft",), "sent for approval")
        order.status = "Pending approval"
        order.submitted_at = now()
        order.submitted_by_user_id = self._actor.id
        return self._touch(order)

    def approve(self, order_id: int, data: OrderApprove) -> OrderDetail:
        order = self._visible(order_id)
        self._expect(order, ("Pending approval",), "approved")
        customer = self._db.get(Customer, order.customer_id)
        assert customer is not None
        overridden = enforce_credit(self._actor, credit_check(self._db, customer, order.total), data.override_credit)
        order.credit_check_status = "Approved override" if overridden else "Within limit"
        if overridden:
            order.credit_approved_by_user_id = self._actor.id
            order.credit_approved_at = now()
        order.status = "Approved"
        order.approved_at = now()
        order.approved_by_user_id = self._actor.id
        order.approval_note = data.note
        return self._touch(order)

    def reject(self, order_id: int, data: OrderNote) -> OrderDetail:
        order = self._visible(order_id)
        self._expect(order, ("Pending approval",), "sent back")
        if not data.note:
            raise err("note", "Say why the order is sent back.")
        order.status = "Draft"
        order.approval_note = f"Sent back: {data.note}"
        return self._touch(order)

    def close(self, order_id: int, data: OrderNote) -> OrderDetail:
        """The rest of the order will not be delivered: no more deliveries against it."""
        require(self._actor, ORDER_CLOSE)
        order = self._visible(order_id)
        self._expect(order, ("Approved", "Part delivered", "Delivered", "Part invoiced"), "closed")
        if not data.note:
            raise err("note", "Say why the order is closed.")
        order.status = "Closed"
        order.closed_at = now()
        order.closed_by_user_id = self._actor.id
        order.close_reason = data.note
        return self._touch(order)

    def cancel(self, order_id: int, data: OrderNote) -> OrderDetail:
        """Only an order nothing was delivered or invoiced against; otherwise close it."""
        order = self._visible(order_id)
        self._expect(order, ("Draft", "Pending approval", "Approved"), "cancelled")
        if order.status != "Draft":
            require(self._actor, ORDER_CLOSE)
        delivered = self._db.scalar(
            select(func.coalesce(func.sum(SalesOrderLine.qty_delivered + SalesOrderLine.qty_invoiced), 0)).where(
                SalesOrderLine.sales_order_id == order.id
            )
        )
        if delivered:
            raise Conflict("Goods have gone out against this order; close it instead.")
        received, adjusted = order_advances(self._db, order.id)
        if received - adjusted > 0:
            raise Conflict("An advance is held against this order; refund or re-allocate it first.")
        if not data.note:
            raise err("note", "Say why the order is cancelled.")
        order.status = "Cancelled"
        order.closed_at = now()
        order.closed_by_user_id = self._actor.id
        order.close_reason = data.note
        return self._touch(order)

    # ------------------------------------------------------------------ helpers

    def _visible(self, order_id: int) -> SalesOrder:
        order = self._db.get(SalesOrder, order_id)
        if (
            order is None
            or not self._actor.can_use_branch(order.branch_id)
            or not self._actor.can_see_principal(order.principal_id)
        ):
            raise NotFound("Sales order not found.")
        return order

    @staticmethod
    def _expect(order: SalesOrder, statuses: tuple[str, ...], action: str) -> None:
        if order.status not in statuses:
            raise Conflict(f"Order {order.order_no} is {order.status.lower()}, so it can't be {action}.")

    def _touch(self, order: SalesOrder) -> OrderDetail:
        order.updated_at = now()
        order.updated_by_user_id = self._actor.id
        self._commit()
        return self.get(order.id)

    def _commit(self) -> None:
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise Conflict("The order could not be saved; someone else changed it. Reload and try again.") from error
