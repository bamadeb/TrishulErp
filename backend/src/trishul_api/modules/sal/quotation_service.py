r"""Sales quotations with revisions.

    Draft --submit--> Submitted --accept--> Accepted --convert--> Converted (a draft sales order)
      |                  \--reject--> Rejected
      \--submit (has a discount, submitter can't approve discounts)--> Pending approval
                             --approve--> Submitted   --send back--> Draft
    Submitted past its validity date shows as Expired; it can't be accepted, only revised or rejected.
    revise: Pending approval / Submitted / Accepted / Rejected / Expired --> Draft, version + 1

Every version keeps its own lines (sal.quotation_line.version_no) and a row in sal.quotation_version
(total, what changed), so earlier revisions stay on record. Only a draft is edited, in place.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, case, func, or_, select
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
    Contact,
    Customer,
    CustomerPrincipal,
    CustomerSite,
    Employee,
    HsnSac,
    Item,
    PaymentTerms,
    Principal,
    Quotation,
    QuotationLine,
    QuotationVersion,
    SalesOrder,
    State,
    Uom,
)
from trishul_api.modules.inv.common import now, visible_branch
from trishul_api.modules.pur.words import number_in_words
from trishul_api.modules.sal.common import (
    QUOTATION_APPROVE,
    ZERO,
    active_branch,
    active_customer,
    active_principal,
    customer_branch,
    err,
    is_inter_state,
    place_of_supply,
    require,
    rupees,
)
from trishul_api.modules.sal.lines import ItemLineIn, PricedLineOut, net_price, price_lines
from trishul_api.modules.sal.order_schemas import OrderCreate, OrderDetail
from trishul_api.modules.sal.order_service import SalesOrderService
from trishul_api.modules.sal.quotation_schemas import (
    ConvertQuotation,
    QuotationCreate,
    QuotationDetail,
    QuotationListItem,
    QuotationNote,
    QuotationQuery,
    QuotationState,
)

REVISABLE = ("Pending approval", "Submitted", "Accepted", "Rejected")
VALIDITY_DAYS = 30


def amount_in_words(amount: Decimal) -> str:
    """Decimal('17682') -> 'SEVENTEEN THOUSAND SIX HUNDRED EIGHTY-TWO RUPEES AND ZERO PAISE ONLY' (OEM style)."""
    value = amount.quantize(Decimal("0.01"))
    whole = int(value)
    paise = int((value - whole) * 100)
    return f"{number_in_words(whole)} rupees and {number_in_words(paise)} paise only".upper()


def quotation_state(status: str, valid_until: date | None, today: date) -> QuotationState:
    if status == "Submitted" and valid_until is not None and valid_until < today:
        return "Expired"
    if status == "Sent":
        return "Submitted"
    return status  # type: ignore[return-value]


class QuotationService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ list and detail

    def _select(self) -> Select[*tuple[Any, ...]]:
        return (
            select(
                Quotation.id,
                Quotation.quotation_no,
                Quotation.quotation_date,
                Quotation.valid_until,
                Quotation.customer_id,
                Customer.name.label("customer_name"),
                CustomerSite.site_name.label("customer_site_name"),
                Branch.name.label("branch_name"),
                Principal.name.label("principal_name"),
                Quotation.status,
                Quotation.current_version,
                Quotation.total,
                Quotation.created_at,
            )
            .join(Customer, Customer.id == Quotation.customer_id)
            .join(Branch, Branch.id == Quotation.branch_id)
            .join(Principal, Principal.id == Quotation.principal_id)
            .outerjoin(CustomerSite, CustomerSite.id == Quotation.customer_site_id)
            .where(visible_branch(self._actor), *self._brands())
        )

    def _brands(self) -> list[Any]:
        if self._actor.principal_ids is None:
            return []
        return [Quotation.principal_id.in_(self._actor.principal_ids)]

    def search(self, query: QuotationQuery) -> Page[QuotationListItem]:
        statement = self._select()
        today = date.today()
        expired = and_(Quotation.status == "Submitted", Quotation.valid_until < today)
        if query.state == "Expired":
            statement = statement.where(expired)
        elif query.state == "Submitted":
            statement = statement.where(
                Quotation.status.in_(("Submitted", "Sent")),
                or_(Quotation.valid_until.is_(None), Quotation.valid_until >= today),
            )
        elif query.state is not None:
            statement = statement.where(Quotation.status == query.state)
        if query.customer_id is not None:
            statement = statement.where(Quotation.customer_id == query.customer_id)
        if query.branch_id is not None:
            statement = statement.where(Quotation.branch_id == query.branch_id)
        if query.from_date is not None:
            statement = statement.where(Quotation.quotation_date >= query.from_date)
        if query.to_date is not None:
            statement = statement.where(Quotation.quotation_date <= query.to_date)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Quotation.quotation_no.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {
                "quotationDate": Quotation.quotation_date,
                "quotationNo": Quotation.quotation_no,
                "customerName": Customer.name,
                "total": Quotation.total,
                "validUntil": Quotation.valid_until,
            },
            default="-quotationDate",
            tiebreaker=Quotation.id.desc(),
        )
        page = paginate(self._db, statement.add_columns(case((expired, "Expired"), else_=Quotation.status).label(
            "state")), query, QuotationListItem)  # fmt: skip
        for row in page.items:
            row.state = quotation_state(row.status, row.valid_until, today)
        return page

    def get(self, quotation_id: int) -> QuotationDetail:
        quotation = self._visible(quotation_id)
        created, submitted, approved, responded = (aliased(AppUser) for _ in range(4))
        # Contact person on the print: the salesperson, else the employee who made the quotation.
        salesperson, maker = aliased(Employee), aliased(Employee)
        oem_code = (
            select(CustomerPrincipal.oem_customer_code)
            .where(
                CustomerPrincipal.customer_id == Quotation.customer_id,
                CustomerPrincipal.principal_id == Quotation.principal_id,
                CustomerPrincipal.is_active,
            )
            .limit(1)
            .correlate(Quotation)
            .scalar_subquery()
        )
        attention = (
            select(Contact.name)
            .where(Contact.customer_id == Quotation.customer_id, Contact.is_active)
            .order_by(Contact.is_primary.desc(), Contact.id)
            .limit(1)
            .correlate(Quotation)
            .scalar_subquery()
        )
        header = (
            self._db.execute(
                self._select()
                .add_columns(
                    Quotation.principal_id,
                    Quotation.branch_id,
                    Quotation.customer_site_id,
                    Quotation.quotation_type,
                    Company.legal_name.label("company_name"),
                    Company.address.label("company_address"),
                    Branch.address.label("branch_address"),
                    Customer.code.label("customer_code"),
                    func.coalesce(CustomerSite.gstin, Customer.gstin).label("customer_gstin"),
                    func.coalesce(CustomerSite.billing_address, CustomerSite.address, Customer.billing_address).label(
                        "customer_address"
                    ),
                    func.coalesce(CustomerSite.site_contact_phone, Customer.primary_phone).label("customer_phone"),
                    State.name.label("place_of_supply"),
                    Principal.logo_url.label("principal_logo_url"),
                    Branch.phone.label("branch_phone"),
                    Branch.email.label("branch_email"),
                    oem_code.label("customer_oem_code"),
                    Customer.gst_registration_type.label("customer_gst_type"),
                    attention.label("customer_contact_name"),
                    func.coalesce(CustomerSite.billing_address, Customer.billing_address).label("billing_address"),
                    func.coalesce(CustomerSite.address, Customer.billing_address).label("delivery_address"),
                    PaymentTerms.description.label("payment_terms"),
                    func.nullif(
                        func.concat_ws(
                            " ",
                            func.coalesce(salesperson.first_name, maker.first_name),
                            func.coalesce(salesperson.last_name, maker.last_name),
                        ),
                        "",
                    ).label("contact_name"),
                    func.coalesce(salesperson.mobile, maker.mobile).label("contact_phone"),
                    func.coalesce(salesperson.email, maker.email, created.email).label("contact_email"),
                    Quotation.subtotal,
                    Quotation.discount_total,
                    Quotation.cgst,
                    Quotation.sgst,
                    Quotation.igst,
                    Quotation.tax_total,
                    Quotation.other_charges,
                    Quotation.terms,
                    Quotation.remarks,
                    created.username.label("created_by"),
                    submitted.username.label("submitted_by"),
                    Quotation.submitted_at,
                    approved.username.label("approved_by"),
                    Quotation.approved_at,
                    responded.username.label("responded_by"),
                    Quotation.responded_at,
                    Quotation.response_note,
                    Quotation.row_version,
                )
                .join(Company, Company.id == Branch.company_id)
                .join(State, State.id == Quotation.place_of_supply_state_id)
                .outerjoin(PaymentTerms, PaymentTerms.id == Customer.payment_terms_id)
                .outerjoin(salesperson, salesperson.id == Quotation.salesperson_employee_id)
                .outerjoin(created, created.id == Quotation.created_by_user_id)
                .outerjoin(maker, maker.id == created.employee_id)
                .outerjoin(submitted, submitted.id == Quotation.submitted_by_user_id)
                .outerjoin(approved, approved.id == Quotation.approved_by_user_id)
                .outerjoin(responded, responded.id == Quotation.responded_by_user_id)
                .where(Quotation.id == quotation.id)
            )
            .mappings()
            .one()
        )
        lines = [
            PricedLineOut(
                id=line.id,
                line_no=line.line_no,
                item_id=line.item_id,
                item_code=code,
                description=line.description,
                uom_code=uom,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount_pct=line.discount_pct or ZERO,
                gst_pct=line.gst_pct,
                net_price=net_price(line.unit_price, line.discount_pct or ZERO),
                taxable_value=line.taxable_value,
                tax_amount=line.tax_amount,
                line_total=line.line_total,
                hsn_code=hsn,
            )
            for line, code, uom, hsn in self._db.execute(
                select(QuotationLine, Item.item_code, Uom.code, HsnSac.code)
                .outerjoin(Item, Item.id == QuotationLine.item_id)
                .outerjoin(Uom, Uom.id == QuotationLine.uom_id)
                .outerjoin(HsnSac, HsnSac.id == QuotationLine.hsn_sac_id)
                .where(
                    QuotationLine.quotation_id == quotation.id, QuotationLine.version_no == quotation.current_version
                )
                .order_by(QuotationLine.line_no)
            ).all()
        ]
        by = aliased(AppUser)
        versions = [
            {"version_no": v, "total": t, "change_note": n, "created_at": c, "created_by": u}
            for v, t, n, c, u in self._db.execute(
                select(QuotationVersion.version_no, QuotationVersion.total, QuotationVersion.change_note,
                       QuotationVersion.created_at, by.username)
                .outerjoin(by, by.id == QuotationVersion.created_by_user_id)
                .where(QuotationVersion.quotation_id == quotation.id)
                .order_by(QuotationVersion.version_no.desc())
            ).all()
        ]  # fmt: skip
        order = self._db.execute(
            select(SalesOrder.id, SalesOrder.order_no)
            .where(SalesOrder.quotation_id == quotation.id, SalesOrder.status != "Cancelled")
            .order_by(SalesOrder.id.desc())
            .limit(1)
        ).first()
        return QuotationDetail.model_validate(
            {
                **header,
                "state": quotation_state(quotation.status, quotation.valid_until, date.today()),
                "taxable_value": quotation.subtotal - quotation.discount_total,
                "needs_discount_approval": any(line.discount_pct > 0 for line in lines),
                "lines": lines,
                "versions": versions,
                "sales_order_id": order[0] if order else None,
                "order_no": order[1] if order else None,
                "rounded_total": rupees(quotation.total),
                "amount_in_words": amount_in_words(rupees(quotation.total)),
            }
        )

    # ------------------------------------------------------------------ create and change

    def create(self, data: QuotationCreate) -> QuotationDetail:
        branch = active_branch(self._db, self._actor, data.branch_id)
        quotation = Quotation(
            quotation_no=next_document_no(
                self._db, company_id=branch.company_id, document_type="QUOTATION", branch_id=branch.id
            ),
            branch_id=branch.id,
            status="Draft",
            current_version=1,
            subtotal=ZERO,
            discount_total=ZERO,
            tax_total=ZERO,
            total=ZERO,
            created_by_user_id=self._actor.id,
        )
        self._fill(quotation, data)
        self._db.add(quotation)
        self._db.flush()
        self._db.add(QuotationVersion(quotation_id=quotation.id, version_no=1, total=ZERO,
                                      change_note="First version", created_by_user_id=self._actor.id))  # fmt: skip
        self._write_lines(quotation, data)
        self._commit()
        return self.get(quotation.id)

    def update(self, quotation_id: int, expected: bytes, data: QuotationCreate) -> QuotationDetail:
        """Replaces the current version (header and lines). Only a draft can change; revise the others."""
        quotation = self._visible(quotation_id)
        check_row_version(quotation.row_version, expected)
        if quotation.status != "Draft":
            raise Conflict(f"Only a draft quotation can be changed; revise this {quotation.status.lower()} one.")
        if data.branch_id != quotation.branch_id:
            raise err("branchId", "The branch can't change (the quotation number belongs to it).")
        self._fill(quotation, data)
        for line in self._db.scalars(
            select(QuotationLine).where(
                QuotationLine.quotation_id == quotation.id, QuotationLine.version_no == quotation.current_version
            )
        ).all():
            self._db.delete(line)
        self._db.flush()
        self._write_lines(quotation, data)
        return self._touch(quotation)

    def _fill(self, quotation: Quotation, data: QuotationCreate) -> None:
        principal = active_principal(self._db, self._actor, data.principal_id)
        customer = active_customer(self._db, data.customer_id)
        site = customer_branch(self._db, customer, data.customer_site_id)
        quotation_date = data.quotation_date or date.today()
        valid_until = data.valid_until or quotation_date + timedelta(days=VALIDITY_DAYS)
        if valid_until < quotation_date:
            raise err("validUntil", "The validity date is before the quotation date.")
        quotation.principal_id = principal.id
        quotation.customer_id = customer.id
        quotation.customer_site_id = site.id if site else None
        quotation.quotation_type = data.quotation_type
        quotation.quotation_date = quotation_date
        quotation.valid_until = valid_until
        quotation.place_of_supply_state_id = place_of_supply(self._db, customer, site, quotation.branch_id)
        quotation.salesperson_employee_id = quotation.salesperson_employee_id or customer.salesman_employee_id
        quotation.other_charges = data.other_charges
        quotation.terms = data.terms
        quotation.remarks = data.remarks

    def _write_lines(self, quotation: Quotation, data: QuotationCreate) -> None:
        inter_state = is_inter_state(self._db, quotation.branch_id, quotation.place_of_supply_state_id)
        totals = price_lines(self._db, self._actor, list(data.lines), quotation.principal_id, inter_state=inter_state)
        for number, priced in enumerate(totals.lines, start=1):
            item = priced.item
            self._db.add(
                QuotationLine(
                    quotation_id=quotation.id,
                    version_no=quotation.current_version,
                    line_no=number * 10,
                    item_id=item.id if item else None,
                    description=priced.description,
                    quantity=priced.quantity,
                    uom_id=item.uom_id if item else None,
                    unit_price=priced.unit_price,
                    discount_pct=priced.discount_pct,
                    discount_amount=priced.discount,
                    gst_pct=priced.gst_pct,
                    hsn_sac_id=item.hsn_sac_id if item else None,
                    taxable_value=priced.taxable,
                    tax_amount=priced.tax,
                    line_total=priced.total,
                    created_by_user_id=self._actor.id,
                )
            )
        quotation.subtotal = totals.gross
        quotation.discount_total = totals.discount
        quotation.tax_total = totals.tax
        quotation.cgst, quotation.sgst, quotation.igst = totals.cgst, totals.sgst, totals.igst
        quotation.total = totals.total(quotation.other_charges)
        version = self._version(quotation)
        version.total = quotation.total

    def _version(self, quotation: Quotation) -> QuotationVersion:
        version = self._db.scalars(
            select(QuotationVersion).where(
                QuotationVersion.quotation_id == quotation.id,
                QuotationVersion.version_no == quotation.current_version,
            )
        ).first()
        assert version is not None
        return version

    # ------------------------------------------------------------------ workflow

    def submit(self, quotation_id: int) -> QuotationDetail:
        quotation = self._visible(quotation_id)
        self._expect(quotation, ("Draft",), "submitted")
        discounted = self._db.scalar(
            select(func.count(QuotationLine.id)).where(
                QuotationLine.quotation_id == quotation.id,
                QuotationLine.version_no == quotation.current_version,
                QuotationLine.discount_pct > 0,
            )
        )
        quotation.submitted_at = now()
        quotation.submitted_by_user_id = self._actor.id
        if discounted and not self._actor.can(QUOTATION_APPROVE):
            quotation.status = "Pending approval"
        else:
            quotation.status = "Submitted"
            if discounted:
                quotation.approved_at = quotation.submitted_at
                quotation.approved_by_user_id = self._actor.id
        return self._touch(quotation)

    def approve(self, quotation_id: int) -> QuotationDetail:
        require(
            self._actor, QUOTATION_APPROVE, "Approving quotation discounts needs the quotation approval permission."
        )
        quotation = self._visible(quotation_id)
        self._expect(quotation, ("Pending approval",), "approved")
        quotation.status = "Submitted"
        quotation.approved_at = now()
        quotation.approved_by_user_id = self._actor.id
        return self._touch(quotation)

    def send_back(self, quotation_id: int, data: QuotationNote) -> QuotationDetail:
        require(self._actor, QUOTATION_APPROVE, "Sending a quotation back needs the quotation approval permission.")
        quotation = self._visible(quotation_id)
        self._expect(quotation, ("Pending approval",), "sent back")
        if not data.note:
            raise err("note", "Say why the quotation is sent back.")
        quotation.status = "Draft"
        quotation.response_note = f"Sent back: {data.note}"
        return self._touch(quotation)

    def accept(self, quotation_id: int, data: QuotationNote) -> QuotationDetail:
        """The customer accepted the quotation."""
        quotation = self._visible(quotation_id)
        self._expect(quotation, ("Submitted", "Sent"), "accepted")
        if quotation_state(quotation.status, quotation.valid_until, date.today()) == "Expired":
            raise Conflict(f"Quotation {quotation.quotation_no} has expired; revise it first.")
        quotation.status = "Accepted"
        return self._respond(quotation, data.note)

    def reject(self, quotation_id: int, data: QuotationNote) -> QuotationDetail:
        """The customer turned the quotation down."""
        quotation = self._visible(quotation_id)
        self._expect(quotation, ("Submitted", "Sent"), "rejected")
        if not data.note:
            raise err("note", "Say why the customer rejected it.")
        quotation.status = "Rejected"
        return self._respond(quotation, data.note)

    def _respond(self, quotation: Quotation, note: str | None) -> QuotationDetail:
        quotation.responded_at = now()
        quotation.responded_by_user_id = self._actor.id
        quotation.response_note = note
        return self._touch(quotation)

    def revise(self, quotation_id: int, data: QuotationNote) -> QuotationDetail:
        """A new version (draft) with the current lines copied; the old version stays on record."""
        quotation = self._visible(quotation_id)
        self._expect(quotation, REVISABLE, "revised")
        if not data.note:
            raise err("note", "Say what this revision changes.")
        old_lines = self._db.scalars(
            select(QuotationLine).where(
                QuotationLine.quotation_id == quotation.id, QuotationLine.version_no == quotation.current_version
            )
        ).all()
        quotation.current_version += 1
        self._db.add(
            QuotationVersion(quotation_id=quotation.id, version_no=quotation.current_version, total=quotation.total,
                             change_note=data.note, created_by_user_id=self._actor.id)
        )  # fmt: skip
        copied = ("line_no", "item_id", "description", "quantity", "uom_id", "unit_price", "discount_pct",
                  "discount_amount", "gst_pct", "hsn_sac_id", "taxable_value", "tax_amount", "line_total")  # fmt: skip
        for line in old_lines:
            self._db.add(
                QuotationLine(
                    quotation_id=quotation.id,
                    version_no=quotation.current_version,
                    created_by_user_id=self._actor.id,
                    **{f: getattr(line, f) for f in copied},
                )
            )
        quotation.status = "Draft"
        for column in ("submitted_at", "submitted_by_user_id", "approved_at", "approved_by_user_id",
                       "responded_at", "responded_by_user_id", "response_note"):  # fmt: skip
            setattr(quotation, column, None)
        return self._touch(quotation)

    def convert(self, quotation_id: int, data: ConvertQuotation) -> OrderDetail:
        """An accepted quotation becomes a draft sales order with the same lines."""
        quotation = self._visible(quotation_id)
        self._expect(quotation, ("Accepted",), "converted to an order")
        lines = self._db.scalars(
            select(QuotationLine)
            .where(QuotationLine.quotation_id == quotation.id, QuotationLine.version_no == quotation.current_version)
            .order_by(QuotationLine.line_no)
        ).all()
        missing = [line.description for line in lines if line.item_id is None]
        if missing:
            raise Conflict(f"Lines without an item can't go on an order: {', '.join(missing)}. Revise the quotation.")
        order = OrderCreate(
            principal_id=quotation.principal_id,
            branch_id=quotation.branch_id,
            customer_id=quotation.customer_id,
            customer_site_id=quotation.customer_site_id,
            customer_po_no=data.customer_po_no,
            customer_po_date=data.customer_po_date,
            expected_delivery_date=data.expected_delivery_date,
            is_prepaid=data.is_prepaid,
            other_charges=quotation.other_charges,
            remarks=f"From quotation {quotation.quotation_no} (version {quotation.current_version})",
            lines=[
                ItemLineIn(
                    item_id=line.item_id,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount_pct=line.discount_pct or ZERO,
                    gst_pct=line.gst_pct,
                )
                for line in lines
            ],
        )
        quotation.status = "Converted"
        quotation.updated_at = now()
        quotation.updated_by_user_id = self._actor.id
        return SalesOrderService(self._db, self._actor).create(order, quotation_id=quotation.id)

    # ------------------------------------------------------------------ helpers

    def _visible(self, quotation_id: int) -> Quotation:
        quotation = self._db.get(Quotation, quotation_id)
        if (
            quotation is None
            or not self._actor.can_use_branch(quotation.branch_id)
            or not self._actor.can_see_principal(quotation.principal_id)
        ):
            raise NotFound("Quotation not found.")
        return quotation

    @staticmethod
    def _expect(quotation: Quotation, statuses: tuple[str, ...], action: str) -> None:
        if quotation.status not in statuses:
            raise Conflict(
                f"Quotation {quotation.quotation_no} is {quotation.status.lower()}, so it can't be {action}."
            )

    def _touch(self, quotation: Quotation) -> QuotationDetail:
        quotation.updated_at = now()
        quotation.updated_by_user_id = self._actor.id
        self._commit()
        return self.get(quotation.id)

    def _commit(self) -> None:
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise Conflict(
                "The quotation could not be saved; someone else changed it. Reload and try again."
            ) from error
