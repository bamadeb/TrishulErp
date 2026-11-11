"""Customer accounts: sales invoices, receipts (order advances, on-account, against invoices), allocations.

Invoices
  * Against delivery lines (sal.invoice.manage): no more than delivered and not yet invoiced on each line
    (delivery_note_line.qty_invoiced), several deliveries of one customer, brand and branch on one invoice,
    part of a delivery is fine. A delivery-based invoice never moves stock: the delivery did.
  * Direct lines (sal.invoice.direct): an item or a description. A direct stock item is taken out of stock
    by the invoice itself, from its location: this is the only other way stock leaves, so it can't go twice.
  * Numbers: SALES_INVOICE series of the branch, at most 16 characters (GST). Totals: taxable + GST
    (CGST/SGST or IGST by place of supply) + other charges, rounded to the rupee (round_off recorded).
  * Credit: an invoice not fully covered by credit-approved orders is checked against the credit limit.
  * Advances: receipts of type 'Order advance' for the orders billed are set against the new invoice at
    once (adjust_advances), never beyond what each receipt has left, so an advance is used only once.
  * Cancelling reverses it all through new records: allocations are reversed (kept), delivered quantities
    become invoiceable again, stock taken by a direct invoice goes back to its batches.
Receipts reduce the balance at once; allocations record which invoices they settle and are never deleted.
"""

from collections import defaultdict
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import AlreadyExists, Conflict, Forbidden, NotFound
from trishul_api.common.numbering import GST_DOCUMENT_NO_MAX_LENGTH, next_document_no
from trishul_api.common.paging import order_by_sort
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Branch,
    Company,
    Customer,
    CustomerAllocation,
    CustomerSite,
    DeliveryNote,
    DeliveryNoteLine,
    GstinRegistration,
    HsnSac,
    Item,
    Location,
    PaymentTerms,
    Principal,
    Receipt,
    SalesInvoice,
    SalesInvoiceLine,
    SalesOrder,
    SalesOrderLine,
    State,
    Uom,
)
from trishul_api.modules.inv.common import company_of_branch, now, rack_of, stock_location
from trishul_api.modules.inv.ledger import Source, StockLedger
from trishul_api.modules.pur.words import rupees_in_words
from trishul_api.modules.sal.account_schemas import (
    CustomerAllocationCreate,
    CustomerAllocationIn,
    CustomerAllocationOut,
    CustomerAllocationQuery,
    CustomerAllocationReverse,
    ReceiptCreate,
    ReceiptDetail,
    ReceiptListItem,
    ReceiptQuery,
    SalesAccountQuery,
    SalesInvoiceCancel,
    SalesInvoiceCreate,
    SalesInvoiceDetail,
    SalesInvoiceLineOut,
    SalesInvoiceListItem,
    SalesInvoiceQuery,
    SalesInvoiceState,
)
from trishul_api.modules.sal.common import (
    ALLOCATION_REVERSE,
    INVOICE_CANCEL,
    INVOICE_DIRECT,
    INVOICE_MANAGE,
    ZERO,
    active_branch,
    active_customer,
    active_principal,
    addresses,
    allocated_to_invoice,
    credit_check,
    customer_branch,
    enforce_credit,
    err,
    is_inter_state,
    money,
    place_of_supply,
    qty_text,
    require,
    rupees,
    sale_item,
)
from trishul_api.modules.sal.lines import Priced, price_line, total_up
from trishul_api.modules.sal.order_service import refresh_status
from trishul_api.modules.sal.stock import put_back, take_for_sale

OPEN = ("Posted", "Part paid")
DOCUMENT = "SALES_INVOICE"
CREDIT_APPROVED = ("Within limit", "Approved override")


def _allocated(column: Any, correlate: Any) -> Any:
    return (
        select(func.coalesce(func.sum(CustomerAllocation.amount), 0))
        .where(column == correlate.id, CustomerAllocation.is_active)
        .correlate(correlate)
        .scalar_subquery()
    )


def invoice_state(status: str, due: date | None, outstanding: Decimal, today: date) -> SalesInvoiceState:
    if status == "Cancelled":
        return "Cancelled"
    if outstanding <= 0:
        return "Paid"
    if due is not None and due < today:
        return "Overdue"
    return "Partially paid" if status == "Part paid" else "Unpaid"


class _Line:
    """One invoice line being prepared."""

    def __init__(self, priced: Priced, delivery_line: DeliveryNoteLine | None, order_line: SalesOrderLine | None,
                 bin_id: int | None, lot_id: int | None) -> None:  # fmt: skip
        self.priced = priced
        self.delivery_line = delivery_line
        self.order_line = order_line
        self.bin_id = bin_id
        self.lot_id = lot_id


