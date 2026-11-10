"""Supplier accounts: invoices, payments, credit notes and allocations.

Invoices
  * Billed from GRN lines (the usual case), from order lines not yet received, or directly (an item or just
    a description). Anything not backed by a GRN needs pur.invoice.direct.
  * An invoice never adds stock: goods come in only through a GRN. Each GRN line can be billed once
    (grn_line.qty_invoiced), order lines track qty_invoiced too.
  * The supplier's invoice number is unique per supplier (UX_pur_supplier_invoice_k1).
  * Totals: taxable + GST (CGST/SGST or IGST) + other charges, rounded to the rupee (round_off recorded).
Payments and credit notes reduce the balance at once; allocations record which invoices they settle.
A payment can be allocated now, later, or stay an advance. A credit note linked to an invoice is set
against it automatically. A purchase-return credit note takes the goods out of stock from their GRN batch.
Allocations are never deleted: a reversal keeps the row (is_active 0) with who reversed it, when and why.
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
from trishul_api.common.errors import AlreadyExists, ApiError, Conflict, Forbidden, NotFound
from trishul_api.common.numbering import next_document_no
from trishul_api.common.paging import order_by_sort
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Bin,
    Branch,
    Company,
    DebitNote,
    DebitNoteLine,
    Grn,
    GrnLine,
    Item,
    Location,
    LookupType,
    LookupValue,
    PaymentTerms,
    PurchaseOrder,
    PurchaseOrderLine,
    State,
    StockLot,
    Supplier,
    SupplierAllocation,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierPayment,
)
from trishul_api.modules.inv.common import company_of_branch, now, rack_of, stock_item, stock_location
from trishul_api.modules.inv.ledger import Source, StockLedger
from trishul_api.modules.pur.account_schemas import (
    AccountQuery,
    AllocationCreate,
    AllocationIn,
    AllocationOut,
    AllocationQuery,
    AllocationReverse,
    CreditNoteCreate,
    CreditNoteDetail,
    CreditNoteLineOut,
    CreditNoteListItem,
    InvoiceCreate,
    InvoiceDetail,
    InvoiceLineOut,
    InvoiceListItem,
    InvoiceQuery,
    InvoiceState,
    PaymentCreate,
    PaymentDetail,
    PaymentListItem,
)
from trishul_api.modules.pur.common import (
    ALLOCATION_REVERSE,
    INVOICE_DIRECT,
    ZERO,
    active_branch,
    active_supplier,
    allocated_to_invoice,
    branch_state,
    is_inter_state,
    line_amounts,
    money,
    rupees,
    split_gst,
)
from trishul_api.modules.pur.words import rupees_in_words

OPEN = ("Posted", "Part paid")
RETURN_REASON = "RETURN_REASON"
_QTY = Decimal("0.001")


def _err(field: str, message: str) -> ApiError:
    return ApiError(message, errors={field: [message]})


def _allocated(column: Any, correlate: Any) -> Any:
    return (
        select(func.coalesce(func.sum(SupplierAllocation.amount), 0))
        .where(column == correlate.id, SupplierAllocation.is_active)
        .correlate(correlate)
        .scalar_subquery()
    )


def invoice_state(status: str, due: date | None, outstanding: Decimal, today: date) -> InvoiceState:
    if status == "Cancelled":
        return "Cancelled"
    if outstanding <= 0:
        return "Paid"
    if due is not None and due < today:
        return "Overdue"
    return "Partially paid" if status == "Part paid" else "Unpaid"


class AccountService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ================================================================ invoices

    def create_invoice(self, data: InvoiceCreate) -> InvoiceDetail:
        supplier = active_supplier(self._db, data.supplier_id)
        number = data.supplier_invoice_no.strip()
        duplicate = self._db.scalar(
            select(SupplierInvoice.invoice_no).where(
                SupplierInvoice.supplier_id == supplier.id,
                func.upper(SupplierInvoice.supplier_invoice_no) == number.upper(),
            )
        )
        if duplicate is not None:
            raise AlreadyExists(f"Invoice {number} of {supplier.name} is already recorded as {duplicate}.")
        if data.supplier_invoice_date > date.today():
            raise _err("supplierInvoiceDate", "The invoice date can't be in the future.")

        billed_grn: dict[int, Decimal] = defaultdict(lambda: ZERO)
        billed_po: dict[int, Decimal] = defaultdict(lambda: ZERO)
        prepared = []
        grn_ids: set[int] = set()
        po_ids: set[int] = set()
        branch_ids: set[int] = set()
        direct = False
        for index, line in enumerate(data.lines):
            field = f"lines[{index}]"
            grn_line = order_line = None
            item_id = line.item_id
            if line.grn_line_id is not None:
                grn_line = self._db.get(GrnLine, line.grn_line_id)
                grn = self._db.get(Grn, grn_line.grn_id) if grn_line else None
                if grn_line is None or grn is None or grn.supplier_id != supplier.id or grn.status != "Posted":
                    raise _err(f"{field}.grnLineId", "That GRN line is not from this supplier.")
                left = grn_line.qty_accepted - grn_line.qty_invoiced - billed_grn[grn_line.id]
                if line.quantity > left:
                    raise _err(f"{field}.quantity", f"Only {_qty(left)} of that GRN line is left to invoice.")
                billed_grn[grn_line.id] += line.quantity
                item_id = grn_line.item_id
                grn_ids.add(grn.id)
                branch_ids.add(grn.branch_id)
                if grn_line.purchase_order_line_id:
                    order_line = self._db.get(PurchaseOrderLine, grn_line.purchase_order_line_id)
                if grn.purchase_order_id:
                    po_ids.add(grn.purchase_order_id)
            elif line.purchase_order_line_id is not None:
                self._need_direct()
                direct = True
                order_line = self._db.get(PurchaseOrderLine, line.purchase_order_line_id)
                po = self._db.get(PurchaseOrder, order_line.purchase_order_id) if order_line else None
                if order_line is None or po is None or po.supplier_id != supplier.id:
                    raise _err(f"{field}.purchaseOrderLineId", "That order line is not from this supplier.")
                if po.status in ("Draft", "Pending approval", "Cancelled"):
                    raise _err(f"{field}.purchaseOrderLineId", f"Order {po.po_no} is {po.status.lower()}.")
                left = order_line.quantity - order_line.qty_invoiced - billed_po[order_line.id]
                if line.quantity > left:
                    raise _err(f"{field}.quantity", f"Only {_qty(left)} of that order line is left to invoice.")
                billed_po[order_line.id] += line.quantity
                item_id = order_line.item_id
                po_ids.add(po.id)
                branch_ids.add(po.branch_id)
            else:
                self._need_direct()
                direct = True
                if item_id is not None:
                    item = self._db.get(Item, item_id)
                    if item is None or not item.is_active:
                        raise _err(f"{field}.itemId", "Choose an active item.")
            prepared.append((line, grn_line, order_line, item_id))

        branch_id = data.branch_id or (branch_ids.pop() if len(branch_ids) == 1 else None)
        if branch_id is None:
            raise _err("branchId", "Choose the branch the invoice is booked in.")
        branch = active_branch(self._db, self._actor, branch_id)
        inter_state = is_inter_state(self._db, supplier, branch.id)

        taxable = tax = ZERO
        rows = []
        for line, grn_line, order_line, item_id in prepared:
            amounts = line_amounts(line.quantity, line.unit_price, line.discount_pct, line.gst_pct)
            taxable += amounts.taxable
            tax += amounts.tax
            rows.append(
                SupplierInvoiceLine(
                    grn_line_id=grn_line.id if grn_line else None,
                    purchase_order_line_id=order_line.id if order_line else None,
                    item_id=item_id,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount_pct=line.discount_pct,
                    gst_pct=line.gst_pct,
                    taxable_value=amounts.taxable,
                    tax_amount=amounts.tax,
                    line_total=amounts.total,
                    created_by_user_id=self._actor.id,
                )
            )
            if grn_line is not None:
                grn_line.qty_invoiced = grn_line.qty_invoiced + line.quantity
            if order_line is not None:
                order_line.qty_invoiced = order_line.qty_invoiced + line.quantity

        split = split_gst(tax, inter_state=inter_state)
        raw = taxable + split.cgst + split.sgst + split.igst + data.other_charges
        total = rupees(raw)
        invoice = SupplierInvoice(
            invoice_no=next_document_no(
                self._db, company_id=branch.company_id, document_type="SUPPLIER_INVOICE", branch_id=branch.id
            ),
            supplier_invoice_no=number,
            supplier_invoice_date=data.supplier_invoice_date,
            supplier_id=supplier.id,
            branch_id=branch.id,
            purchase_order_id=po_ids.pop() if len(po_ids) == 1 else None,
            grn_id=grn_ids.pop() if len(grn_ids) == 1 else None,
            place_of_supply_state_id=branch_state(self._db, branch.id),
            taxable_value=taxable,
            cgst=split.cgst,
            sgst=split.sgst,
            igst=split.igst,
            other_charges=data.other_charges,
            round_off=total - raw,
            total=total,
            due_date=data.due_date or self._due_date(supplier, data.supplier_invoice_date),
            amount_paid=ZERO,
            status="Posted",
            is_direct=direct,
            remarks=data.remarks,
            posted_by_user_id=self._actor.id,
            created_by_user_id=self._actor.id,
        )
        self._db.add(invoice)
        self._db.flush()
        for row in rows:
            row.supplier_invoice_id = invoice.id
            self._db.add(row)
        self._commit(f"Invoice {number} of {supplier.name} is already recorded.")
        return self.invoice(invoice.id)

    def _due_date(self, supplier: Supplier, invoice_date: date) -> date | None:
        if supplier.payment_terms_id is None:
            return None
        terms = self._db.get(PaymentTerms, supplier.payment_terms_id)
        if terms is None or terms.days_before_due is None:
            return None
        return invoice_date + timedelta(days=terms.days_before_due)

    def _invoice_select(self) -> Select[*tuple[Any, ...]]:
        allocated = _allocated(SupplierAllocation.supplier_invoice_id, SupplierInvoice)
        return (
            select(
                SupplierInvoice.id,
                SupplierInvoice.invoice_no,
                SupplierInvoice.supplier_invoice_no,
                SupplierInvoice.supplier_invoice_date,
                SupplierInvoice.due_date,
                SupplierInvoice.supplier_id,
                Supplier.name.label("supplier_name"),
                Branch.name.label("branch_name"),
                PurchaseOrder.po_no,
                Grn.grn_no,
                SupplierInvoice.is_direct,
                SupplierInvoice.total,
                SupplierInvoice.status,
                allocated.label("allocated"),
                SupplierInvoice.created_at,
            )
            .join(Supplier, Supplier.id == SupplierInvoice.supplier_id)
            .join(Branch, Branch.id == SupplierInvoice.branch_id)
            .outerjoin(PurchaseOrder, PurchaseOrder.id == SupplierInvoice.purchase_order_id)
            .outerjoin(Grn, Grn.id == SupplierInvoice.grn_id)
            .where(self._branches(SupplierInvoice.branch_id))
        )

    def invoices(self, query: InvoiceQuery) -> Page[InvoiceListItem]:
        statement = self._filtered(
            self._invoice_select(),
            query,
            SupplierInvoice.supplier_id,
            SupplierInvoice.branch_id,
            SupplierInvoice.supplier_invoice_date,
        )
        today = date.today()
        if query.purchase_order_id is not None:
            statement = statement.where(SupplierInvoice.purchase_order_id == query.purchase_order_id)
        if query.grn_id is not None:
            statement = statement.where(SupplierInvoice.grn_id == query.grn_id)
        if query.state == "Paid":
            statement = statement.where(SupplierInvoice.status == "Paid")
        elif query.state == "Partially paid":
            statement = statement.where(SupplierInvoice.status == "Part paid")
        elif query.state == "Unpaid":
            statement = statement.where(SupplierInvoice.status.in_(OPEN))
        elif query.state == "Overdue":
            statement = statement.where(SupplierInvoice.status.in_(OPEN), SupplierInvoice.due_date < today)
        elif query.state == "Cancelled":
            statement = statement.where(SupplierInvoice.status == "Cancelled")
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    SupplierInvoice.invoice_no.contains(term, autoescape=True),
                    SupplierInvoice.supplier_invoice_no.contains(term, autoescape=True),
                    Supplier.name.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {
                "supplierInvoiceDate": SupplierInvoice.supplier_invoice_date,
                "dueDate": SupplierInvoice.due_date,
                "total": SupplierInvoice.total,
                "invoiceNo": SupplierInvoice.invoice_no,
            },
            default="-supplierInvoiceDate",
            tiebreaker=SupplierInvoice.id.desc(),
        )
        return self._page(statement, query, self._invoice_item)

    @staticmethod
    def _invoice_item(row: Any) -> InvoiceListItem:
        return InvoiceListItem.model_validate(AccountService._invoice_fields(row))

    @staticmethod
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

    def invoice(self, invoice_id: int) -> InvoiceDetail:
        posted = aliased(AppUser)
        header = (
            self._db.execute(
                self._invoice_select()
                .add_columns(
                    SupplierInvoice.branch_id,
                    SupplierInvoice.purchase_order_id,
                    SupplierInvoice.grn_id,
                    State.name.label("place_of_supply"),
                    SupplierInvoice.taxable_value,
                    SupplierInvoice.cgst,
                    SupplierInvoice.sgst,
                    SupplierInvoice.igst,
                    SupplierInvoice.other_charges,
                    SupplierInvoice.round_off,
                    SupplierInvoice.remarks,
                    posted.username.label("posted_by"),
                )
                .join(State, State.id == SupplierInvoice.place_of_supply_state_id)
                .outerjoin(posted, posted.id == SupplierInvoice.posted_by_user_id)
                .where(SupplierInvoice.id == invoice_id)
            )
            .mappings()
            .first()
        )
        if header is None:
            raise NotFound("Supplier invoice not found.")
        line_grn = aliased(Grn)
        lines = [
            InvoiceLineOut.model_validate(r)
            for r in self._db.execute(
                select(
                    SupplierInvoiceLine.id,
                    SupplierInvoiceLine.grn_line_id,
                    line_grn.grn_no,
                    SupplierInvoiceLine.purchase_order_line_id,
                    SupplierInvoiceLine.item_id,
                    Item.item_code,
                    func.coalesce(SupplierInvoiceLine.description, Item.description).label("description"),
                    SupplierInvoiceLine.quantity,
                    SupplierInvoiceLine.unit_price,
                    SupplierInvoiceLine.discount_pct,
                    SupplierInvoiceLine.gst_pct,
                    SupplierInvoiceLine.taxable_value,
                    SupplierInvoiceLine.tax_amount,
                    SupplierInvoiceLine.line_total,
                )
                .outerjoin(Item, Item.id == SupplierInvoiceLine.item_id)
                .outerjoin(GrnLine, GrnLine.id == SupplierInvoiceLine.grn_line_id)
                .outerjoin(line_grn, line_grn.id == GrnLine.grn_id)
                .where(SupplierInvoiceLine.supplier_invoice_id == invoice_id)
                .order_by(SupplierInvoiceLine.id)
            )
            .mappings()
            .all()
        ]
        allocations = self._allocation_rows(AllocationQuery(supplier_invoice_id=invoice_id, page_size=200)).items
        return InvoiceDetail.model_validate(
            {**self._invoice_fields(header), "lines": lines, "allocations": allocations}
        )

    # ================================================================ payments

    def create_payment(self, data: PaymentCreate) -> PaymentDetail:
        supplier = active_supplier(self._db, data.supplier_id)
        branch = active_branch(self._db, self._actor, data.branch_id)
        if data.payment_date > date.today():
            raise _err("paymentDate", "The payment date can't be in the future.")
        if data.payment_mode != "Cash" and not data.reference_no:
            raise _err("referenceNo", "Give the UTR, cheque or UPI reference.")
        payment = SupplierPayment(
            payment_no=next_document_no(
                self._db, company_id=branch.company_id, document_type="SUPPLIER_PAYMENT", branch_id=branch.id
            ),
            supplier_id=supplier.id,
            branch_id=branch.id,
            payment_date=data.payment_date,
            payment_mode=data.payment_mode,
            reference_no=data.reference_no,
            bank_name=data.bank_name,
            cheque_date=data.cheque_date,
            amount=data.amount,
            status="Posted",
            remarks=data.remarks,
            posted_by_user_id=self._actor.id,
            created_by_user_id=self._actor.id,
        )
        self._db.add(payment)
        self._db.flush()
        if data.allocations:
            self._allocate(supplier.id, data.allocations, data.amount, payment_id=payment.id)
        self._commit("The payment could not be saved.")
        return self.payment(payment.id)

    def _payment_select(self) -> Select[*tuple[Any, ...]]:
        allocated = _allocated(SupplierAllocation.supplier_payment_id, SupplierPayment)
        return (
            select(
                SupplierPayment.id,
                SupplierPayment.payment_no,
                SupplierPayment.payment_date,
                SupplierPayment.supplier_id,
                Supplier.name.label("supplier_name"),
                Branch.name.label("branch_name"),
                SupplierPayment.payment_mode,
                SupplierPayment.reference_no,
                SupplierPayment.amount,
                allocated.label("allocated"),
                (SupplierPayment.amount - allocated).label("unallocated"),
                SupplierPayment.status,
                SupplierPayment.created_at,
            )
            .join(Supplier, Supplier.id == SupplierPayment.supplier_id)
            .join(Branch, Branch.id == SupplierPayment.branch_id)
            .where(self._branches(SupplierPayment.branch_id))
        )

    def payments(self, query: AccountQuery) -> Page[PaymentListItem]:
        statement = self._filtered(
            self._payment_select(),
            query,
            SupplierPayment.supplier_id,
            SupplierPayment.branch_id,
            SupplierPayment.payment_date,
        )
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    SupplierPayment.payment_no.contains(term, autoescape=True),
                    SupplierPayment.reference_no.contains(term, autoescape=True),
                    Supplier.name.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {"paymentDate": SupplierPayment.payment_date, "amount": SupplierPayment.amount},
            default="-paymentDate",
            tiebreaker=SupplierPayment.id.desc(),
        )
        return self._page(statement, query, PaymentListItem.model_validate)

    def payment(self, payment_id: int) -> PaymentDetail:
        posted = aliased(AppUser)
        header = (
            self._db.execute(
                self._payment_select()
                .add_columns(
                    Company.legal_name.label("company_name"),
                    Supplier.code.label("supplier_code"),
                    Supplier.address.label("supplier_address"),
                    Supplier.gstin.label("supplier_gstin"),
                    SupplierPayment.bank_name,
                    SupplierPayment.cheque_date,
                    SupplierPayment.remarks,
                    posted.username.label("posted_by"),
                )
                .join(Company, Company.id == Branch.company_id)
                .outerjoin(posted, posted.id == SupplierPayment.posted_by_user_id)
                .where(SupplierPayment.id == payment_id)
            )
            .mappings()
            .first()
        )
        if header is None:
            raise NotFound("Payment not found.")
        allocations = self._allocation_rows(AllocationQuery(supplier_payment_id=payment_id, page_size=200)).items
        return PaymentDetail.model_validate(
            {**header, "amount_in_words": rupees_in_words(header["amount"]), "allocations": allocations}
        )

    # ================================================================ credit notes

    def create_credit_note(self, data: CreditNoteCreate) -> CreditNoteDetail:
        supplier = active_supplier(self._db, data.supplier_id)
        branch = active_branch(self._db, self._actor, data.branch_id)
        if data.note_date > date.today():
            raise _err("noteDate", "The date can't be in the future.")
        if data.supplier_note_no:
            taken = self._db.scalar(
                select(DebitNote.debit_note_no).where(
                    DebitNote.supplier_id == supplier.id, DebitNote.supplier_note_no == data.supplier_note_no
                )
            )
            if taken is not None:
                raise AlreadyExists(f"Credit note {data.supplier_note_no} of {supplier.name} is already {taken}.")
        invoice = None
        if data.supplier_invoice_id is not None:
            invoice = self._db.get(SupplierInvoice, data.supplier_invoice_id)
            if invoice is None or invoice.supplier_id != supplier.id or invoice.status == "Cancelled":
                raise _err("supplierInvoiceId", "That invoice is not an open invoice of this supplier.")
        if data.reason_id is not None:
            self._check_reason(data.reason_id)
        is_return = data.note_type == "Purchase return"
        location = None
        if is_return:
            if data.location_id is None:
                raise _err("locationId", "Say where the returned goods leave from.")
            location = stock_location(self._db, self._actor, data.location_id)
            if location.branch_id != branch.id:
                raise _err("locationId", "The location is in another branch.")

        inter_state = is_inter_state(self._db, supplier, branch.id)
        note = DebitNote(
            debit_note_no=next_document_no(
                self._db, company_id=branch.company_id, document_type="SUPPLIER_CREDIT_NOTE", branch_id=branch.id
            ),
            supplier_id=supplier.id,
            supplier_invoice_id=invoice.id if invoice else None,
            grn_id=data.grn_id,
            note_date=data.note_date,
            reason_lookup_id=data.reason_id,
            note_type=data.note_type,
            supplier_note_no=data.supplier_note_no,
            supplier_note_date=data.supplier_note_date,
            branch_id=branch.id,
            location_id=location.id if location else None,
            remarks=data.remarks,
            taxable_value=ZERO,
            tax_amount=ZERO,
            total=ZERO,
            status="Posted",
            posted_by_user_id=self._actor.id,
            created_by_user_id=self._actor.id,
        )
        self._db.add(note)
        self._db.flush()
        ledger = (
            StockLedger(self._db, company_id=company_of_branch(self._db, branch.id), user_id=self._actor.id, at=now())
            if is_return
            else None
        )
        taxable = tax = ZERO
        for index, line in enumerate(data.lines):
            field = f"lines[{index}]"
            amounts = line_amounts(line.quantity, line.unit_price, ZERO, line.gst_pct)
            taxable += amounts.taxable
            tax += amounts.tax
            row = DebitNoteLine(
                debit_note_id=note.id,
                item_id=line.item_id,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                gst_pct=line.gst_pct,
                taxable_value=amounts.taxable,
                tax_amount=amounts.tax,
                line_total=amounts.total,
                grn_line_id=line.grn_line_id,
                created_by_user_id=self._actor.id,
            )
            if ledger is not None and location is not None:
                if line.item_id is None:
                    raise _err(f"{field}.itemId", "A returned line needs the item.")
                item = stock_item(self._db, self._actor, line.item_id, f"{field}.itemId")
                lot_id = line.stock_lot_id or self._lot_of(line.grn_line_id, item.id, supplier.id, field)
                bin_id = rack_of(self._db, location, line.bin_id, f"{field}.binId")
                self._db.add(row)
                self._db.flush()
                removed = ledger.take(
                    item=item,
                    location_id=location.id,
                    bin_id=bin_id,
                    quantity=line.quantity,
                    movement="PURCHASE_RETURN",
                    source=Source("SUPPLIER_CREDIT_NOTE", note.id, note.debit_note_no, row.id),
                    lot_id=lot_id,
                    location_label=location.name,
                )
                row.stock_lot_id = removed[0].lot.id if len({t.lot.id for t in removed}) == 1 else lot_id
                row.bin_id = removed[0].bin_id if len({t.bin_id for t in removed}) == 1 else bin_id
            else:
                self._db.add(row)
        split = split_gst(tax, inter_state=inter_state)
        note.taxable_value = taxable
        note.tax_amount = money(tax)
        note.cgst, note.sgst, note.igst = split.cgst, split.sgst, split.igst
        note.total = taxable + money(tax)
        self._db.flush()
        if invoice is not None:
            outstanding = invoice.total - allocated_to_invoice(self._db, invoice.id)
            amount = min(note.total, outstanding)
            if amount > 0:
                self._allocate(
                    supplier.id,
                    [AllocationIn(supplier_invoice_id=invoice.id, amount=amount)],
                    note.total,
                    debit_note_id=note.id,
                )
        self._commit("The credit note could not be saved.")
        return self.credit_note(note.id)

    def _lot_of(self, grn_line_id: int | None, item_id: int, supplier_id: int, field: str) -> int | None:
        if grn_line_id is None:
            return None
        lot = self._db.scalar(select(StockLot).where(StockLot.grn_line_id == grn_line_id))
        if lot is None or lot.item_id != item_id or lot.supplier_id != supplier_id:
            raise _err(f"{field}.grnLineId", "That GRN line is not this item from this supplier.")
        return lot.id

    def _check_reason(self, reason_id: int) -> None:
        found = self._db.scalar(
            select(LookupValue.id)
            .join(LookupType, LookupType.id == LookupValue.lookup_type_id)
            .where(LookupValue.id == reason_id, LookupType.code == RETURN_REASON)
        )
        if found is None:
            raise _err("reasonId", "Choose a reason from the list.")

    def _note_select(self) -> Select[*tuple[Any, ...]]:
        allocated = _allocated(SupplierAllocation.debit_note_id, DebitNote)
        return (
            select(
                DebitNote.id,
                DebitNote.debit_note_no,
                DebitNote.note_date,
                DebitNote.note_type,
                DebitNote.supplier_id,
                Supplier.name.label("supplier_name"),
                DebitNote.supplier_note_no,
                SupplierInvoice.invoice_no,
                DebitNote.total,
                allocated.label("allocated"),
                (DebitNote.total - allocated).label("unallocated"),
                DebitNote.status,
                DebitNote.created_at,
            )
            .join(Supplier, Supplier.id == DebitNote.supplier_id)
            .outerjoin(SupplierInvoice, SupplierInvoice.id == DebitNote.supplier_invoice_id)
            .where(or_(DebitNote.branch_id.is_(None), self._branches(DebitNote.branch_id)))
        )

    def credit_notes(self, query: AccountQuery) -> Page[CreditNoteListItem]:
        statement = self._filtered(
            self._note_select(), query, DebitNote.supplier_id, DebitNote.branch_id, DebitNote.note_date
        )
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    DebitNote.debit_note_no.contains(term, autoescape=True),
                    DebitNote.supplier_note_no.contains(term, autoescape=True),
                    Supplier.name.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {"noteDate": DebitNote.note_date, "total": DebitNote.total},
            default="-noteDate",
            tiebreaker=DebitNote.id.desc(),
        )
        return self._page(statement, query, CreditNoteListItem.model_validate)

    def credit_note(self, note_id: int) -> CreditNoteDetail:
        posted = aliased(AppUser)
        note_branch = aliased(Branch)
        header = (
            self._db.execute(
                self._note_select()
                .add_columns(
                    note_branch.name.label("branch_name"),
                    Location.name.label("location_name"),
                    DebitNote.supplier_note_date,
                    DebitNote.supplier_invoice_id,
                    DebitNote.grn_id,
                    LookupValue.label.label("reason"),
                    DebitNote.taxable_value,
                    DebitNote.cgst,
                    DebitNote.sgst,
                    DebitNote.igst,
                    DebitNote.remarks,
                    posted.username.label("posted_by"),
                )
                .outerjoin(note_branch, note_branch.id == DebitNote.branch_id)
                .outerjoin(Location, Location.id == DebitNote.location_id)
                .outerjoin(LookupValue, LookupValue.id == DebitNote.reason_lookup_id)
                .outerjoin(posted, posted.id == DebitNote.posted_by_user_id)
                .where(DebitNote.id == note_id)
            )
            .mappings()
            .first()
        )
        if header is None:
            raise NotFound("Credit note not found.")
        lines = [
            CreditNoteLineOut.model_validate(r)
            for r in self._db.execute(
                select(
                    DebitNoteLine.id,
                    DebitNoteLine.item_id,
                    Item.item_code,
                    func.coalesce(DebitNoteLine.description, Item.description).label("description"),
                    DebitNoteLine.quantity,
                    DebitNoteLine.unit_price,
                    DebitNoteLine.gst_pct,
                    DebitNoteLine.taxable_value,
                    DebitNoteLine.tax_amount,
                    DebitNoteLine.line_total,
                    StockLot.lot_no,
                    StockLot.grn_no,
                    Bin.code.label("bin_code"),
                )
                .outerjoin(Item, Item.id == DebitNoteLine.item_id)
                .outerjoin(StockLot, StockLot.id == DebitNoteLine.stock_lot_id)
                .outerjoin(Bin, Bin.id == DebitNoteLine.bin_id)
                .where(DebitNoteLine.debit_note_id == note_id)
                .order_by(DebitNoteLine.id)
            )
            .mappings()
            .all()
        ]
        allocations = self._allocation_rows(AllocationQuery(debit_note_id=note_id, page_size=200)).items
        return CreditNoteDetail.model_validate({**header, "lines": lines, "allocations": allocations})

    # ================================================================ allocations

    def allocate(self, data: AllocationCreate) -> list[AllocationOut]:
        if data.supplier_payment_id is not None:
            payment = self._db.get(SupplierPayment, data.supplier_payment_id)
            if payment is None or payment.status != "Posted" or not self._actor.can_use_branch(payment.branch_id):
                raise NotFound("Payment not found.")
            used = self._db.scalar(_used(SupplierAllocation.supplier_payment_id, payment.id)) or 0
            supplier_id, available = payment.supplier_id, payment.amount - Decimal(used)
        else:
            note = self._db.get(DebitNote, data.debit_note_id)
            if note is None or note.status != "Posted":
                raise NotFound("Credit note not found.")
            used = self._db.scalar(_used(SupplierAllocation.debit_note_id, note.id)) or 0
            supplier_id, available = note.supplier_id, note.total - Decimal(used)
        ids = self._allocate(
            supplier_id,
            data.allocations,
            available,
            payment_id=data.supplier_payment_id,
            debit_note_id=data.debit_note_id,
        )
        self._commit("The allocation could not be saved.")
        rows = self._allocation_rows(AllocationQuery(supplier_id=supplier_id, page_size=200)).items
        return [row for row in rows if row.id in ids]

    def _allocate(
        self,
        supplier_id: int,
        items: list[AllocationIn],
        available: Decimal,
        *,
        payment_id: int | None = None,
        debit_note_id: int | None = None,
    ) -> set[int]:
        total = sum((i.amount for i in items), ZERO)
        if total > available:
            raise _err("allocations", f"Only {available:.2f} is left to allocate; {total:.2f} was asked.")
        asked: dict[int, Decimal] = defaultdict(lambda: ZERO)
        created = []
        for index, item in enumerate(items):
            invoice = self._db.get(SupplierInvoice, item.supplier_invoice_id)
            if invoice is None or invoice.supplier_id != supplier_id or invoice.status not in OPEN:
                raise _err(f"allocations[{index}].supplierInvoiceId", "That is not an open invoice of this supplier.")
            asked[invoice.id] += item.amount
            outstanding = invoice.total - allocated_to_invoice(self._db, invoice.id)
            if asked[invoice.id] > outstanding:
                raise _err(
                    f"allocations[{index}].amount", f"{invoice.invoice_no} has only {outstanding:.2f} outstanding."
                )
            row = SupplierAllocation(
                supplier_invoice_id=invoice.id,
                supplier_payment_id=payment_id,
                debit_note_id=debit_note_id,
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

    def reverse(self, allocation_id: int, data: AllocationReverse) -> AllocationOut:
        if not self._actor.can(ALLOCATION_REVERSE):
            raise Forbidden("You do not have permission to reverse allocations.")
        row = self._db.get(SupplierAllocation, allocation_id)
        if row is None or row.supplier_invoice_id is None:
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
        self._refresh_invoice(row.supplier_invoice_id)
        self._commit("The allocation could not be reversed.")
        rows = self._allocation_rows(AllocationQuery(supplier_invoice_id=row.supplier_invoice_id, page_size=200))
        return next(r for r in rows.items if r.id == allocation_id)

    def allocations(self, query: AllocationQuery) -> Page[AllocationOut]:
        return self._allocation_rows(query)

    def _allocation_rows(self, query: AllocationQuery) -> Page[AllocationOut]:
        by, reverser = aliased(AppUser), aliased(AppUser)
        invoice_allocated = (
            select(func.coalesce(func.sum(SupplierAllocation.amount), 0))
            .where(SupplierAllocation.supplier_invoice_id == SupplierInvoice.id, SupplierAllocation.is_active)
            .correlate(SupplierInvoice)
            .scalar_subquery()
        )
        alloc = aliased(SupplierAllocation)
        statement = (
            select(
                alloc.id,
                SupplierInvoice.supplier_id,
                Supplier.name.label("supplier_name"),
                alloc.supplier_invoice_id,
                SupplierInvoice.invoice_no,
                SupplierInvoice.supplier_invoice_no,
                SupplierInvoice.total.label("invoice_total"),
                (SupplierInvoice.total - invoice_allocated).label("invoice_outstanding"),
                alloc.supplier_payment_id,
                SupplierPayment.payment_no,
                SupplierPayment.reference_no.label("payment_reference"),
                alloc.debit_note_id,
                DebitNote.debit_note_no.label("credit_note_no"),
                alloc.amount,
                alloc.allocated_on,
                by.username.label("allocated_by"),
                alloc.is_active,
                alloc.reversed_at,
                reverser.username.label("reversed_by"),
                alloc.reversal_reason,
            )
            .join(SupplierInvoice, SupplierInvoice.id == alloc.supplier_invoice_id)
            .join(Supplier, Supplier.id == SupplierInvoice.supplier_id)
            .outerjoin(SupplierPayment, SupplierPayment.id == alloc.supplier_payment_id)
            .outerjoin(DebitNote, DebitNote.id == alloc.debit_note_id)
            .outerjoin(by, by.id == alloc.allocated_by_user_id)
            .outerjoin(reverser, reverser.id == alloc.reversed_by_user_id)
            .where(self._branches(SupplierInvoice.branch_id))
        )
        if query.supplier_id is not None:
            statement = statement.where(SupplierInvoice.supplier_id == query.supplier_id)
        if query.supplier_invoice_id is not None:
            statement = statement.where(alloc.supplier_invoice_id == query.supplier_invoice_id)
        if query.supplier_payment_id is not None:
            statement = statement.where(alloc.supplier_payment_id == query.supplier_payment_id)
        if query.debit_note_id is not None:
            statement = statement.where(alloc.debit_note_id == query.debit_note_id)
        if not query.include_reversed:
            statement = statement.where(alloc.is_active)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    SupplierInvoice.invoice_no.contains(term, autoescape=True),
                    SupplierInvoice.supplier_invoice_no.contains(term, autoescape=True),
                    SupplierPayment.payment_no.contains(term, autoescape=True),
                    SupplierPayment.reference_no.contains(term, autoescape=True),
                    DebitNote.debit_note_no.contains(term, autoescape=True),
                )
            )
        statement = statement.order_by(alloc.allocated_on.desc(), alloc.id.desc())
        return self._page(statement, query, AllocationOut.model_validate)

    def _refresh_invoice(self, invoice_id: int) -> None:
        invoice = self._db.get(SupplierInvoice, invoice_id)
        assert invoice is not None
        paid = allocated_to_invoice(self._db, invoice.id)
        invoice.amount_paid = paid
        invoice.status = "Paid" if paid >= invoice.total else ("Part paid" if paid > 0 else "Posted")
        invoice.updated_at = now()
        invoice.updated_by_user_id = self._actor.id

    # ================================================================ helpers

    def _need_direct(self) -> None:
        if not self._actor.can(INVOICE_DIRECT):
            raise Forbidden("Billing without a GRN needs the 'invoices without GRN' permission.")

    def _branches(self, column: Any) -> Any:
        return column.in_(self._actor.branch_ids) if self._actor.branch_ids is not None else column.is_not(None)

    @staticmethod
    def _filtered(statement: Any, query: AccountQuery, supplier: Any, branch: Any, day: Any) -> Any:
        if query.supplier_id is not None:
            statement = statement.where(supplier == query.supplier_id)
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


def _used(column: Any, value: int) -> Any:
    return select(func.coalesce(func.sum(SupplierAllocation.amount), 0)).where(
        column == value, SupplierAllocation.is_active
    )


def _qty(value: Decimal) -> str:
    text = format(value.quantize(_QTY), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text
