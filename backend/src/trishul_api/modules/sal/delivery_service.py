"""Delivery notes: goods to a customer, against an approved sales order or direct.

* Posting a delivery note takes the stock at once (status Dispatched); confirming receipt later records
  who received it and when (Delivered).
* Against an order: no more than is outstanding on each line, unless the user may over-deliver and asks
  to. The order's delivered quantities and status follow.
* Batches: oldest GRN date first unless a batch or rack is named; each batch taken is on stock_move,
  so the GRN reference stays traceable from the delivery.
* Cancelling (nothing invoiced yet) puts the same batches back and reduces the order's delivered quantity.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import AlreadyExists, Conflict, NotFound
from trishul_api.common.numbering import next_document_no
from trishul_api.common.paging import order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Bin,
    Branch,
    Company,
    Customer,
    CustomerSite,
    DeliveryNote,
    DeliveryNoteLine,
    Item,
    Location,
    Principal,
    SalesInvoice,
    SalesInvoiceLine,
    SalesOrder,
    SalesOrderLine,
    StockLot,
    StockMove,
    Uom,
)
from trishul_api.modules.inv.common import company_of_branch, now, rack_of, stock_location, visible_branch
from trishul_api.modules.inv.ledger import Source, StockLedger
from trishul_api.modules.sal.common import (
    DELIVERY_OVER_ORDER,
    ZERO,
    active_branch,
    active_customer,
    active_principal,
    addresses,
    customer_branch,
    err,
    qty_text,
    require,
    sale_item,
)
from trishul_api.modules.sal.delivery_schemas import (
    DeliveryBatch,
    DeliveryCancel,
    DeliveryConfirm,
    DeliveryCreate,
    DeliveryDetail,
    DeliveryInvoice,
    DeliveryLineOut,
    DeliveryListItem,
    DeliveryQuery,
    UninvoicedDeliveryLine,
    UninvoicedDeliveryQuery,
)
from trishul_api.modules.sal.order_service import OPEN_FOR_DELIVERY, refresh_status
from trishul_api.modules.sal.stock import put_back, take_for_sale

DOCUMENT = "DELIVERY_NOTE"
LIVE = ("Dispatched", "Delivered")


class DeliveryService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ create

    def create(self, data: DeliveryCreate) -> DeliveryDetail:
        order = None
        if data.sales_order_id is not None:
            order = self._db.get(SalesOrder, data.sales_order_id)
            if order is None or not self._actor.can_use_branch(order.branch_id):
                raise err("salesOrderId", "Sales order not found.")
            if order.status not in OPEN_FOR_DELIVERY:
                raise Conflict(f"Order {order.order_no} is {order.status.lower()}; goods can't go out against it.")
            principal_id, branch_id, customer_id = order.principal_id, order.branch_id, order.customer_id
        else:
            if data.principal_id is None or data.branch_id is None or data.customer_id is None:
                raise err("customerId", "A direct delivery needs the brand, branch and customer.")
            principal_id, branch_id, customer_id = data.principal_id, data.branch_id, data.customer_id
        principal = active_principal(self._db, self._actor, principal_id)
        branch = active_branch(self._db, self._actor, branch_id)
        customer = active_customer(self._db, customer_id)
        site = customer_branch(self._db, customer, data.customer_site_id or (order.customer_site_id if order else None))
        location = stock_location(self._db, self._actor, data.location_id)
        delivery_date = data.delivery_date or date.today()
        if delivery_date > date.today():
            raise err("deliveryDate", "The delivery date can't be in the future.")
        if order is not None and delivery_date < order.order_date:
            raise err("deliveryDate", "The delivery date is before the order date.")
        _, ship_to = addresses(customer, site)

        note = DeliveryNote(
            delivery_no=next_document_no(
                self._db, company_id=branch.company_id, document_type="DELIVERY_NOTE", branch_id=branch.id
            ),
            principal_id=principal.id,
            branch_id=branch.id,
            sales_order_id=order.id if order else None,
            customer_id=customer.id,
            customer_site_id=site.id if site else None,
            delivery_site_id=site.id if site else None,
            delivery_date=delivery_date,
            from_location_id=location.id,
            ship_to_address=data.ship_to_address or (order.ship_to_address if order else None) or ship_to,
            delivery_reference=data.delivery_reference,
            vehicle_no=data.vehicle_no,
            transporter=data.transporter,
            lr_no=data.lr_no,
            received_by_name=data.received_by_name,
            recipient_phone=data.recipient_phone,
            remarks=data.remarks,
            status="Dispatched",
            dispatched_at=now(),
            posted_by_user_id=self._actor.id,
            created_by_user_id=self._actor.id,
        )
        self._db.add(note)
        self._db.flush()
        ledger = StockLedger(
            self._db, company_id=company_of_branch(self._db, location.branch_id), user_id=self._actor.id, at=now()
        )
        asked: dict[int, Decimal] = defaultdict(lambda: ZERO)
        for index, line in enumerate(data.lines):
            field = f"lines[{index}]"
            order_line = None
            if line.sales_order_line_id is not None:
                order_line = self._db.get(SalesOrderLine, line.sales_order_line_id)
                if order is None or order_line is None or order_line.sales_order_id != order.id:
                    raise err(f"{field}.salesOrderLineId", "That line is not on this order.")
                left = order_line.quantity - order_line.qty_delivered - asked[order_line.id]
                if line.quantity > left:
                    if not data.over_deliver:
                        raise err(
                            f"{field}.quantity", f"Only {qty_text(max(left, ZERO))} is left to deliver on that line."
                        )
                    require(self._actor, DELIVERY_OVER_ORDER, "Delivering more than was ordered needs permission.")
                asked[order_line.id] += line.quantity
                item_id = order_line.item_id
            elif order is not None:
                raise err(f"{field}.salesOrderLineId", "Against an order, every line comes from the order.")
            else:
                assert line.item_id is not None
                item_id = line.item_id
            item = sale_item(self._db, self._actor, item_id, principal.id, f"{field}.itemId")
            bin_id = rack_of(self._db, location, line.bin_id, f"{field}.binId")
            row = DeliveryNoteLine(
                delivery_note_id=note.id,
                sales_order_line_id=order_line.id if order_line else None,
                item_id=item.id,
                quantity=line.quantity,
                qty_invoiced=ZERO,
                description=(order_line.description if order_line else None) or line.description or item.description,
                uom_id=item.uom_id,
                bin_id=bin_id,
                unit_price=order_line.unit_price if order_line else line.unit_price,
                discount_pct=order_line.discount_pct if order_line else line.discount_pct,
                gst_pct=order_line.gst_pct if order_line else line.gst_pct,
                created_by_user_id=self._actor.id,
            )
            self._db.add(row)
            self._db.flush()
            if item.item_type == "Stock":
                row.unit_cost = take_for_sale(
                    ledger, item=item, location=location, bin_id=bin_id, quantity=line.quantity,
                    lot_id=line.stock_lot_id, source=Source(DOCUMENT, note.id, note.delivery_no, row.id),
                )  # fmt: skip
            if order_line is not None:
                order_line.qty_delivered = order_line.qty_delivered + line.quantity
        if order is not None:
            self._db.flush()
            refresh_status(self._db, order)
        self._commit("The delivery could not be saved; stock may have changed. Reload and try again.")
        return self.get(note.id)

    # ------------------------------------------------------------------ after dispatch

    def confirm(self, note_id: int, data: DeliveryConfirm) -> DeliveryDetail:
        """The customer received the goods (proof of delivery)."""
        note = self._visible(note_id)
        if note.status != "Dispatched":
            raise Conflict(f"Delivery {note.delivery_no} is {note.status.lower()}.")
        note.status = "Delivered"
        note.received_by_name = data.received_by_name
        note.delivered_at = (data.delivered_at.replace(tzinfo=None) if data.delivered_at else None) or now()
        note.updated_at = now()
        note.updated_by_user_id = self._actor.id
        self._commit("The delivery could not be saved.")
        return self.get(note.id)

    def cancel(self, note_id: int, data: DeliveryCancel) -> DeliveryDetail:
        """Reverses the delivery: the batches go back, the order's delivered quantity goes down."""
        note = self._visible(note_id)
        if note.status not in LIVE:
            raise Conflict(f"Delivery {note.delivery_no} is {note.status.lower()}.")
        lines = self._db.scalars(select(DeliveryNoteLine).where(DeliveryNoteLine.delivery_note_id == note.id)).all()
        if any(line.qty_invoiced > 0 for line in lines):
            raise Conflict(f"Delivery {note.delivery_no} has been invoiced; cancel the invoice first.")
        ledger = StockLedger(
            self._db, company_id=company_of_branch(self._db, self._location(note).branch_id), user_id=self._actor.id,
            at=now(),
        )  # fmt: skip
        put_back(self._db, ledger, document_type=DOCUMENT, document_id=note.id, reference=note.delivery_no)
        for line in lines:
            if line.sales_order_line_id is not None:
                order_line = self._db.get(SalesOrderLine, line.sales_order_line_id)
                assert order_line is not None
                order_line.qty_delivered = max(order_line.qty_delivered - line.quantity, ZERO)
        note.status = "Cancelled"
        note.cancelled_at = now()
        note.cancelled_by_user_id = self._actor.id
        note.cancel_reason = data.reason
        note.updated_at = note.cancelled_at
        note.updated_by_user_id = self._actor.id
        if note.sales_order_id is not None:
            self._db.flush()
            order = self._db.get(SalesOrder, note.sales_order_id)
            assert order is not None
            refresh_status(self._db, order)
        self._commit("The delivery could not be cancelled.")
        return self.get(note.id)

    # ------------------------------------------------------------------ reads

    def _select(self) -> Select[*tuple[Any, ...]]:
        totals = (
            select(
                DeliveryNoteLine.delivery_note_id,
                func.sum(DeliveryNoteLine.quantity).label("total_qty"),
                func.sum(DeliveryNoteLine.qty_invoiced).label("qty_invoiced"),
            )
            .group_by(DeliveryNoteLine.delivery_note_id)
            .subquery()
        )
        return (
            select(
                DeliveryNote.id,
                DeliveryNote.delivery_no,
                DeliveryNote.delivery_date,
                DeliveryNote.customer_id,
                Customer.name.label("customer_name"),
                CustomerSite.site_name.label("customer_site_name"),
                DeliveryNote.sales_order_id,
                SalesOrder.order_no,
                Branch.name.label("branch_name"),
                Location.name.label("location_name"),
                Principal.name.label("principal_name"),
                DeliveryNote.status,
                func.coalesce(totals.c.total_qty, 0).label("total_qty"),
                func.coalesce(totals.c.qty_invoiced, 0).label("qty_invoiced"),
                DeliveryNote.created_at,
            )
            .join(Customer, Customer.id == DeliveryNote.customer_id)
            .join(Branch, Branch.id == DeliveryNote.branch_id)
            .join(Location, Location.id == DeliveryNote.from_location_id)
            .join(Principal, Principal.id == DeliveryNote.principal_id)
            .outerjoin(CustomerSite, CustomerSite.id == DeliveryNote.customer_site_id)
            .outerjoin(SalesOrder, SalesOrder.id == DeliveryNote.sales_order_id)
            .outerjoin(totals, totals.c.delivery_note_id == DeliveryNote.id)
            .where(visible_branch(self._actor), *self._brands(DeliveryNote.principal_id))
        )

    def _brands(self, column: Any) -> list[Any]:
        return [] if self._actor.principal_ids is None else [column.in_(self._actor.principal_ids)]

    def search(self, query: DeliveryQuery) -> Page[DeliveryListItem]:
        statement = self._select()
        for value, column in (
            (query.status, DeliveryNote.status),
            (query.customer_id, DeliveryNote.customer_id),
            (query.sales_order_id, DeliveryNote.sales_order_id),
            (query.branch_id, DeliveryNote.branch_id),
            (query.location_id, DeliveryNote.from_location_id),
        ):
            if value is not None:
                statement = statement.where(column == value)
        if query.from_date is not None:
            statement = statement.where(DeliveryNote.delivery_date >= query.from_date)
        if query.to_date is not None:
            statement = statement.where(DeliveryNote.delivery_date <= query.to_date)
        if query.direct_only:
            statement = statement.where(DeliveryNote.sales_order_id.is_(None))
        if query.uninvoiced_only:
            statement = statement.where(
                DeliveryNote.status.in_(LIVE),
                select(DeliveryNoteLine.id)
                .where(DeliveryNoteLine.delivery_note_id == DeliveryNote.id,
                       DeliveryNoteLine.qty_invoiced < DeliveryNoteLine.quantity)
                .exists(),
            )  # fmt: skip
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    DeliveryNote.delivery_no.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                    SalesOrder.order_no.contains(term, autoescape=True),
                    DeliveryNote.vehicle_no.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {"deliveryDate": DeliveryNote.delivery_date, "deliveryNo": DeliveryNote.delivery_no,
             "customerName": Customer.name},
            default="-deliveryDate",
            tiebreaker=DeliveryNote.id.desc(),
        )  # fmt: skip
        return paginate(self._db, statement, query, DeliveryListItem)

    def get(self, note_id: int) -> DeliveryDetail:
        note = self._visible(note_id)
        posted, cancelled = aliased(AppUser), aliased(AppUser)
        header = (
            self._db.execute(
                self._select()
                .add_columns(
                    DeliveryNote.principal_id,
                    DeliveryNote.branch_id,
                    DeliveryNote.from_location_id.label("location_id"),
                    DeliveryNote.customer_site_id,
                    Company.legal_name.label("company_name"),
                    Company.address.label("company_address"),
                    Branch.address.label("branch_address"),
                    Location.address.label("location_address"),
                    Customer.code.label("customer_code"),
                    func.coalesce(CustomerSite.gstin, Customer.gstin).label("customer_gstin"),
                    func.coalesce(CustomerSite.site_contact_phone, Customer.primary_phone).label("customer_phone"),
                    DeliveryNote.ship_to_address,
                    DeliveryNote.delivery_reference,
                    DeliveryNote.vehicle_no,
                    DeliveryNote.transporter,
                    DeliveryNote.lr_no,
                    DeliveryNote.received_by_name,
                    DeliveryNote.recipient_phone,
                    DeliveryNote.remarks,
                    DeliveryNote.dispatched_at,
                    DeliveryNote.delivered_at,
                    posted.username.label("posted_by"),
                    cancelled.username.label("cancelled_by"),
                    DeliveryNote.cancelled_at,
                    DeliveryNote.cancel_reason,
                )
                .join(Company, Company.id == Branch.company_id)
                .outerjoin(posted, posted.id == DeliveryNote.posted_by_user_id)
                .outerjoin(cancelled, cancelled.id == DeliveryNote.cancelled_by_user_id)
                .where(DeliveryNote.id == note.id)
            )
            .mappings()
            .one()
        )
        batches: dict[int | None, list[DeliveryBatch]] = defaultdict(list)
        for line_id, lot_no, grn_no, grn_date, bin_code, quantity in self._db.execute(
            select(StockMove.source_line_id, StockLot.lot_no, StockLot.grn_no, StockLot.grn_date, Bin.code,
                   StockMove.quantity)
            .join(StockLot, StockLot.id == StockMove.stock_lot_id)
            .outerjoin(Bin, Bin.id == StockMove.bin_id)
            .where(StockMove.source_document_type == DOCUMENT, StockMove.source_document_id == note.id,
                   StockMove.quantity < 0)
            .order_by(StockMove.id)
        ).all():  # fmt: skip
            batches[line_id].append(
                DeliveryBatch(lot_no=lot_no, grn_no=grn_no, grn_date=grn_date, bin_code=bin_code, quantity=-quantity)
            )
        lines = [
            DeliveryLineOut(
                id=line.id,
                sales_order_line_id=line.sales_order_line_id,
                item_id=line.item_id,
                item_code=code,
                description=line.description or description,
                uom_code=uom,
                quantity=line.quantity,
                qty_invoiced=line.qty_invoiced,
                qty_to_invoice=max(line.quantity - line.qty_invoiced, ZERO),
                unit_price=line.unit_price,
                discount_pct=line.discount_pct,
                gst_pct=line.gst_pct,
                unit_cost=line.unit_cost,
                batches=batches.get(line.id, []),
            )
            for line, code, description, uom in self._db.execute(
                select(DeliveryNoteLine, Item.item_code, Item.description, Uom.code)
                .join(Item, Item.id == DeliveryNoteLine.item_id)
                .outerjoin(Uom, Uom.id == DeliveryNoteLine.uom_id)
                .where(DeliveryNoteLine.delivery_note_id == note.id)
                .order_by(DeliveryNoteLine.id)
            ).all()
        ]
        invoices = [
            DeliveryInvoice(id=i, invoice_no=n, invoice_date=d, total=t, status=s)
            for i, n, d, t, s in self._db.execute(
                select(SalesInvoice.id, SalesInvoice.invoice_no, SalesInvoice.invoice_date, SalesInvoice.total,
                       SalesInvoice.status)
                .where(
                    SalesInvoice.id.in_(
                        select(SalesInvoiceLine.sales_invoice_id)
                        .join(DeliveryNoteLine, DeliveryNoteLine.id == SalesInvoiceLine.delivery_note_line_id)
                        .where(DeliveryNoteLine.delivery_note_id == note.id)
                    )
                )
                .order_by(SalesInvoice.id)
            ).all()
        ]  # fmt: skip
        return DeliveryDetail.model_validate({**header, "lines": lines, "invoices": invoices})

    def uninvoiced(self, query: UninvoicedDeliveryQuery) -> list[UninvoicedDeliveryLine]:
        statement = (
            select(
                DeliveryNoteLine.id.label("delivery_note_line_id"),
                DeliveryNote.id.label("delivery_note_id"),
                DeliveryNote.delivery_no,
                DeliveryNote.delivery_date,
                DeliveryNote.sales_order_id,
                SalesOrder.order_no,
                DeliveryNoteLine.sales_order_line_id,
                DeliveryNote.principal_id,
                DeliveryNote.branch_id,
                DeliveryNoteLine.item_id,
                Item.item_code,
                func.coalesce(DeliveryNoteLine.description, Item.description).label("description"),
                Uom.code.label("uom_code"),
                DeliveryNoteLine.quantity.label("qty_delivered"),
                DeliveryNoteLine.qty_invoiced,
                (DeliveryNoteLine.quantity - DeliveryNoteLine.qty_invoiced).label("qty_to_invoice"),
                DeliveryNoteLine.unit_price,
                DeliveryNoteLine.discount_pct,
                DeliveryNoteLine.gst_pct,
            )
            .join(DeliveryNote, DeliveryNote.id == DeliveryNoteLine.delivery_note_id)
            .join(Item, Item.id == DeliveryNoteLine.item_id)
            .join(Branch, Branch.id == DeliveryNote.branch_id)
            .outerjoin(Uom, Uom.id == DeliveryNoteLine.uom_id)
            .outerjoin(SalesOrder, SalesOrder.id == DeliveryNote.sales_order_id)
            .where(
                DeliveryNote.customer_id == query.customer_id,
                DeliveryNote.status.in_(LIVE),
                DeliveryNoteLine.qty_invoiced < DeliveryNoteLine.quantity,
                visible_branch(self._actor),
                *self._brands(DeliveryNote.principal_id),
            )
            .order_by(DeliveryNote.delivery_date, DeliveryNote.id, DeliveryNoteLine.id)
        )
        if query.delivery_note_id is not None:
            statement = statement.where(DeliveryNote.id == query.delivery_note_id)
        if query.sales_order_id is not None:
            statement = statement.where(DeliveryNote.sales_order_id == query.sales_order_id)
        return [UninvoicedDeliveryLine.model_validate(r) for r in self._db.execute(statement).mappings().all()]

    # ------------------------------------------------------------------ helpers

    def _location(self, note: DeliveryNote) -> Location:
        location = self._db.get(Location, note.from_location_id)
        assert location is not None
        return location

    def _visible(self, note_id: int) -> DeliveryNote:
        note = self._db.get(DeliveryNote, note_id)
        if (
            note is None
            or not self._actor.can_use_branch(note.branch_id)
            or not self._actor.can_see_principal(note.principal_id)
        ):
            raise NotFound("Delivery note not found.")
        return note

    def _commit(self, message: str) -> None:
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists(message) from error
