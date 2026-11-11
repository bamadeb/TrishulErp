"""Suppliers (core.supplier): the master, the balance we owe each one, their statement and open items.

Balance = opening balance + invoices - payments - credit notes (posted documents only). Allocations
don't change the balance: they only record which invoice a payment or credit note settles.
Purchase orders and GRNs appear on the statement for information but carry no money.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.common.paging import order_by_sort
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    DebitNote,
    Grn,
    GrnLine,
    PaymentTerms,
    PurchaseOrder,
    State,
    Supplier,
    SupplierAllocation,
    SupplierInvoice,
    SupplierPayment,
)
from trishul_api.modules.inv.common import default_company, now
from trishul_api.modules.pur.common import ZERO, money
from trishul_api.modules.pur.supplier_schemas import (
    OpenCredit,
    OpenInvoice,
    Option,
    StatementEntry,
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

_FIELDS = (
    "supplier_type",
    "gstin",
    "gst_registration_type",
    "pan",
    "phone",
    "email",
    "address",
    "contact_person",
    "state_id",
    "payment_terms_id",
    "credit_limit",
    "bank_name",
    "bank_account_no",
    "ifsc",
    "opening_balance",
    "opening_balance_date",
)
_NOT_NULL = {"supplier_type", "opening_balance", "name", "is_active"}


def invoiced_total(supplier_id: Any) -> ColumnElement[Any]:
    return (
        select(func.coalesce(func.sum(SupplierInvoice.total), 0))
        .where(SupplierInvoice.supplier_id == supplier_id, SupplierInvoice.status != "Cancelled")
        .scalar_subquery()
    )


def paid_total(supplier_id: Any) -> ColumnElement[Any]:
    return (
        select(func.coalesce(func.sum(SupplierPayment.amount), 0))
        .where(SupplierPayment.supplier_id == supplier_id, SupplierPayment.status == "Posted")
        .scalar_subquery()
    )


def credited_total(supplier_id: Any) -> ColumnElement[Any]:
    return (
        select(func.coalesce(func.sum(DebitNote.total), 0))
        .where(DebitNote.supplier_id == supplier_id, DebitNote.status == "Posted")
        .scalar_subquery()
    )


def balance_of(supplier_id: Any) -> ColumnElement[Any]:
    return (
        Supplier.opening_balance + invoiced_total(supplier_id) - paid_total(supplier_id) - credited_total(supplier_id)
    )


def _mask(account: str | None) -> str | None:
    return f"{'*' * max(len(account) - 4, 0)}{account[-4:]}" if account else None


class SupplierService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ reads

    def _select(self) -> Select[*tuple[Any, ...]]:
        return (
            select(
                Supplier.id,
                Supplier.code,
                Supplier.name,
                Supplier.supplier_type,
                Supplier.gstin,
                Supplier.pan,
                Supplier.phone,
                Supplier.email,
                Supplier.address,
                Supplier.contact_person,
                Supplier.state_id,
                State.name.label("state_name"),
                Supplier.payment_terms_id,
                PaymentTerms.description.label("payment_terms"),
                balance_of(Supplier.id).label("balance"),
                Supplier.is_active,
                Supplier.row_version,
            )
            .outerjoin(State, State.id == Supplier.state_id)
            .outerjoin(PaymentTerms, PaymentTerms.id == Supplier.payment_terms_id)
        )

    def search(self, query: SupplierQuery) -> Page[SupplierOut]:
        statement = self._select()
        if query.status != "all":
            statement = statement.where(Supplier.is_active == (query.status == "active"))
        if query.with_balance:
            statement = statement.where(balance_of(Supplier.id) != 0)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Supplier.code.contains(term, autoescape=True),
                    Supplier.name.contains(term, autoescape=True),
                    Supplier.gstin.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {"code": Supplier.code, "name": Supplier.name, "balance": balance_of(Supplier.id)},
            default="name",
            tiebreaker=Supplier.id.asc(),
        )
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = (
            self._db.execute(statement.offset((query.page - 1) * query.page_size).limit(query.page_size))
            .mappings()
            .all()
        )
        return Page(
            items=[SupplierOut.model_validate(r) for r in rows], total=total, page=query.page, page_size=query.page_size
        )

    def get(self, supplier_id: int) -> SupplierDetail:
        supplier = self._require(supplier_id)
        row = self._db.execute(self._select().where(Supplier.id == supplier_id)).mappings().one()
        invoiced = Decimal(self._db.scalar(select(invoiced_total(supplier.id))) or 0)
        paid = Decimal(self._db.scalar(select(paid_total(supplier.id))) or 0)
        credited = Decimal(self._db.scalar(select(credited_total(supplier.id))) or 0)
        items = self.open_items(supplier_id)
        today = date.today()
        return SupplierDetail.model_validate(
            {
                **row,
                "gst_registration_type": supplier.gst_registration_type,
                "credit_limit": supplier.credit_limit,
                "bank_name": supplier.bank_name,
                "bank_account_no": _mask(supplier.bank_account_no),
                "ifsc": supplier.ifsc,
                "opening_balance": supplier.opening_balance,
                "opening_balance_date": supplier.opening_balance_date,
                "invoiced": invoiced,
                "paid": paid,
                "credited": credited,
                "unallocated": sum((c.unallocated for c in items.credits), ZERO),
                "overdue": sum(
                    (i.outstanding for i in items.invoices if i.due_date is not None and i.due_date < today), ZERO
                ),
            }
        )

    def form_options(self) -> SupplierFormOptions:
        # .all() before the next query: SQL Server allows one open result per connection.
        states = (
            self._db.execute(select(State.id, State.gst_state_code.label("code"), State.name).order_by(State.name))
            .mappings()
            .all()
        )
        terms = (
            self._db.execute(
                select(PaymentTerms.id, PaymentTerms.code, PaymentTerms.description.label("name"))
                .where(PaymentTerms.is_active)
                .order_by(PaymentTerms.days_before_due, PaymentTerms.code)
            )
            .mappings()
            .all()
        )
        return SupplierFormOptions(
            states=[Option.model_validate(r) for r in states],
            payment_terms=[Option.model_validate(r) for r in terms],
        )

    # ------------------------------------------------------------------ open items and statement

    def open_items(self, supplier_id: int) -> SupplierOpenItems:
        self._require(supplier_id)
        allocated = (
            select(func.coalesce(func.sum(SupplierAllocation.amount), 0))
            .where(SupplierAllocation.supplier_invoice_id == SupplierInvoice.id, SupplierAllocation.is_active)
            .correlate(SupplierInvoice)
            .scalar_subquery()
        )
        today = date.today()
        invoices = []
        for row in self._db.execute(
            select(SupplierInvoice, allocated.label("allocated"))
            .where(
                SupplierInvoice.supplier_id == supplier_id,
                SupplierInvoice.status.in_(("Posted", "Part paid")),
            )
            .order_by(SupplierInvoice.due_date, SupplierInvoice.supplier_invoice_date, SupplierInvoice.id)
        ).all():
            invoice, done = row[0], Decimal(row[1] or 0)
            outstanding = invoice.total - done
            if outstanding <= 0:
                continue
            invoices.append(
                OpenInvoice(
                    id=invoice.id,
                    invoice_no=invoice.invoice_no,
                    supplier_invoice_no=invoice.supplier_invoice_no,
                    supplier_invoice_date=invoice.supplier_invoice_date,
                    due_date=invoice.due_date,
                    total=invoice.total,
                    allocated=done,
                    outstanding=outstanding,
                    overdue_days=max((today - invoice.due_date).days, 0) if invoice.due_date else 0,
                )
            )
        credits = [*self._open_payments(supplier_id), *self._open_notes(supplier_id)]
        credits.sort(key=lambda c: (c.date, c.document_no))
        return SupplierOpenItems(supplier_id=supplier_id, invoices=invoices, credits=credits)

    def _open_payments(self, supplier_id: int) -> list[OpenCredit]:
        used = (
            select(func.coalesce(func.sum(SupplierAllocation.amount), 0))
            .where(SupplierAllocation.supplier_payment_id == SupplierPayment.id, SupplierAllocation.is_active)
            .correlate(SupplierPayment)
            .scalar_subquery()
        )
        rows = self._db.execute(
            select(SupplierPayment, used).where(
                SupplierPayment.supplier_id == supplier_id, SupplierPayment.status == "Posted"
            )
        ).all()
        return [
            OpenCredit(
                kind="Payment",
                id=p.id,
                document_no=p.payment_no,
                date=p.payment_date,
                reference=p.reference_no,
                amount=p.amount,
                allocated=Decimal(u or 0),
                unallocated=p.amount - Decimal(u or 0),
            )
            for p, u in rows
            if p.amount - Decimal(u or 0) > 0
        ]

    def _open_notes(self, supplier_id: int) -> list[OpenCredit]:
        used = (
            select(func.coalesce(func.sum(SupplierAllocation.amount), 0))
            .where(SupplierAllocation.debit_note_id == DebitNote.id, SupplierAllocation.is_active)
            .correlate(DebitNote)
            .scalar_subquery()
        )
        rows = self._db.execute(
            select(DebitNote, used).where(DebitNote.supplier_id == supplier_id, DebitNote.status == "Posted")
        ).all()
        return [
            OpenCredit(
                kind="Credit note",
                id=n.id,
                document_no=n.debit_note_no,
                date=n.note_date,
                reference=n.supplier_note_no,
                amount=n.total,
                allocated=Decimal(u or 0),
                unallocated=n.total - Decimal(u or 0),
            )
            for n, u in rows
            if n.total - Decimal(u or 0) > 0
        ]

    def statement(self, supplier_id: int, query: StatementQuery) -> SupplierStatement:
        supplier = self._require(supplier_id)
        to_date = query.to_date or date.today()
        entries = self._entries(supplier_id, to_date)
        opening = supplier.opening_balance
        if query.from_date is not None:
            for entry in entries:
                if entry.date < query.from_date:
                    opening += entry.credit - entry.debit
            entries = [e for e in entries if e.date >= query.from_date]
        balance = opening
        for entry in entries:
            if entry.memo_amount is None:
                balance += entry.credit - entry.debit
                entry.balance = balance
        return SupplierStatement(
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            from_date=query.from_date,
            to_date=to_date,
            opening_balance=opening,
            closing_balance=balance,
            total_debit=sum((e.debit for e in entries), ZERO),
            total_credit=sum((e.credit for e in entries), ZERO),
            entries=entries,
        )

    def _entries(self, supplier_id: int, to_date: date) -> list[StatementEntry]:
        entries: list[StatementEntry] = []
        for po in self._db.scalars(
            select(PurchaseOrder).where(
                PurchaseOrder.supplier_id == supplier_id,
                PurchaseOrder.po_date <= to_date,
                PurchaseOrder.status.not_in(("Draft", "Cancelled")),
            )
        ).all():
            entries.append(
                StatementEntry(
                    date=po.po_date,
                    entry_type="Purchase order",
                    document_id=po.id,
                    document_no=po.po_no,
                    reference=None,
                    description=f"Order ({po.status})",
                    debit=ZERO,
                    credit=ZERO,
                    balance=None,
                    memo_amount=po.total,
                )
            )
        grn_value = (
            select(func.coalesce(func.sum(GrnLine.qty_accepted * GrnLine.unit_cost), 0))
            .where(GrnLine.grn_id == Grn.id)
            .correlate(Grn)
            .scalar_subquery()
        )
        for grn, value in self._db.execute(
            select(Grn, grn_value).where(Grn.supplier_id == supplier_id, Grn.grn_date <= to_date)
        ).all():
            entries.append(
                StatementEntry(
                    date=grn.grn_date,
                    entry_type="GRN",
                    document_id=grn.id,
                    document_no=grn.grn_no,
                    reference=grn.supplier_invoice_no,
                    description="Goods received",
                    debit=ZERO,
                    credit=ZERO,
                    balance=None,
                    memo_amount=money(Decimal(value or 0)),
                )
            )
        for invoice in self._db.scalars(
            select(SupplierInvoice).where(
                SupplierInvoice.supplier_id == supplier_id,
                SupplierInvoice.status != "Cancelled",
                SupplierInvoice.supplier_invoice_date <= to_date,
            )
        ).all():
            entries.append(
                StatementEntry(
                    date=invoice.supplier_invoice_date,
                    entry_type="Invoice",
                    document_id=invoice.id,
                    document_no=invoice.invoice_no,
                    reference=invoice.supplier_invoice_no,
                    description="Supplier invoice" + (f", due {invoice.due_date:%d %b %Y}" if invoice.due_date else ""),
                    debit=ZERO,
                    credit=invoice.total,
                    balance=None,
                    memo_amount=None,
                )
            )
        for payment in self._db.scalars(
            select(SupplierPayment).where(
                SupplierPayment.supplier_id == supplier_id,
                SupplierPayment.status == "Posted",
                SupplierPayment.payment_date <= to_date,
            )
        ).all():
            entries.append(
                StatementEntry(
                    date=payment.payment_date,
                    entry_type="Payment",
                    document_id=payment.id,
                    document_no=payment.payment_no,
                    reference=payment.reference_no,
                    description=f"Payment ({payment.payment_mode})",
                    debit=payment.amount,
                    credit=ZERO,
                    balance=None,
                    memo_amount=None,
                )
            )
        for note in self._db.scalars(
            select(DebitNote).where(
                DebitNote.supplier_id == supplier_id, DebitNote.status == "Posted", DebitNote.note_date <= to_date
            )
        ).all():
            entries.append(
                StatementEntry(
                    date=note.note_date,
                    entry_type="Credit note",
                    document_id=note.id,
                    document_no=note.debit_note_no,
                    reference=note.supplier_note_no,
                    description=f"Credit note ({note.note_type})",
                    debit=note.total,
                    credit=ZERO,
                    balance=None,
                    memo_amount=None,
                )
            )
        order = {"Purchase order": 0, "GRN": 1, "Invoice": 2, "Credit note": 3, "Payment": 4}
        entries.sort(key=lambda e: (e.date, order[e.entry_type], e.document_no))
        return entries

    # ------------------------------------------------------------------ writes

    def create(self, data: SupplierCreate, scope: RequestScope) -> SupplierDetail:
        code = data.code.upper()
        self._check_code(code)
        self._check_refs(data)
        supplier = Supplier(
            company_id=default_company(self._db, self._actor, scope),
            code=code,
            name=data.name,
            created_by_user_id=self._actor.id,
            **{f: getattr(data, f) for f in _FIELDS if getattr(data, f) is not None},
        )
        if supplier.supplier_type is None:
            supplier.supplier_type = "Parts"
        self._save(supplier)
        return self.get(supplier.id)

    def update(self, supplier_id: int, expected: bytes, data: SupplierUpdate) -> SupplierDetail:
        supplier = self._require(supplier_id)
        check_row_version(supplier.row_version, expected)
        self._check_refs(data)
        for field in (*_FIELDS, "name", "is_active"):
            if field in data.model_fields_set:
                value = getattr(data, field)
                if value is None and field in _NOT_NULL:
                    continue
                setattr(supplier, field, value)
        supplier.updated_at = now()
        supplier.updated_by_user_id = self._actor.id
        self._save(supplier)
        return self.get(supplier.id)

    # ------------------------------------------------------------------ helpers

    def _require(self, supplier_id: int) -> Supplier:
        supplier = self._db.get(Supplier, supplier_id)
        if supplier is None:
            raise NotFound("Supplier not found.")
        return supplier

    def _check_code(self, code: str) -> None:
        if self._db.scalar(select(Supplier.id).where(Supplier.code == code).limit(1)) is not None:
            raise AlreadyExists(f"Supplier code '{code}' is already used.")

    def _check_refs(self, data: SupplierCreate | SupplierUpdate) -> None:
        if data.state_id is not None and self._db.get(State, data.state_id) is None:
            raise ApiError("Choose a state from the list.", errors={"stateId": ["Unknown state."]})
        if data.payment_terms_id is not None and self._db.get(PaymentTerms, data.payment_terms_id) is None:
            raise ApiError("Choose payment terms from the list.", errors={"paymentTermsId": ["Unknown terms."]})

    def _save(self, supplier: Supplier) -> None:
        self._db.add(supplier)
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists("The supplier could not be saved. The code may already be in use.") from error