class SalesAccountService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ================================================================ invoices

    def create_invoice(self, data: SalesInvoiceCreate) -> SalesInvoiceDetail:
        customer = active_customer(self._db, data.customer_id)
        invoice_date = data.invoice_date or date.today()
        if invoice_date > date.today():
            raise err("invoiceDate", "The invoice date can't be in the future.")

        billed: dict[int, Decimal] = defaultdict(lambda: ZERO)
        prepared: list[tuple[int, Any, DeliveryNoteLine | None, DeliveryNote | None]] = []
        principals: set[int] = set()
        branches: set[int] = set()
        sites: set[int | None] = set()
        for index, line in enumerate(data.lines):
            field = f"lines[{index}]"
            if line.delivery_note_line_id is None:
                prepared.append((index, line, None, None))
                continue
            require(self._actor, INVOICE_MANAGE, "Invoicing deliveries needs the invoice permission.")
            delivery_line = self._db.get(DeliveryNoteLine, line.delivery_note_line_id)
            note = self._db.get(DeliveryNote, delivery_line.delivery_note_id) if delivery_line else None
            if delivery_line is None or note is None or note.customer_id != customer.id or note.status not in (
                "Dispatched", "Delivered"
            ):  # fmt: skip
                raise err(f"{field}.deliveryNoteLineId", "That delivery line is not a live delivery of this customer.")
            if delivery_note_date_after(note, invoice_date):
                raise err("invoiceDate", f"The invoice date is before delivery {note.delivery_no}.")
            left = delivery_line.quantity - delivery_line.qty_invoiced - billed[delivery_line.id]
            if line.quantity > left:
                raise err(
                    f"{field}.quantity", f"Only {qty_text(max(left, ZERO))} of that delivery line is left to invoice."
                )
            billed[delivery_line.id] += line.quantity
            principals.add(note.principal_id)
            branches.add(note.branch_id)
            sites.add(note.customer_site_id)
            prepared.append((index, line, delivery_line, note))
        direct = any(d is None for _, _, d, _ in prepared)
        if direct:
            require(self._actor, INVOICE_DIRECT, "Invoicing without a delivery needs the direct invoice permission.")

        if len(principals) > 1:
            raise err("lines", "The deliveries are of different brands; one invoice is for one brand.")
        if len(branches) > 1:
            raise err("lines", "The deliveries are from different branches; invoice them separately.")
        principal_id = data.principal_id or (next(iter(principals)) if principals else None)
        branch_id = data.branch_id or (next(iter(branches)) if branches else None)
        if principal_id is None:
            raise err("principalId", "Choose the brand.")
        if branch_id is None:
            raise err("branchId", "Choose the branch the invoice is raised from.")
        if principals and principal_id not in principals:
            raise err("principalId", "The deliveries are of another brand.")
        if branches and branch_id not in branches:
            raise err("branchId", "The deliveries belong to another branch.")
        principal = active_principal(self._db, self._actor, principal_id)
        branch = active_branch(self._db, self._actor, branch_id)
        site_id = data.customer_site_id or (next(iter(sites)) if len(sites) == 1 else None)
        site = customer_branch(self._db, customer, site_id)
        supply_state = place_of_supply(self._db, customer, site, branch.id)
        inter_state = is_inter_state(self._db, branch.id, supply_state)

        location = None
        lines: list[_Line] = []
        order_ids: set[int] = set()
        for index, line, delivery_line, _ in prepared:
            field = f"lines[{index}]"
            order_line = None
            if delivery_line is not None:
                item = self._db.get(Item, delivery_line.item_id)
                description = delivery_line.description
                if delivery_line.sales_order_line_id:
                    order_line = self._db.get(SalesOrderLine, delivery_line.sales_order_line_id)
                    if order_line is not None:
                        order_ids.add(order_line.sales_order_id)
                bin_id = lot_id = None
            else:
                item = (
                    sale_item(self._db, self._actor, line.item_id, principal.id, f"{field}.itemId")
                    if line.item_id
                    else None
                )
                description = line.description
                bin_id, lot_id = line.bin_id, line.stock_lot_id
                if item is not None and item.item_type == "Stock":
                    if data.location_id is None:
                        raise err("locationId", "Say where the goods on the direct lines leave from.")
                    location = location or stock_location(self._db, self._actor, data.location_id)
                    bin_id = rack_of(self._db, location, line.bin_id, f"{field}.binId")
            priced = price_line(item, line.description or description, line.quantity, line.unit_price,
                                line.discount_pct, line.gst_pct)  # fmt: skip
            lines.append(_Line(priced, delivery_line, order_line, bin_id, lot_id))
        totals = total_up([entry.priced for entry in lines], inter_state=inter_state)
        raw = totals.total(data.other_charges)
        total = rupees(raw)

        # Credit: orders approved within (or over, by override) the limit were checked already.
        covered = not direct and all(
            entry.order_line is not None and self._order_credit_ok(entry.order_line.sales_order_id) for entry in lines
        )
        overridden = False
        if not covered:
            overridden = enforce_credit(
                self._actor, credit_check(self._db, customer, total, invoicing=True), data.override_credit
            )

        billing, delivery = addresses(customer, site)
        notes = {n.id for _, _, _, n in prepared if n is not None}
        invoice = SalesInvoice(
            invoice_no=next_document_no(
                self._db, company_id=branch.company_id, document_type="SALES_INVOICE", branch_id=branch.id,
                max_length=GST_DOCUMENT_NO_MAX_LENGTH,
            ),
            principal_id=principal.id,
            company_id=branch.company_id,
            branch_id=branch.id,
            gstin_registration_id=branch.gstin_registration_id,
            customer_id=customer.id,
            customer_site_id=site.id if site else None,
            ship_to_site_id=site.id if site else None,
            bill_to_address=data.bill_to_address or billing,
            ship_to_address=data.ship_to_address or delivery,
            place_of_supply_state_id=supply_state,
            invoice_type=data.invoice_type,
            source_type="Delivery" if notes else "Direct",
            sales_order_id=next(iter(order_ids)) if len(order_ids) == 1 else None,
            delivery_note_id=next(iter(notes)) if len(notes) == 1 else None,
            invoice_date=invoice_date,
            due_date=data.due_date or self._due_date(customer, order_ids, invoice_date),
            is_reverse_charge=False,
            taxable_value=totals.taxable,
            cgst=totals.cgst,
            sgst=totals.sgst,
            igst=totals.igst,
            cess=ZERO,
            other_charges=data.other_charges,
            round_off=total - raw,
            total=total,
            amount_received=ZERO,
            status="Posted",
            is_direct=direct,
            location_id=location.id if location else None,
            remarks=data.remarks,
            posted_by_user_id=self._actor.id,
            credit_override_by_user_id=self._actor.id if overridden else None,
            credit_override_at=now() if overridden else None,
            created_by_user_id=self._actor.id,
        )  # fmt: skip
        self._db.add(invoice)
        self._db.flush()
        ledger = (
            StockLedger(self._db, company_id=company_of_branch(self._db, location.branch_id), user_id=self._actor.id,
                        at=now())
            if location is not None else None
        )  # fmt: skip
        for number, entry in enumerate(lines, start=1):
            priced = entry.priced
            split = _line_split(priced.tax, inter_state)
            row = SalesInvoiceLine(
                sales_invoice_id=invoice.id,
                line_no=number * 10,
                item_id=priced.item.id if priced.item else None,
                sales_order_line_id=entry.order_line.id if entry.order_line else None,
                delivery_note_line_id=entry.delivery_line.id if entry.delivery_line else None,
                description=priced.description,
                hsn_sac_id=priced.item.hsn_sac_id if priced.item else None,
                quantity=priced.quantity,
                uom_id=priced.item.uom_id if priced.item else None,
                unit_price=priced.unit_price,
                discount_pct=priced.discount_pct,
                discount_amount=priced.discount,
                gst_pct=priced.gst_pct,
                taxable_value=priced.taxable,
                cgst_amount=split[0],
                sgst_amount=split[1],
                igst_amount=split[2],
                line_total=priced.total,
                unit_cost=entry.delivery_line.unit_cost if entry.delivery_line else None,
                bin_id=entry.bin_id,
                created_by_user_id=self._actor.id,
            )
            self._db.add(row)
            self._db.flush()
            if entry.delivery_line is not None:
                entry.delivery_line.qty_invoiced = entry.delivery_line.qty_invoiced + priced.quantity
                if entry.order_line is not None:
                    entry.order_line.qty_invoiced = entry.order_line.qty_invoiced + priced.quantity
            elif priced.item is not None and priced.item.item_type == "Stock":
                assert ledger is not None and location is not None
                row.unit_cost = take_for_sale(
                    ledger, item=priced.item, location=location, bin_id=entry.bin_id, quantity=priced.quantity,
                    lot_id=entry.lot_id, source=Source(DOCUMENT, invoice.id, invoice.invoice_no, row.id),
                )  # fmt: skip
        self._db.flush()
        for order_id in order_ids:
            order = self._db.get(SalesOrder, order_id)
            assert order is not None
            refresh_status(self._db, order)
        if data.adjust_advances and order_ids:
            self._adjust_advances(invoice, order_ids)
        self._commit("The invoice could not be saved; reload and try again.")
        return self.invoice(invoice.id)

    def _order_credit_ok(self, order_id: int) -> bool:
        status = self._db.scalar(select(SalesOrder.credit_check_status).where(SalesOrder.id == order_id))
        return status in CREDIT_APPROVED

    def _due_date(self, customer: Customer, order_ids: set[int], invoice_date: date) -> date | None:
        terms_id = customer.payment_terms_id
        if len(order_ids) == 1:
            terms_id = (
                self._db.scalar(select(SalesOrder.payment_terms_id).where(SalesOrder.id.in_(order_ids))) or terms_id
            )
        if terms_id is None:
            return None
        terms = self._db.get(PaymentTerms, terms_id)
        if terms is None or terms.days_before_due is None:
            return None
        return invoice_date + timedelta(days=terms.days_before_due)

    def _adjust_advances(self, invoice: SalesInvoice, order_ids: set[int]) -> None:
        """Uses up the orders' advance receipts against the invoice, oldest first."""
        outstanding = invoice.total - allocated_to_invoice(self._db, invoice.id)
        used = _allocated(CustomerAllocation.receipt_id, Receipt)
        rows = self._db.execute(
            select(Receipt, used)
            .where(Receipt.sales_order_id.in_(order_ids), Receipt.status == "Posted",
                   Receipt.customer_id == invoice.customer_id)
            .order_by(Receipt.receipt_date, Receipt.id)
            .with_hint(Receipt, "WITH (UPDLOCK, ROWLOCK)", "mssql")
        ).all()  # fmt: skip
        for receipt, done in rows:
            if outstanding <= 0:
                break
            amount = min(receipt.amount - Decimal(done or 0), outstanding)
            if amount <= 0:
                continue
            self._db.add(
                CustomerAllocation(
                    sales_invoice_id=invoice.id,
                    receipt_id=receipt.id,
                    amount=amount,
                    allocated_on=date.today(),
                    allocated_by_user_id=self._actor.id,
                    created_by_user_id=self._actor.id,
                )
            )
            outstanding -= amount
        self._db.flush()
        self._refresh_invoice(invoice.id)

    def cancel_invoice(self, invoice_id: int, data: SalesInvoiceCancel) -> SalesInvoiceDetail:
        require(self._actor, INVOICE_CANCEL, "Cancelling invoices needs the cancel permission.")
        invoice = self._visible_invoice(invoice_id)
        if invoice.status == "Cancelled":
            raise Conflict(f"Invoice {invoice.invoice_no} is already cancelled.")
        at = now()
        for allocation in self._db.scalars(
            select(CustomerAllocation).where(
                CustomerAllocation.sales_invoice_id == invoice.id, CustomerAllocation.is_active
            )
        ).all():
            allocation.is_active = False
            allocation.reversed_at = at
            allocation.reversed_by_user_id = self._actor.id
            allocation.reversal_reason = f"Invoice {invoice.invoice_no} cancelled: {data.reason}"
            allocation.updated_at = at
            allocation.updated_by_user_id = self._actor.id
        order_ids: set[int] = set()
        for line in self._db.scalars(
            select(SalesInvoiceLine).where(SalesInvoiceLine.sales_invoice_id == invoice.id)
        ).all():
            if line.delivery_note_line_id is not None:
                delivery_line = self._db.get(DeliveryNoteLine, line.delivery_note_line_id)
                assert delivery_line is not None
                delivery_line.qty_invoiced = max(delivery_line.qty_invoiced - line.quantity, ZERO)
                if line.sales_order_line_id is not None:
                    order_line = self._db.get(SalesOrderLine, line.sales_order_line_id)
                    assert order_line is not None
                    order_line.qty_invoiced = max(order_line.qty_invoiced - line.quantity, ZERO)
                    order_ids.add(order_line.sales_order_id)
        if invoice.location_id is not None:
            location = self._db.get(Location, invoice.location_id)
            assert location is not None
            ledger = StockLedger(self._db, company_id=company_of_branch(self._db, location.branch_id),
                                 user_id=self._actor.id, at=at)  # fmt: skip
            put_back(self._db, ledger, document_type=DOCUMENT, document_id=invoice.id, reference=invoice.invoice_no)
        invoice.status = "Cancelled"
        invoice.amount_received = ZERO
        invoice.cancelled_at = at
        invoice.cancelled_by_user_id = self._actor.id
        invoice.cancel_reason = data.reason
        invoice.updated_at = at
        invoice.updated_by_user_id = self._actor.id
        self._db.flush()
        for order_id in order_ids:
            order = self._db.get(SalesOrder, order_id)
            assert order is not None
            refresh_status(self._db, order)
        self._commit("The invoice could not be cancelled.")
        return self.invoice(invoice.id)

    def _invoice_select(self) -> Select[*tuple[Any, ...]]:
        allocated = _allocated(CustomerAllocation.sales_invoice_id, SalesInvoice)
        return (
            select(
                SalesInvoice.id,
                SalesInvoice.invoice_no,
                SalesInvoice.invoice_date,
                SalesInvoice.due_date,
                SalesInvoice.customer_id,
                Customer.name.label("customer_name"),
                Branch.name.label("branch_name"),
                Principal.name.label("principal_name"),
                SalesOrder.order_no,
                DeliveryNote.delivery_no,
                SalesInvoice.source_type,
                SalesInvoice.is_direct,
                SalesInvoice.total,
                allocated.label("allocated"),
                SalesInvoice.status,
                SalesInvoice.created_at,
            )
            .join(Customer, Customer.id == SalesInvoice.customer_id)
            .join(Branch, Branch.id == SalesInvoice.branch_id)
            .join(Principal, Principal.id == SalesInvoice.principal_id)
            .outerjoin(SalesOrder, SalesOrder.id == SalesInvoice.sales_order_id)
            .outerjoin(DeliveryNote, DeliveryNote.id == SalesInvoice.delivery_note_id)
            .where(self._branches(SalesInvoice.branch_id), *self._brands(SalesInvoice.principal_id))
        )

    def invoices(self, query: SalesInvoiceQuery) -> Page[SalesInvoiceListItem]:
        statement = self._filtered(
            self._invoice_select(), query, SalesInvoice.customer_id, SalesInvoice.branch_id, SalesInvoice.invoice_date
        )
        today = date.today()
        if query.sales_order_id is not None:
            statement = statement.where(
                or_(
                    SalesInvoice.sales_order_id == query.sales_order_id,
                    SalesInvoice.id.in_(
                        select(SalesInvoiceLine.sales_invoice_id)
                        .join(SalesOrderLine, SalesOrderLine.id == SalesInvoiceLine.sales_order_line_id)
                        .where(SalesOrderLine.sales_order_id == query.sales_order_id)
                    ),
                )
            )
        if query.delivery_note_id is not None:
            statement = statement.where(
                SalesInvoice.id.in_(
                    select(SalesInvoiceLine.sales_invoice_id)
                    .join(DeliveryNoteLine, DeliveryNoteLine.id == SalesInvoiceLine.delivery_note_line_id)
                    .where(DeliveryNoteLine.delivery_note_id == query.delivery_note_id)
                )
            )
        if query.direct_only:
            statement = statement.where(SalesInvoice.is_direct)
        if query.state == "Paid":
            statement = statement.where(SalesInvoice.status == "Paid")
        elif query.state == "Partially paid":
            statement = statement.where(SalesInvoice.status == "Part paid")
        elif query.state == "Unpaid":
            statement = statement.where(SalesInvoice.status.in_(OPEN))
        elif query.state == "Overdue":
            statement = statement.where(SalesInvoice.status.in_(OPEN), SalesInvoice.due_date < today)
        elif query.state == "Cancelled":
            statement = statement.where(SalesInvoice.status == "Cancelled")
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    SalesInvoice.invoice_no.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                    SalesOrder.order_no.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {"invoiceDate": SalesInvoice.invoice_date, "dueDate": SalesInvoice.due_date,
             "total": SalesInvoice.total, "invoiceNo": SalesInvoice.invoice_no},
            default="-invoiceDate",
            tiebreaker=SalesInvoice.id.desc(),
        )  # fmt: skip
        return self._page(statement, query, lambda r: SalesInvoiceListItem.model_validate(_invoice_fields(r)))

    def invoice(self, invoice_id: int) -> SalesInvoiceDetail:
        posted, override, cancelled = aliased(AppUser), aliased(AppUser), aliased(AppUser)
        header = (
            self._db.execute(
                self._invoice_select()
                .add_columns(
                    SalesInvoice.principal_id,
                    SalesInvoice.branch_id,
                    SalesInvoice.customer_site_id,
                    SalesInvoice.sales_order_id,
                    SalesInvoice.delivery_note_id,
                    SalesInvoice.invoice_type,
                    Company.legal_name.label("company_name"),
                    Company.address.label("company_address"),
                    Branch.address.label("branch_address"),
                    GstinRegistration.gstin.label("our_gstin"),
                    Customer.code.label("customer_code"),
                    func.coalesce(CustomerSite.gstin, Customer.gstin).label("customer_gstin"),
                    func.coalesce(CustomerSite.site_contact_phone, Customer.primary_phone).label("customer_phone"),
                    SalesInvoice.bill_to_address,
                    SalesInvoice.ship_to_address,
                    State.name.label("place_of_supply"),
                    Location.name.label("location_name"),
                    SalesInvoice.taxable_value,
                    SalesInvoice.cgst,
                    SalesInvoice.sgst,
                    SalesInvoice.igst,
                    SalesInvoice.other_charges,
                    SalesInvoice.round_off,
                    SalesInvoice.remarks,
                    posted.username.label("posted_by"),
                    override.username.label("credit_override_by"),
                    cancelled.username.label("cancelled_by"),
                    SalesInvoice.cancelled_at,
                    SalesInvoice.cancel_reason,
                )
                .join(Company, Company.id == SalesInvoice.company_id)
                .join(State, State.id == SalesInvoice.place_of_supply_state_id)
                .outerjoin(GstinRegistration, GstinRegistration.id == SalesInvoice.gstin_registration_id)
                .outerjoin(CustomerSite, CustomerSite.id == SalesInvoice.customer_site_id)
                .outerjoin(Location, Location.id == SalesInvoice.location_id)
                .outerjoin(posted, posted.id == SalesInvoice.posted_by_user_id)
                .outerjoin(override, override.id == SalesInvoice.credit_override_by_user_id)
                .outerjoin(cancelled, cancelled.id == SalesInvoice.cancelled_by_user_id)
                .where(SalesInvoice.id == invoice_id)
            )
            .mappings()
            .first()
        )
        if header is None:
            raise NotFound("Sales invoice not found.")
        line_note, line_order = aliased(DeliveryNote), aliased(SalesOrder)
        lines = [
            SalesInvoiceLineOut.model_validate(r)
            for r in self._db.execute(
                select(
                    SalesInvoiceLine.id,
                    SalesInvoiceLine.line_no,
                    SalesInvoiceLine.delivery_note_line_id,
                    line_note.delivery_no,
                    SalesInvoiceLine.sales_order_line_id,
                    line_order.order_no,
                    SalesInvoiceLine.item_id,
                    Item.item_code,
                    SalesInvoiceLine.description,
                    HsnSac.code.label("hsn_code"),
                    Uom.code.label("uom_code"),
                    SalesInvoiceLine.quantity,
                    SalesInvoiceLine.unit_price,
                    SalesInvoiceLine.discount_pct,
                    SalesInvoiceLine.gst_pct,
                    SalesInvoiceLine.taxable_value,
                    SalesInvoiceLine.cgst_amount,
                    SalesInvoiceLine.sgst_amount,
                    SalesInvoiceLine.igst_amount,
                    SalesInvoiceLine.line_total,
                )
                .outerjoin(Item, Item.id == SalesInvoiceLine.item_id)
                .outerjoin(HsnSac, HsnSac.id == SalesInvoiceLine.hsn_sac_id)
                .outerjoin(Uom, Uom.id == SalesInvoiceLine.uom_id)
                .outerjoin(DeliveryNoteLine, DeliveryNoteLine.id == SalesInvoiceLine.delivery_note_line_id)
                .outerjoin(line_note, line_note.id == DeliveryNoteLine.delivery_note_id)
                .outerjoin(SalesOrderLine, SalesOrderLine.id == SalesInvoiceLine.sales_order_line_id)
                .outerjoin(line_order, line_order.id == SalesOrderLine.sales_order_id)
                .where(SalesInvoiceLine.sales_invoice_id == invoice_id)
                .order_by(SalesInvoiceLine.line_no)
            )
            .mappings()
            .all()
        ]
        allocations = self._allocation_rows(CustomerAllocationQuery(sales_invoice_id=invoice_id, page_size=200)).items
        adjusted = sum((a.amount for a in allocations if a.is_active and a.receipt_type == "Order advance"), ZERO)
        return SalesInvoiceDetail.model_validate(
            {
                **_invoice_fields(header),
                "lines": lines,
                "allocations": allocations,
                "advance_adjusted": adjusted,
                "amount_in_words": rupees_in_words(header["total"]),
            }
        )

    # ================================================================ receipts

    def create_receipt(self, data: ReceiptCreate) -> ReceiptDetail:
        customer = active_customer(self._db, data.customer_id)
        branch = active_branch(self._db, self._actor, data.branch_id)
        if data.receipt_date > date.today():
            raise err("receiptDate", "The receipt date can't be in the future.")
        if data.payment_mode not in ("Cash",) and not data.reference_no:
            raise err("referenceNo", "Give the UTR, cheque or UPI reference.")
        order = None
        if data.receipt_type == "Order advance":
            if data.sales_order_id is None:
                raise err("salesOrderId", "Say which sales order the advance is for.")
            order = self._db.get(SalesOrder, data.sales_order_id)
            if order is None or order.customer_id != customer.id or order.status in ("Cancelled", "Closed"):
                raise err("salesOrderId", "That is not an open order of this customer.")
        elif data.sales_order_id is not None:
            raise err("salesOrderId", "Only an order advance is linked to an order.")
        receipt = Receipt(
            receipt_no=next_document_no(
                self._db, company_id=branch.company_id, document_type="CUSTOMER_RECEIPT", branch_id=branch.id
            ),
            branch_id=branch.id,
            customer_id=customer.id,
            receipt_date=data.receipt_date,
            receipt_type=data.receipt_type,
            sales_order_id=order.id if order else None,
            payment_mode=data.payment_mode,
            reference_no=data.reference_no,
            bank_name=data.bank_name,
            cheque_date=data.cheque_date,
            amount=data.amount,
            tds_deducted=ZERO,
            status="Posted",
            remarks=data.remarks,
            posted_by_user_id=self._actor.id,
            confirmed_by_user_id=self._actor.id,
            confirmed_at=now(),
            created_by_user_id=self._actor.id,
        )
        self._db.add(receipt)
        self._db.flush()
        if order is not None:
            order.advance_received = order.advance_received + data.amount
            order.updated_at = now()
            order.updated_by_user_id = self._actor.id
        if data.allocations:
            self._allocate(customer.id, data.allocations, data.amount, receipt_id=receipt.id)
        self._commit("The receipt could not be saved.")
        return self.receipt(receipt.id)

    def _receipt_select(self) -> Select[*tuple[Any, ...]]:
        allocated = _allocated(CustomerAllocation.receipt_id, Receipt)
        return (
            select(
                Receipt.id,
                Receipt.receipt_no,
                Receipt.receipt_date,
                Receipt.receipt_type,
                Receipt.customer_id,
                Customer.name.label("customer_name"),
                Branch.name.label("branch_name"),
                Receipt.sales_order_id,
                SalesOrder.order_no,
                Receipt.payment_mode,
                Receipt.reference_no,
                Receipt.amount,
                allocated.label("allocated"),
                (Receipt.amount - allocated).label("unallocated"),
                Receipt.status,
                Receipt.created_at,
            )
            .join(Customer, Customer.id == Receipt.customer_id)
            .join(Branch, Branch.id == Receipt.branch_id)
            .outerjoin(SalesOrder, SalesOrder.id == Receipt.sales_order_id)
            .where(self._branches(Receipt.branch_id))
        )

    def receipts(self, query: ReceiptQuery) -> Page[ReceiptListItem]:
        statement = self._filtered(
            self._receipt_select(), query, Receipt.customer_id, Receipt.branch_id, Receipt.receipt_date
        )
        if query.receipt_type is not None:
            statement = statement.where(Receipt.receipt_type == query.receipt_type)
        if query.sales_order_id is not None:
            statement = statement.where(Receipt.sales_order_id == query.sales_order_id)
        if query.unallocated_only:
            statement = statement.where(
                Receipt.status == "Posted", Receipt.amount > _allocated(CustomerAllocation.receipt_id, Receipt)
            )
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Receipt.receipt_no.contains(term, autoescape=True),
                    Receipt.reference_no.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {"receiptDate": Receipt.receipt_date, "amount": Receipt.amount},
            default="-receiptDate",
            tiebreaker=Receipt.id.desc(),
        )
        return self._page(statement, query, ReceiptListItem.model_validate)

    def receipt(self, receipt_id: int) -> ReceiptDetail:
        posted = aliased(AppUser)
        header = (
            self._db.execute(
                self._receipt_select()
                .add_columns(
                    Company.legal_name.label("company_name"),
                    Branch.address.label("branch_address"),
                    Customer.code.label("customer_code"),
                    Customer.billing_address.label("customer_address"),
                    Customer.gstin.label("customer_gstin"),
                    Receipt.bank_name,
                    Receipt.cheque_date,
                    Receipt.remarks,
                    posted.username.label("posted_by"),
                )
                .join(Company, Company.id == Branch.company_id)
                .outerjoin(posted, posted.id == Receipt.posted_by_user_id)
                .where(Receipt.id == receipt_id)
            )
            .mappings()
            .first()
        )
        if header is None:
            raise NotFound("Receipt not found.")
        allocations = self._allocation_rows(CustomerAllocationQuery(receipt_id=receipt_id, page_size=200)).items
        return ReceiptDetail.model_validate(
            {**header, "amount_in_words": rupees_in_words(header["amount"]), "allocations": allocations}
        )

    # ================================================================ allocations

    def allocate(self, data: CustomerAllocationCreate) -> list[CustomerAllocationOut]:
        receipt = self._db.get(Receipt, data.receipt_id)
        if receipt is None or receipt.status != "Posted" or not self._actor.can_use_branch(receipt.branch_id):
            raise NotFound("Receipt not found.")
        used = Decimal(
            self._db.scalar(
                select(func.coalesce(func.sum(CustomerAllocation.amount), 0)).where(
                    CustomerAllocation.receipt_id == receipt.id, CustomerAllocation.is_active
                )
            )
            or 0
        )
        ids = self._allocate(receipt.customer_id, data.allocations, receipt.amount - used, receipt_id=receipt.id)
        self._commit("The allocation could not be saved.")
        rows = self._allocation_rows(CustomerAllocationQuery(receipt_id=receipt.id, page_size=200)).items
        return [row for row in rows if row.id in ids]

    def _allocate(
        self, customer_id: int, items: list[CustomerAllocationIn], available: Decimal, *, receipt_id: int
    ) -> set[int]:
        total = sum((i.amount for i in items), ZERO)
        if total > available:
            raise err("allocations", f"Only {available:.2f} is left to allocate; {total:.2f} was asked.")
        asked: dict[int, Decimal] = defaultdict(lambda: ZERO)
        created = []
        for index, item in enumerate(items):
            invoice = self._db.get(SalesInvoice, item.sales_invoice_id)
            if invoice is None or invoice.customer_id != customer_id or invoice.status not in OPEN:
                raise err(f"allocations[{index}].salesInvoiceId", "That is not an open invoice of this customer.")
            asked[invoice.id] += item.amount
            outstanding = invoice.total - allocated_to_invoice(self._db, invoice.id)
            if asked[invoice.id] > outstanding:
                raise err(
                    f"allocations[{index}].amount", f"{invoice.invoice_no} has only {outstanding:.2f} outstanding."
                )
            row = CustomerAllocation(
                sales_invoice_id=invoice.id,
                receipt_id=receipt_id,
                amount=item.amount,
                allocated_on=date.today(),
                allocated_by_user_id=self._actor.id,
                created_by_user_id=self._actor.id,
            )
            self._db.add(row)
            created.append(row)
        self._db.flush()
        for invoice_id in asked:
            self._refresh_invoice(invoice_id)
        return {row.id for row in created}

    def reverse(self, allocation_id: int, data: CustomerAllocationReverse) -> CustomerAllocationOut:
        if not self._actor.can(ALLOCATION_REVERSE):
            raise Forbidden("You do not have permission to reverse allocations.")
        row = self._db.get(CustomerAllocation, allocation_id)
        if row is None or row.sales_invoice_id is None:
            raise NotFound("Allocation not found.")
        if not row.is_active:
            raise Conflict("This allocation is already reversed.")
        row.is_active = False
        row.reversed_at = now()
        row.reversed_by_user_id = self._actor.id
        row.reversal_reason = data.reason
        row.updated_at = row.reversed_at
        row.updated_by_user_id = self._actor.id
        self._db.flush()
        self._refresh_invoice(row.sales_invoice_id)
        self._commit("The allocation could not be reversed.")
        rows = self._allocation_rows(CustomerAllocationQuery(sales_invoice_id=row.sales_invoice_id, page_size=200))
        return next(r for r in rows.items if r.id == allocation_id)

    def allocations(self, query: CustomerAllocationQuery) -> Page[CustomerAllocationOut]:
        return self._allocation_rows(query)

    def _allocation_rows(self, query: CustomerAllocationQuery) -> Page[CustomerAllocationOut]:
        by, reverser = aliased(AppUser), aliased(AppUser)
        invoice_allocated = _allocated(CustomerAllocation.sales_invoice_id, SalesInvoice)
        alloc = aliased(CustomerAllocation)
        statement = (
            select(
                alloc.id,
                SalesInvoice.customer_id,
                Customer.name.label("customer_name"),
                alloc.sales_invoice_id,
                SalesInvoice.invoice_no,
                SalesInvoice.total.label("invoice_total"),
                (SalesInvoice.total - invoice_allocated).label("invoice_outstanding"),
                alloc.receipt_id,
                Receipt.receipt_no,
                Receipt.receipt_type,
                Receipt.reference_no.label("receipt_reference"),
                alloc.amount,
                alloc.allocated_on,
                by.username.label("allocated_by"),
                alloc.is_active,
                alloc.reversed_at,
                reverser.username.label("reversed_by"),
                alloc.reversal_reason,
            )
            .join(SalesInvoice, SalesInvoice.id == alloc.sales_invoice_id)
            .join(Customer, Customer.id == SalesInvoice.customer_id)
            .outerjoin(Receipt, Receipt.id == alloc.receipt_id)
            .outerjoin(by, by.id == alloc.allocated_by_user_id)
            .outerjoin(reverser, reverser.id == alloc.reversed_by_user_id)
            .where(self._branches(SalesInvoice.branch_id))
        )
        if query.customer_id is not None:
            statement = statement.where(SalesInvoice.customer_id == query.customer_id)
        if query.sales_invoice_id is not None:
            statement = statement.where(alloc.sales_invoice_id == query.sales_invoice_id)
        if query.receipt_id is not None:
            statement = statement.where(alloc.receipt_id == query.receipt_id)
        if not query.include_reversed:
            statement = statement.where(alloc.is_active)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    SalesInvoice.invoice_no.contains(term, autoescape=True),
                    Receipt.receipt_no.contains(term, autoescape=True),
                    Receipt.reference_no.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                )
            )
        statement = statement.order_by(alloc.allocated_on.desc(), alloc.id.desc())
        return self._page(statement, query, CustomerAllocationOut.model_validate)

    def _refresh_invoice(self, invoice_id: int) -> None:
        invoice = self._db.get(SalesInvoice, invoice_id)
        assert invoice is not None
        if invoice.status == "Cancelled":
            return
        paid = allocated_to_invoice(self._db, invoice.id)
        invoice.amount_received = paid
        invoice.status = "Paid" if paid >= invoice.total else ("Part paid" if paid > 0 else "Posted")
        invoice.updated_at = now()
        invoice.updated_by_user_id = self._actor.id

    # ================================================================ helpers

    def _visible_invoice(self, invoice_id: int) -> SalesInvoice:
        invoice = self._db.get(SalesInvoice, invoice_id)
        if invoice is None or not self._actor.can_use_branch(invoice.branch_id):
            raise NotFound("Sales invoice not found.")
        return invoice

    def _branches(self, column: Any) -> Any:
        return column.in_(self._actor.branch_ids) if self._actor.branch_ids is not None else column.is_not(None)

    def _brands(self, column: Any) -> list[Any]:
        return [] if self._actor.principal_ids is None else [column.in_(self._actor.principal_ids)]

    @staticmethod
    def _filtered(statement: Any, query: SalesAccountQuery, customer: Any, branch: Any, day: Any) -> Any:
        if query.customer_id is not None:
            statement = statement.where(customer == query.customer_id)
        if query.branch_id is not None:
            statement = statement.where(branch == query.branch_id)
        if query.from_date is not None:
            statement = statement.where(day >= query.from_date)
        if query.to_date is not None:
            statement = statement.where(day <= query.to_date)
        return statement

    def _page[T](self, statement: Any, query: Any, build: Callable[[Any], T]) -> Page[T]:
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = (
            self._db.execute(statement.offset((query.page - 1) * query.page_size).limit(query.page_size))
            .mappings()
            .all()
        )
        return Page(items=[build(r) for r in rows], total=total, page=query.page, page_size=query.page_size)

    def _commit(self, duplicate: str) -> None:
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists(duplicate) from error


def delivery_note_date_after(note: DeliveryNote, invoice_date: date) -> bool:
    return note.delivery_date > invoice_date


def _line_split(tax: Decimal, inter_state: bool) -> tuple[Decimal, Decimal, Decimal]:
    if inter_state:
        return ZERO, ZERO, money(tax)
    half = money(tax / 2)
    return half, money(tax) - half, ZERO


def _invoice_fields(row: Any) -> dict[str, Any]:
    today = date.today()
    allocated = Decimal(row["allocated"] or 0)
    outstanding = row["total"] - allocated if row["status"] != "Cancelled" else ZERO
    due = row["due_date"]
    return {
        **row,
        "allocated": allocated,
        "outstanding": outstanding,
        "state": invoice_state(row["status"], due, outstanding, today),
        "overdue_days": max((today - due).days, 0) if due and outstanding > 0 else 0,
    }
