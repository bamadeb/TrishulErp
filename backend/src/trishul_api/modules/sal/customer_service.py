"""Customer accounts (the existing core.customer master seen from sales): balance, credit terms, customer
branches (core.customer_site), statement, open items, plus the dropdowns and item price lookup the sales
screens share.

Balance = opening balance + posted invoices - posted receipts. Allocations don't change it: they record
which invoice a receipt settles. Orders and deliveries appear on the statement for information only.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, NotFound
from trishul_api.common.paging import order_by_sort
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    Branch,
    CreditLimitChange,
    Customer,
    CustomerAllocation,
    CustomerSite,
    DeliveryNote,
    GstRate,
    HsnSac,
    Item,
    Location,
    LotBalance,
    PaymentTerms,
    PriceList,
    PriceListItem,
    Principal,
    Receipt,
    SalesInvoice,
    SalesOrder,
    State,
    Uom,
)
from trishul_api.modules.inv.common import now, visible_location
from trishul_api.modules.sal.common import (
    ZERO,
    balance_of,
    err,
    invoiced_total,
    received_total,
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
    CustomerStatementEntry,
    CustomerStatementQuery,
    DispatchLocationOption,
    ItemSaleInfo,
    OpenReceipt,
    OpenSalesInvoice,
    SalesFormOptions,
    SalesOption,
    SaleStockAt,
)

OPEN_ORDER = ("Pending approval", "Approved", "Part delivered", "Delivered", "Part invoiced")
_BRANCH_FIELDS = (
    "site_code",
    "site_name",
    "address",
    "billing_address",
    "state_id",
    "billing_state_id",
    "gstin",
    "site_contact_name",
    "site_contact_phone",
    "email",
)


def _branch_count() -> Any:
    return (
        select(func.count(CustomerSite.id))
        .where(CustomerSite.customer_id == Customer.id, CustomerSite.is_active)
        .correlate(Customer)
        .scalar_subquery()
    )


class CustomerAccountService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ accounts

    def _select(self) -> Select[*tuple[Any, ...]]:
        return (
            select(
                Customer.id,
                Customer.code,
                Customer.name,
                Customer.customer_type,
                Customer.gstin,
                Customer.primary_phone,
                State.name.label("billing_state_name"),
                Customer.payment_terms_id,
                PaymentTerms.description.label("payment_terms"),
                Customer.credit_limit,
                balance_of(Customer.id).label("balance"),
                _branch_count().label("branch_count"),
                Customer.is_active,
            )
            .outerjoin(State, State.id == Customer.billing_state_id)
            .outerjoin(PaymentTerms, PaymentTerms.id == Customer.payment_terms_id)
        )

    def search(self, query: CustomerAccountQuery) -> Page[CustomerAccount]:
        statement = self._select()
        if query.status != "all":
            statement = statement.where(Customer.is_active == (query.status == "active"))
        if query.with_balance:
            statement = statement.where(balance_of(Customer.id) != 0)
        if query.over_limit:
            statement = statement.where(
                Customer.credit_limit.is_not(None), balance_of(Customer.id) > Customer.credit_limit
            )
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Customer.code.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                    Customer.gstin.contains(term, autoescape=True),
                    Customer.primary_phone.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {"code": Customer.code, "name": Customer.name, "balance": balance_of(Customer.id)},
            default="name",
            tiebreaker=Customer.id.asc(),
        )
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = (
            self._db.execute(statement.offset((query.page - 1) * query.page_size).limit(query.page_size))
            .mappings()
            .all()
        )
        return Page(
            items=[CustomerAccount.model_validate(r) for r in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def get(self, customer_id: int) -> CustomerAccountDetail:
        customer = self._require(customer_id)
        row = self._db.execute(self._select().where(Customer.id == customer_id)).mappings().one()
        invoiced = Decimal(self._db.scalar(select(invoiced_total(customer.id))) or 0)
        received = Decimal(self._db.scalar(select(received_total(customer.id))) or 0)
        items = self.open_items(customer_id)
        today = date.today()
        balance = Decimal(row["balance"])
        open_orders = self._db.scalar(
            select(func.count(SalesOrder.id)).where(
                SalesOrder.customer_id == customer.id, SalesOrder.status.in_(OPEN_ORDER)
            )
        )
        return CustomerAccountDetail.model_validate(
            {
                **row,
                "billing_address": customer.billing_address,
                "email": customer.email,
                "pan": customer.pan,
                "opening_balance": customer.opening_balance,
                "opening_balance_date": customer.opening_balance_date,
                "invoiced": invoiced,
                "received": received,
                "unallocated": sum((r.unallocated for r in items.receipts), ZERO),
                "overdue": sum(
                    (i.outstanding for i in items.invoices if i.due_date is not None and i.due_date < today), ZERO
                ),
                "available_credit": customer.credit_limit - balance if customer.credit_limit is not None else None,
                "open_orders": open_orders or 0,
                "row_version": customer.row_version,
            }
        )

    def update_terms(self, customer_id: int, expected: bytes, data: CreditTermsUpdate) -> CustomerAccountDetail:
        customer = self._require(customer_id)
        check_row_version(customer.row_version, expected)
        fields = data.model_fields_set - {"reason"}
        terms_id = data.payment_terms_id
        if "payment_terms_id" in fields and terms_id is not None and self._db.get(PaymentTerms, terms_id) is None:
            raise err("paymentTermsId", "Choose payment terms from the list.")
        old_limit, old_terms = customer.credit_limit, customer.payment_terms_id
        if "payment_terms_id" in fields:
            customer.payment_terms_id = data.payment_terms_id
        if "credit_limit" in fields:
            customer.credit_limit = data.credit_limit
        if "opening_balance" in fields and data.opening_balance is not None:
            customer.opening_balance = data.opening_balance
        if "opening_balance_date" in fields:
            customer.opening_balance_date = data.opening_balance_date
        if (old_limit, old_terms) != (customer.credit_limit, customer.payment_terms_id):
            self._db.add(
                CreditLimitChange(
                    customer_id=customer.id,
                    old_credit_limit=old_limit,
                    new_credit_limit=customer.credit_limit,
                    old_credit_status_id=customer.credit_status_id,
                    new_credit_status_id=customer.credit_status_id,
                    old_payment_terms_id=old_terms,
                    new_payment_terms_id=customer.payment_terms_id,
                    effective_from=date.today(),
                    reason=data.reason,
                    approved_by_user_id=self._actor.id,
                    approved_at=now(),
                    created_by_user_id=self._actor.id,
                )
            )
        customer.updated_at = now()
        customer.updated_by_user_id = self._actor.id
        self._db.flush()
        self._db.commit()
        return self.get(customer.id)

    # ------------------------------------------------------------------ customer branches

    def branches(self, customer_id: int, include_inactive: bool = False) -> list[CustomerBranchOut]:
        self._require(customer_id)
        statement = (
            select(CustomerSite, State.name)
            .outerjoin(State, State.id == CustomerSite.state_id)
            .where(CustomerSite.customer_id == customer_id)
            .order_by(CustomerSite.is_default.desc(), CustomerSite.site_name)
        )
        if not include_inactive:
            statement = statement.where(CustomerSite.is_active)
        return [self._branch_out(site, state) for site, state in self._db.execute(statement).all()]

    @staticmethod
    def _branch_out(site: CustomerSite, state_name: str | None) -> CustomerBranchOut:
        return CustomerBranchOut.model_validate(
            {**{f: getattr(site, f) for f in (*_BRANCH_FIELDS, "id", "customer_id", "is_default", "is_active",
                                               "row_version")}, "state_name": state_name}
        )  # fmt: skip

    def create_branch(self, customer_id: int, data: CustomerBranchCreate) -> CustomerBranchOut:
        customer = self._require(customer_id)
        self._check_branch(customer.id, data, None)
        site = CustomerSite(
            customer_id=customer.id,
            is_default=bool(data.is_default),
            created_by_user_id=self._actor.id,
            **{f: getattr(data, f) for f in _BRANCH_FIELDS},
        )
        if site.site_code:
            site.site_code = site.site_code.upper()
        if site.is_default or not self._db.scalar(
            select(CustomerSite.id).where(CustomerSite.customer_id == customer.id, CustomerSite.is_active).limit(1)
        ):
            self._clear_default(customer.id)
            site.is_default = True
        self._db.add(site)
        self._save_branch()
        return self._one_branch(site.id)

    def update_branch(self, site_id: int, expected: bytes, data: CustomerBranchUpdate) -> CustomerBranchOut:
        site = self._db.get(CustomerSite, site_id)
        if site is None:
            raise NotFound("Customer branch not found.")
        check_row_version(site.row_version, expected)
        self._check_branch(site.customer_id, data, site.id)
        for field in (*_BRANCH_FIELDS, "is_active"):
            if field in data.model_fields_set:
                value = getattr(data, field)
                if value is None and field in ("site_name", "address", "is_active"):
                    continue
                setattr(site, field, value.upper() if field == "site_code" and value else value)
        if data.is_default:
            self._clear_default(site.customer_id, keep=site.id)
            site.is_default = True
        site.updated_at = now()
        site.updated_by_user_id = self._actor.id
        self._save_branch()
        return self._one_branch(site.id)

    def _one_branch(self, site_id: int) -> CustomerBranchOut:
        site, state = self._db.execute(
            select(CustomerSite, State.name)
            .outerjoin(State, State.id == CustomerSite.state_id)
            .where(CustomerSite.id == site_id)
        ).one()
        return self._branch_out(site, state)

    def _check_branch(self, customer_id: int, data: Any, site_id: int | None) -> None:
        for field, name in (("state_id", "stateId"), ("billing_state_id", "billingStateId")):
            value = getattr(data, field)
            if value is not None and self._db.get(State, value) is None:
                raise err(name, "Choose a state from the list.")
        if data.site_code:
            taken = self._db.scalar(
                select(CustomerSite.id).where(
                    CustomerSite.customer_id == customer_id,
                    CustomerSite.site_code == data.site_code.upper(),
                    CustomerSite.id != (site_id or 0),
                )
            )
            if taken is not None:
                raise AlreadyExists(f"Branch code {data.site_code.upper()} is already used for this customer.")

    def _clear_default(self, customer_id: int, keep: int | None = None) -> None:
        for other in self._db.scalars(
            select(CustomerSite).where(CustomerSite.customer_id == customer_id, CustomerSite.is_default)
        ).all():
            if other.id != keep:
                other.is_default = False

    def _save_branch(self) -> None:
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists("The branch could not be saved; its code may already be in use.") from error

    # ------------------------------------------------------------------ open items and statement

    def open_items(self, customer_id: int) -> CustomerOpenItems:
        self._require(customer_id)
        allocated = (
            select(func.coalesce(func.sum(CustomerAllocation.amount), 0))
            .where(CustomerAllocation.sales_invoice_id == SalesInvoice.id, CustomerAllocation.is_active)
            .correlate(SalesInvoice)
            .scalar_subquery()
        )
        today = date.today()
        invoices = []
        for invoice, done in self._db.execute(
            select(SalesInvoice, allocated)
            .where(SalesInvoice.customer_id == customer_id, SalesInvoice.status.in_(("Posted", "Part paid")))
            .order_by(SalesInvoice.due_date, SalesInvoice.invoice_date, SalesInvoice.id)
        ).all():
            outstanding = invoice.total - Decimal(done or 0)
            if outstanding <= 0:
                continue
            invoices.append(
                OpenSalesInvoice(
                    id=invoice.id,
                    invoice_no=invoice.invoice_no,
                    invoice_date=invoice.invoice_date,
                    due_date=invoice.due_date,
                    sales_order_id=invoice.sales_order_id,
                    total=invoice.total,
                    allocated=Decimal(done or 0),
                    outstanding=outstanding,
                    overdue_days=max((today - invoice.due_date).days, 0) if invoice.due_date else 0,
                )
            )
        used = (
            select(func.coalesce(func.sum(CustomerAllocation.amount), 0))
            .where(CustomerAllocation.receipt_id == Receipt.id, CustomerAllocation.is_active)
            .correlate(Receipt)
            .scalar_subquery()
        )
        receipts = []
        for receipt, order_no, done in self._db.execute(
            select(Receipt, SalesOrder.order_no, used)
            .outerjoin(SalesOrder, SalesOrder.id == Receipt.sales_order_id)
            .where(Receipt.customer_id == customer_id, Receipt.status == "Posted")
            .order_by(Receipt.receipt_date, Receipt.id)
        ).all():
            left = receipt.amount - Decimal(done or 0)
            if left > 0:
                receipts.append(
                    OpenReceipt(
                        id=receipt.id,
                        receipt_no=receipt.receipt_no,
                        receipt_date=receipt.receipt_date,
                        receipt_type=receipt.receipt_type,
                        sales_order_id=receipt.sales_order_id,
                        order_no=order_no,
                        reference_no=receipt.reference_no,
                        amount=receipt.amount,
                        allocated=Decimal(done or 0),
                        unallocated=left,
                    )
                )
        return CustomerOpenItems(customer_id=customer_id, invoices=invoices, receipts=receipts)

    def statement(self, customer_id: int, query: CustomerStatementQuery) -> CustomerStatement:
        customer = self._require(customer_id)
        to_date = query.to_date or date.today()
        entries = self._entries(customer_id, to_date)
        opening = customer.opening_balance
        if query.from_date is not None:
            for entry in entries:
                if entry.date < query.from_date:
                    opening += entry.debit - entry.credit
            entries = [e for e in entries if e.date >= query.from_date]
        balance = opening
        for entry in entries:
            if entry.memo_amount is None and entry.entry_type in ("Invoice", "Receipt"):
                balance += entry.debit - entry.credit
                entry.balance = balance
        return CustomerStatement(
            customer_id=customer.id,
            customer_name=customer.name,
            from_date=query.from_date,
            to_date=to_date,
            opening_balance=opening,
            closing_balance=balance,
            total_debit=sum((e.debit for e in entries), ZERO),
            total_credit=sum((e.credit for e in entries), ZERO),
            entries=entries,
        )

    def _entries(self, customer_id: int, to_date: date) -> list[CustomerStatementEntry]:
        entries: list[CustomerStatementEntry] = []
        for order in self._db.scalars(
            select(SalesOrder).where(
                SalesOrder.customer_id == customer_id,
                SalesOrder.order_date <= to_date,
                SalesOrder.status.not_in(("Draft", "Cancelled")),
            )
        ).all():
            entries.append(
                CustomerStatementEntry(
                    date=order.order_date, entry_type="Sales order", document_id=order.id,
                    document_no=order.order_no, reference=order.customer_po_no,
                    description=f"Order ({order.status})", debit=ZERO, credit=ZERO, balance=None,
                    memo_amount=order.total,
                )
            )  # fmt: skip
        for note in self._db.scalars(
            select(DeliveryNote).where(
                DeliveryNote.customer_id == customer_id,
                DeliveryNote.delivery_date <= to_date,
                DeliveryNote.status != "Cancelled",
            )
        ).all():
            entries.append(
                CustomerStatementEntry(
                    date=note.delivery_date, entry_type="Delivery", document_id=note.id,
                    document_no=note.delivery_no, reference=note.delivery_reference,
                    description="Goods delivered", debit=ZERO, credit=ZERO, balance=None, memo_amount=None,
                )
            )  # fmt: skip
        for invoice in self._db.scalars(
            select(SalesInvoice).where(
                SalesInvoice.customer_id == customer_id,
                SalesInvoice.status.not_in(("Cancelled", "Draft")),
                SalesInvoice.invoice_date <= to_date,
            )
        ).all():
            due = f", due {invoice.due_date:%d %b %Y}" if invoice.due_date else ""
            entries.append(
                CustomerStatementEntry(
                    date=invoice.invoice_date, entry_type="Invoice", document_id=invoice.id,
                    document_no=invoice.invoice_no, reference=None, description=f"Sales invoice{due}",
                    debit=invoice.total, credit=ZERO, balance=None, memo_amount=None,
                )
            )  # fmt: skip
        for receipt in self._db.scalars(
            select(Receipt).where(
                Receipt.customer_id == customer_id, Receipt.status == "Posted", Receipt.receipt_date <= to_date
            )
        ).all():
            entries.append(
                CustomerStatementEntry(
                    date=receipt.receipt_date, entry_type="Receipt", document_id=receipt.id,
                    document_no=receipt.receipt_no, reference=receipt.reference_no,
                    description=f"Receipt ({receipt.receipt_type}, {receipt.payment_mode})", debit=ZERO,
                    credit=receipt.amount, balance=None, memo_amount=None,
                )
            )  # fmt: skip
        rank = {"Sales order": 0, "Delivery": 1, "Invoice": 2, "Receipt": 3}
        entries.sort(key=lambda e: (e.date, rank[e.entry_type], e.document_no))
        return entries

    # ------------------------------------------------------------------ shared lookups

    def form_options(self, scope: RequestScope) -> SalesFormOptions:
        # Every result is read with .all() before the next query: SQL Server allows one open result per connection.
        brands = self._db.execute(
            select(Principal.id, Principal.code, Principal.name).where(Principal.is_active).order_by(Principal.name)
        ).all()
        branches = self._db.execute(
            select(Branch.id, Branch.code, Branch.name).where(Branch.is_active).order_by(Branch.name)
        ).all()
        locations = (
            self._db.execute(
                select(Location.id, Location.code, Location.name, Location.branch_id, Branch.name.label("branch_name"))
                .join(Branch, Branch.id == Location.branch_id)
                .where(Location.is_active, Location.is_stock_location, visible_location(self._actor))
                .order_by(Branch.name, Location.name)
            )
            .mappings()
            .all()
        )
        terms = self._db.execute(
            select(PaymentTerms.id, PaymentTerms.code, PaymentTerms.description)
            .where(PaymentTerms.is_active)
            .order_by(PaymentTerms.days_before_due, PaymentTerms.code)
        ).all()
        states = self._db.execute(select(State.id, State.gst_state_code, State.name).order_by(State.name)).all()
        brand_options = [SalesOption(id=i, code=c, name=n) for i, c, n in brands if self._actor.can_see_principal(i)]
        branch_options = [SalesOption(id=i, code=c, name=n) for i, c, n in branches if self._actor.can_use_branch(i)]
        default_branch = scope.branch_id if scope.branch_id is not None else self._actor.default_branch_id
        return SalesFormOptions(
            brands=brand_options,
            branches=branch_options,
            locations=[DispatchLocationOption.model_validate(r) for r in locations],
            payment_terms=[SalesOption(id=i, code=c, name=d) for i, c, d in terms],
            states=[SalesOption(id=i, code=c, name=n) for i, c, n in states],
            default_branch_id=default_branch if any(b.id == default_branch for b in branch_options) else None,
            default_brand_id=scope.principal_id
            if scope.principal_id is not None
            else (brand_options[0].id if len(brand_options) == 1 else None),
        )

    def item_info(self, item_id: int, principal_id: int | None) -> ItemSaleInfo:
        row = self._db.execute(
            select(Item, Uom.code, HsnSac.code, GstRate.total_rate)
            .join(Uom, Uom.id == Item.uom_id)
            .outerjoin(HsnSac, HsnSac.id == Item.hsn_sac_id)
            .outerjoin(GstRate, GstRate.id == HsnSac.gst_rate_id)
            .where(Item.id == item_id)
        ).first()
        if row is None:
            raise NotFound("Item not found.")
        item, uom_code, hsn, gst_pct = row
        if item.principal_id is not None and not self._actor.can_see_principal(item.principal_id):
            raise NotFound("Item not found.")
        today = date.today()
        brand = principal_id if principal_id is not None else item.principal_id
        price = self._db.execute(
            select(PriceListItem.unit_price, PriceList.name)
            .join(PriceList, PriceList.id == PriceListItem.price_list_id)
            .where(
                PriceListItem.item_id == item.id,
                PriceListItem.is_active,
                PriceList.is_active,
                or_(PriceList.valid_from.is_(None), PriceList.valid_from <= today),
                or_(PriceList.valid_to.is_(None), PriceList.valid_to >= today),
                or_(PriceList.principal_id.is_(None), PriceList.principal_id == brand),
            )
            .order_by(
                case((PriceList.principal_id.is_(None), 1), else_=0),  # the brand's own list first
                case((PriceList.price_list_type == "Retail", 0), else_=1),
                PriceListItem.min_qty,
                PriceList.id,
            )
            .limit(1)
        ).first()
        stock = [
            SaleStockAt.model_validate(r)
            for r in self._db.execute(
                select(
                    Location.id.label("location_id"),
                    Location.name.label("location_name"),
                    Branch.name.label("branch_name"),
                    func.sum(LotBalance.qty_on_hand).label("qty_on_hand"),
                )
                .join(Location, Location.id == LotBalance.location_id)
                .join(Branch, Branch.id == Location.branch_id)
                .where(LotBalance.item_id == item.id, LotBalance.qty_on_hand > 0, visible_location(self._actor))
                .group_by(Location.id, Location.name, Branch.name)
                .order_by(Branch.name, Location.name)
            )
            .mappings()
            .all()
        ]
        return ItemSaleInfo(
            item_id=item.id,
            item_code=item.item_code,
            description=item.description,
            item_type=item.item_type,
            principal_id=item.principal_id,
            uom_id=item.uom_id,
            uom_code=uom_code,
            hsn_code=hsn,
            gst_pct=gst_pct,
            mrp=item.mrp,
            price=price[0] if price else None,
            price_list=price[1] if price else None,
            stock=stock,
        )

    # ------------------------------------------------------------------ helpers

    def _require(self, customer_id: int) -> Customer:
        customer = self._db.get(Customer, customer_id)
        if customer is None:
            raise NotFound("Customer not found.")
        return customer
