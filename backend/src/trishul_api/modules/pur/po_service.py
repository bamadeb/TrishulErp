r"""Purchase orders: create, change while a draft, send for approval, approve or reject, close or cancel.

    Draft --submit--> Pending approval --approve--> Approved --GRN--> Part received --GRN--> Received
                       \--reject--> Draft
    Draft / Pending approval / Approved (nothing received) --cancel--> Cancelled
    Approved / Part received --close--> Closed (the rest will not come)

Quantities received come from GRNs (accepted quantity); invoiced quantities from supplier invoices.
Amounts: taxable = qty x price less discount; GST split CGST + SGST within the branch's state, IGST from
another state; total = taxable + GST + other charges.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, Conflict, Forbidden, NotFound
from trishul_api.common.numbering import next_document_no
from trishul_api.common.paging import order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Branch,
    Company,
    Grn,
    GrnLine,
    Item,
    Location,
    PaymentTerms,
    PurchaseOrder,
    PurchaseOrderLine,
    State,
    Supplier,
    SupplierInvoice,
    Uom,
)
from trishul_api.modules.inv.common import now, stock_item, stock_location, visible_branch
from trishul_api.modules.inv.masters_service import MastersService
from trishul_api.modules.pur.common import (
    PO_CLOSE,
    ZERO,
    active_supplier,
    branch_state,
    is_inter_state,
    line_amounts,
    money,
    split_gst,
)
from trishul_api.modules.pur.po_schemas import (
    OutstandingLine,
    OutstandingQuery,
    PoCreate,
    PoDetail,
    PoDocument,
    PoLineOut,
    PoListItem,
    PoNote,
    PoQuery,
)

OPEN_FOR_RECEIPT = ("Approved", "Sent", "Part received")
_COST = Decimal("0.0001")


def net_price(line: PurchaseOrderLine) -> Decimal:
    return (line.unit_price * (Decimal(100) - (line.discount_pct or ZERO)) / Decimal(100)).quantize(_COST)


class PurchaseOrderService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ list and detail

    def _totals(self) -> Any:
        return (
            select(
                PurchaseOrderLine.purchase_order_id,
                func.count(PurchaseOrderLine.id).label("line_count"),
                func.sum(PurchaseOrderLine.quantity).label("qty_ordered"),
                func.sum(PurchaseOrderLine.qty_received).label("qty_received"),
            )
            .group_by(PurchaseOrderLine.purchase_order_id)
            .subquery()
        )

    def _select(self) -> Select[*tuple[Any, ...]]:
        totals = self._totals()
        ordered = func.coalesce(totals.c.qty_ordered, 0)
        received = func.coalesce(totals.c.qty_received, 0)
        return (
            select(
                PurchaseOrder.id,
                PurchaseOrder.po_no,
                PurchaseOrder.po_date,
                PurchaseOrder.expected_date,
                PurchaseOrder.supplier_id,
                Supplier.name.label("supplier_name"),
                PurchaseOrder.branch_id,
                Branch.name.label("branch_name"),
                Location.name.label("location_name"),
                PurchaseOrder.status,
                PurchaseOrder.total,
                func.coalesce(totals.c.line_count, 0).label("line_count"),
                ordered.label("qty_ordered"),
                received.label("qty_received"),
                (ordered - received).label("qty_pending"),
                PurchaseOrder.created_at,
            )
            .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
            .join(Branch, Branch.id == PurchaseOrder.branch_id)
            .join(Location, Location.id == PurchaseOrder.delivery_location_id)
            .outerjoin(totals, totals.c.purchase_order_id == PurchaseOrder.id)
            .where(visible_branch(self._actor))
        )

    def search(self, query: PoQuery) -> Page[PoListItem]:
        statement = self._select()
        if query.status is not None:
            statement = statement.where(PurchaseOrder.status == query.status)
        if query.supplier_id is not None:
            statement = statement.where(PurchaseOrder.supplier_id == query.supplier_id)
        if query.branch_id is not None:
            statement = statement.where(PurchaseOrder.branch_id == query.branch_id)
        if query.from_date is not None:
            statement = statement.where(PurchaseOrder.po_date >= query.from_date)
        if query.to_date is not None:
            statement = statement.where(PurchaseOrder.po_date <= query.to_date)
        if query.item_id is not None:
            statement = statement.where(
                exists().where(
                    PurchaseOrderLine.purchase_order_id == PurchaseOrder.id, PurchaseOrderLine.item_id == query.item_id
                )
            )
        if query.outstanding_only:
            statement = statement.where(
                PurchaseOrder.status.in_(OPEN_FOR_RECEIPT),
                exists().where(
                    PurchaseOrderLine.purchase_order_id == PurchaseOrder.id,
                    PurchaseOrderLine.qty_received < PurchaseOrderLine.quantity,
                ),
            )
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    PurchaseOrder.po_no.contains(term, autoescape=True),
                    Supplier.name.contains(term, autoescape=True),
                    PurchaseOrder.oem_po_ref.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {
                "poDate": PurchaseOrder.po_date,
                "poNo": PurchaseOrder.po_no,
                "supplierName": Supplier.name,
                "total": PurchaseOrder.total,
                "expectedDate": PurchaseOrder.expected_date,
            },
            default="-poDate",
            tiebreaker=PurchaseOrder.id.desc(),
        )
        return paginate(self._db, statement, query, PoListItem)

    def get(self, po_id: int) -> PoDetail:
        po = self._visible(po_id)
        created, submitted, approved, closed = (aliased(AppUser) for _ in range(4))
        location = aliased(Location)
        header = (
            self._db.execute(
                self._select()
                .add_columns(
                    Company.legal_name.label("company_name"),
                    Company.address.label("company_address"),
                    Branch.address.label("branch_address"),
                    Supplier.code.label("supplier_code"),
                    Supplier.gstin.label("supplier_gstin"),
                    Supplier.address.label("supplier_address"),
                    Supplier.phone.label("supplier_phone"),
                    PurchaseOrder.delivery_location_id,
                    location.address.label("location_address"),
                    PurchaseOrder.payment_terms_id,
                    PaymentTerms.description.label("payment_terms"),
                    State.name.label("place_of_supply"),
                    PurchaseOrder.po_type,
                    PurchaseOrder.subtotal,
                    PurchaseOrder.cgst,
                    PurchaseOrder.sgst,
                    PurchaseOrder.igst,
                    PurchaseOrder.tax_total,
                    PurchaseOrder.other_charges,
                    PurchaseOrder.oem_po_ref,
                    PurchaseOrder.remarks,
                    created.username.label("created_by"),
                    submitted.username.label("submitted_by"),
                    PurchaseOrder.submitted_at,
                    approved.username.label("approved_by"),
                    PurchaseOrder.approved_at,
                    PurchaseOrder.approval_note,
                    closed.username.label("closed_by"),
                    PurchaseOrder.closed_at,
                    PurchaseOrder.close_reason,
                    PurchaseOrder.row_version,
                )
                .join(Company, Company.id == PurchaseOrder.company_id)
                .join(location, location.id == PurchaseOrder.delivery_location_id)
                .join(State, State.id == PurchaseOrder.place_of_supply_state_id)
                .outerjoin(PaymentTerms, PaymentTerms.id == PurchaseOrder.payment_terms_id)
                .outerjoin(created, created.id == PurchaseOrder.created_by_user_id)
                .outerjoin(submitted, submitted.id == PurchaseOrder.submitted_by_user_id)
                .outerjoin(approved, approved.id == PurchaseOrder.approved_by_user_id)
                .outerjoin(closed, closed.id == PurchaseOrder.closed_by_user_id)
                .where(PurchaseOrder.id == po.id)
            )
            .mappings()
            .one()
        )
        lines = []
        for line, code, description, uom in self._db.execute(
            select(PurchaseOrderLine, Item.item_code, Item.description, Uom.code)
            .join(Item, Item.id == PurchaseOrderLine.item_id)
            .join(Uom, Uom.id == PurchaseOrderLine.uom_id)
            .where(PurchaseOrderLine.purchase_order_id == po.id)
            .order_by(PurchaseOrderLine.line_no)
        ).all():
            lines.append(
                PoLineOut(
                    id=line.id,
                    line_no=line.line_no,
                    item_id=line.item_id,
                    item_code=code,
                    item_description=description,
                    description=line.description,
                    uom_code=uom,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount_pct=line.discount_pct or ZERO,
                    gst_pct=line.gst_pct,
                    net_price=net_price(line),
                    taxable_value=line.taxable_value,
                    tax_amount=line.tax_amount,
                    line_total=line.line_total,
                    qty_received=line.qty_received,
                    qty_invoiced=line.qty_invoiced,
                    qty_pending=max(line.quantity - line.qty_received, ZERO),
                )
            )
        grn_value = func.coalesce(func.sum(GrnLine.qty_accepted * GrnLine.unit_cost), 0)
        grns = [
            PoDocument(id=r.id, number=r.grn_no, date=r.grn_date, amount=money(Decimal(r.value)), status=r.status)
            for r in self._db.execute(
                select(Grn.id, Grn.grn_no, Grn.grn_date, Grn.status, grn_value.label("value"))
                .join(GrnLine, GrnLine.grn_id == Grn.id)
                .where(Grn.purchase_order_id == po.id)
                .group_by(Grn.id, Grn.grn_no, Grn.grn_date, Grn.status)
                .order_by(Grn.grn_date, Grn.id)
            ).all()
        ]
        invoices = [
            PoDocument(id=i.id, number=i.invoice_no, date=i.supplier_invoice_date, amount=i.total, status=i.status)
            for i in self._db.scalars(
                select(SupplierInvoice).where(SupplierInvoice.purchase_order_id == po.id).order_by(SupplierInvoice.id)
            ).all()
        ]
        return PoDetail.model_validate({**header, "lines": lines, "grns": grns, "invoices": invoices})

    def outstanding(self, query: OutstandingQuery) -> Page[OutstandingLine]:
        pending = PurchaseOrderLine.quantity - PurchaseOrderLine.qty_received
        price = PurchaseOrderLine.unit_price * (100 - func.coalesce(PurchaseOrderLine.discount_pct, 0)) / 100
        statement: Select[*tuple[Any, ...]] = (
            select(
                PurchaseOrder.id.label("purchase_order_id"),
                PurchaseOrder.po_no,
                PurchaseOrder.po_date,
                PurchaseOrder.expected_date,
                PurchaseOrder.status,
                PurchaseOrder.supplier_id,
                Supplier.name.label("supplier_name"),
                Branch.name.label("branch_name"),
                PurchaseOrderLine.id.label("line_id"),
                PurchaseOrderLine.item_id,
                Item.item_code,
                Item.description.label("item_description"),
                Uom.code.label("uom_code"),
                PurchaseOrderLine.quantity.label("qty_ordered"),
                PurchaseOrderLine.qty_received,
                pending.label("qty_pending"),
                price.label("net_price"),
                (pending * price).label("pending_value"),
            )
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
            .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
            .join(Branch, Branch.id == PurchaseOrder.branch_id)
            .join(Item, Item.id == PurchaseOrderLine.item_id)
            .join(Uom, Uom.id == PurchaseOrderLine.uom_id)
            .where(PurchaseOrder.status.in_(OPEN_FOR_RECEIPT), pending > 0, visible_branch(self._actor))
        )
        if query.supplier_id is not None:
            statement = statement.where(PurchaseOrder.supplier_id == query.supplier_id)
        if query.branch_id is not None:
            statement = statement.where(PurchaseOrder.branch_id == query.branch_id)
        if query.item_id is not None:
            statement = statement.where(PurchaseOrderLine.item_id == query.item_id)
        if query.overdue_only:
            statement = statement.where(PurchaseOrder.expected_date < date.today())
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    PurchaseOrder.po_no.contains(term, autoescape=True),
                    Item.item_code.contains(term, autoescape=True),
                    Item.description.contains(term, autoescape=True),
                    Supplier.name.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {"poDate": PurchaseOrder.po_date, "expectedDate": PurchaseOrder.expected_date, "itemCode": Item.item_code},
            default="poDate",
            tiebreaker=PurchaseOrderLine.id.asc(),
        )
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = (
            self._db.execute(statement.offset((query.page - 1) * query.page_size).limit(query.page_size))
            .mappings()
            .all()
        )
        today = date.today()
        items = [
            OutstandingLine.model_validate(
                {
                    **r,
                    "net_price": Decimal(r["net_price"]).quantize(_COST),
                    "pending_value": money(Decimal(r["pending_value"])),
                    "days_open": (today - r["po_date"]).days,
                }
            )
            for r in rows
        ]
        return Page(items=items, total=total, page=query.page, page_size=query.page_size)

    # ------------------------------------------------------------------ create and change

    def create(self, data: PoCreate) -> PoDetail:
        location = stock_location(self._db, self._actor, data.delivery_location_id, "deliveryLocationId")
        supplier = active_supplier(self._db, data.supplier_id)
        branch = self._db.get(Branch, location.branch_id)
        assert branch is not None
        po = PurchaseOrder(
            po_no=next_document_no(
                self._db, company_id=branch.company_id, document_type="PURCHASE_ORDER", branch_id=branch.id
            ),
            company_id=branch.company_id,
            branch_id=branch.id,
            status="Draft",
            subtotal=ZERO,
            tax_total=ZERO,
            total=ZERO,
            created_by_user_id=self._actor.id,
            currency_id=MastersService(self._db, self._actor).currency_id(),
        )
        self._fill(po, data, supplier, location.id, branch.id)
        self._db.add(po)
        self._db.flush()
        self._replace_lines(po, data, supplier)
        self._commit()
        return self.get(po.id)

    def update(self, po_id: int, expected: bytes, data: PoCreate) -> PoDetail:
        """Replaces the whole order (header and lines). Only a draft can change."""
        po = self._visible(po_id)
        check_row_version(po.row_version, expected)
        if po.status != "Draft":
            raise Conflict(f"Only a draft order can be changed; this one is {po.status.lower()}.")
        location = stock_location(self._db, self._actor, data.delivery_location_id, "deliveryLocationId")
        if location.branch_id != po.branch_id:
            raise ApiError(
                "Deliver to a location of the same branch (the order number belongs to it).",
                errors={"deliveryLocationId": ["Another branch."]},
            )
        supplier = active_supplier(self._db, data.supplier_id)
        self._fill(po, data, supplier, location.id, po.branch_id)
        self._replace_lines(po, data, supplier)
        po.updated_at = now()
        po.updated_by_user_id = self._actor.id
        self._commit()
        return self.get(po.id)

    def _fill(self, po: PurchaseOrder, data: PoCreate, supplier: Supplier, location_id: int, branch_id: int) -> None:
        if data.payment_terms_id is not None and self._db.get(PaymentTerms, data.payment_terms_id) is None:
            raise ApiError("Choose payment terms from the list.", errors={"paymentTermsId": ["Unknown terms."]})
        po_date = data.po_date or date.today()
        if data.expected_date is not None and data.expected_date < po_date:
            raise ApiError("The expected date is before the order date.", errors={"expectedDate": ["Too early."]})
        po.supplier_id = supplier.id
        po.delivery_location_id = location_id
        po.po_date = po_date
        po.expected_date = data.expected_date
        po.payment_terms_id = data.payment_terms_id or supplier.payment_terms_id
        po.place_of_supply_state_id = branch_state(self._db, branch_id)
        po.po_type = data.po_type
        po.other_charges = data.other_charges
        po.oem_po_ref = data.oem_po_ref
        po.remarks = data.remarks

    def _replace_lines(self, po: PurchaseOrder, data: PoCreate, supplier: Supplier) -> None:
        old_lines = self._db.scalars(
            select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == po.id)
        ).all()
        for old in old_lines:
            self._db.delete(old)
        self._db.flush()
        inter_state = is_inter_state(self._db, supplier, po.branch_id)
        subtotal = tax = ZERO
        for number, line in enumerate(data.lines, start=1):
            item = stock_item(self._db, self._actor, line.item_id, f"lines[{number - 1}].itemId")
            amounts = line_amounts(line.quantity, line.unit_price, line.discount_pct, line.gst_pct)
            subtotal += amounts.taxable
            tax += amounts.tax
            self._db.add(
                PurchaseOrderLine(
                    purchase_order_id=po.id,
                    line_no=number * 10,
                    item_id=item.id,
                    description=line.description,
                    quantity=line.quantity,
                    uom_id=item.uom_id,
                    unit_price=line.unit_price,
                    discount_pct=line.discount_pct,
                    gst_pct=line.gst_pct,
                    hsn_sac_id=item.hsn_sac_id,
                    taxable_value=amounts.taxable,
                    tax_amount=amounts.tax,
                    line_total=amounts.total,
                    created_by_user_id=self._actor.id,
                )
            )
        split = split_gst(tax, inter_state=inter_state)
        po.subtotal = subtotal
        po.tax_total = money(tax)
        po.cgst, po.sgst, po.igst = split.cgst, split.sgst, split.igst
        po.total = subtotal + money(tax) + po.other_charges

    # ------------------------------------------------------------------ workflow

    def submit(self, po_id: int) -> PoDetail:
        po = self._visible(po_id)
        self._expect(po, ("Draft",), "sent for approval")
        po.status = "Pending approval"
        po.submitted_at = now()
        po.submitted_by_user_id = self._actor.id
        return self._touch(po)

    def approve(self, po_id: int, data: PoNote) -> PoDetail:
        po = self._visible(po_id)
        self._expect(po, ("Pending approval",), "approved")
        po.status = "Approved"
        po.approved_at = now()
        po.approved_by_user_id = self._actor.id
        po.approval_note = data.note
        return self._touch(po)

    def reject(self, po_id: int, data: PoNote) -> PoDetail:
        po = self._visible(po_id)
        self._expect(po, ("Pending approval",), "sent back")
        if not data.note:
            raise ApiError("Say why the order is sent back.", errors={"note": ["Required."]})
        po.status = "Draft"
        po.approval_note = f"Sent back: {data.note}"
        return self._touch(po)

    def close(self, po_id: int, data: PoNote) -> PoDetail:
        """The rest of the order will not come: no more GRNs against it."""
        self._require(PO_CLOSE)
        po = self._visible(po_id)
        self._expect(po, OPEN_FOR_RECEIPT, "closed")
        if not data.note:
            raise ApiError("Say why the order is closed.", errors={"note": ["Required."]})
        po.status = "Closed"
        po.closed_at = now()
        po.closed_by_user_id = self._actor.id
        po.close_reason = data.note
        return self._touch(po)

    def cancel(self, po_id: int, data: PoNote) -> PoDetail:
        """Only an order nothing has been received against; otherwise close it."""
        po = self._visible(po_id)
        self._expect(po, ("Draft", "Pending approval", "Approved", "Sent"), "cancelled")
        if po.status not in ("Draft",):
            self._require(PO_CLOSE)
        received = self._db.scalar(
            select(func.coalesce(func.sum(PurchaseOrderLine.qty_received), 0)).where(
                PurchaseOrderLine.purchase_order_id == po.id
            )
        )
        if received:
            raise Conflict("Goods have been received against this order; close it instead.")
        if not data.note:
            raise ApiError("Say why the order is cancelled.", errors={"note": ["Required."]})
        po.status = "Cancelled"
        po.closed_at = now()
        po.closed_by_user_id = self._actor.id
        po.close_reason = data.note
        return self._touch(po)

    # ------------------------------------------------------------------ helpers

    def _require(self, permission: str) -> None:
        if not self._actor.can(permission):
            raise Forbidden("You do not have permission for this action.")

    def _visible(self, po_id: int) -> PurchaseOrder:
        po = self._db.get(PurchaseOrder, po_id)
        if po is None or not self._actor.can_use_branch(po.branch_id):
            raise NotFound("Purchase order not found.")
        return po

    @staticmethod
    def _expect(po: PurchaseOrder, statuses: tuple[str, ...], action: str) -> None:
        if po.status not in statuses:
            raise Conflict(f"Order {po.po_no} is {po.status.lower()}, so it can't be {action}.")

    def _touch(self, po: PurchaseOrder) -> PoDetail:
        po.updated_at = now()
        po.updated_by_user_id = self._actor.id
        self._commit()
        return self.get(po.id)

    def _commit(self) -> None:
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise Conflict("The order could not be saved; someone else changed it. Reload and try again.") from error
