"""Goods receipt (GRN), moved here from inventory.

Each accepted line becomes a stock batch aged from the GRN date (inv.ledger). Against a purchase order:
the order must be approved and from the same supplier, each line names its order line, a line may not
receive more than is still pending, and the order becomes Part received / Received. Received quantity
on the order counts accepted goods only; rejected goods stay pending.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError, Conflict, NotFound
from trishul_api.common.numbering import next_document_no
from trishul_api.common.paging import order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Bin,
    Branch,
    Grn,
    GrnLine,
    Item,
    Location,
    LotBalance,
    PurchaseOrder,
    PurchaseOrderLine,
    StockLot,
    Supplier,
    Uom,
)
from trishul_api.modules.inv.common import company_of_branch, now, rack_of, stock_item, stock_location, visible_location
from trishul_api.modules.inv.doc_service import DocumentService
from trishul_api.modules.inv.ledger import Source, StockLedger
from trishul_api.modules.pur.common import ZERO, active_supplier
from trishul_api.modules.pur.grn_schemas import (
    GrnCreate,
    GrnDetail,
    GrnLineOut,
    GrnListItem,
    GrnQuery,
    UninvoicedLine,
    UninvoicedQuery,
)
from trishul_api.modules.pur.po_service import OPEN_FOR_RECEIPT

_COST = Decimal("0.0001")
_QTY = Decimal("0.001")
_DEFAULT_GST = Decimal(18)


def _err(field: str, message: str) -> ApiError:
    return ApiError(message, errors={field: [message]})


class GrnService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    def create(self, data: GrnCreate) -> GrnDetail:
        location = stock_location(self._db, self._actor, data.location_id)
        supplier = active_supplier(self._db, data.supplier_id)
        if data.grn_date > date.today():
            raise _err("grnDate", "The GRN date can't be in the future.")
        po = self._order(data, supplier.id)
        units = DocumentService(self._db, self._actor)
        lines = []
        pending: dict[int, Decimal] = {}
        for index, line in enumerate(data.lines):
            item = stock_item(self._db, self._actor, line.item_id, f"lines[{index}].itemId")
            factor = units.unit_factor(item, line.uom_id, f"lines[{index}].uomId")
            bin_id = rack_of(self._db, location, line.bin_id, f"lines[{index}].binId")
            order_line = self._order_line(po, line.purchase_order_line_id, item, index)
            if order_line is not None:
                left = pending.get(order_line.id, order_line.quantity - order_line.qty_received)
                accepted = (line.quantity * factor).quantize(_QTY)
                if accepted > left:
                    raise _err(
                        f"lines[{index}].quantity",
                        f"Only {_qty(left)} {item.item_code} is still to be received on {po.po_no if po else ''}.",
                    )
                pending[order_line.id] = left - accepted
            lines.append((line, item, factor, bin_id, order_line))

        company_id = company_of_branch(self._db, location.branch_id)
        at = now()
        grn = Grn(
            grn_no=next_document_no(self._db, company_id=company_id, document_type="GRN", branch_id=location.branch_id),
            branch_id=location.branch_id,
            supplier_id=supplier.id,
            purchase_order_id=po.id if po else None,
            principal_id=po.principal_id if po else None,
            grn_date=data.grn_date,
            location_id=location.id,
            supplier_invoice_no=data.supplier_invoice_no,
            supplier_invoice_date=data.supplier_invoice_date,
            vehicle_no=data.vehicle_no,
            lr_no=data.lr_no,
            remarks=data.remarks,
            status="Posted",
            grn_type="Regular",
            created_by_user_id=self._actor.id,
        )
        self._db.add(grn)
        self._db.flush()
        ledger = StockLedger(self._db, company_id=company_id, user_id=self._actor.id, at=at)
        for line, item, factor, bin_id, order_line in lines:
            accepted = (line.quantity * factor).quantize(_QTY)
            rejected = (line.rejected_qty * factor).quantize(_QTY)
            unit_cost = (line.unit_cost / factor).quantize(_COST, ROUND_HALF_UP)
            entered_in_other_unit = bool(line.uom_id and line.uom_id != item.uom_id)
            row = GrnLine(
                grn_id=grn.id,
                purchase_order_line_id=order_line.id if order_line else None,
                item_id=item.id,
                qty_received=accepted + rejected,
                qty_accepted=accepted,
                qty_rejected=rejected,
                bin_id=bin_id,
                unit_cost=unit_cost,
                rejection_reason=line.rejection_reason,
                entry_uom_id=line.uom_id if entered_in_other_unit else None,
                entry_qty=(line.quantity + line.rejected_qty) if entered_in_other_unit else None,
                created_by_user_id=self._actor.id,
            )
            self._db.add(row)
            self._db.flush()
            if accepted > 0:
                ledger.receive(
                    item=item,
                    location_id=location.id,
                    bin_id=bin_id,
                    quantity=accepted,
                    unit_cost=unit_cost,
                    source_type="GRN",
                    grn_no=grn.grn_no,
                    grn_date=grn.grn_date,
                    movement="GRN",
                    source=Source("GRN", grn.id, grn.grn_no, row.id),
                    supplier_id=supplier.id,
                    grn_id=grn.id,
                    grn_line_id=row.id,
                )
            if order_line is not None:
                order_line.qty_received = order_line.qty_received + accepted
                order_line.updated_at = at
            item.last_purchase_cost = unit_cost
            item.updated_at = at
            item.updated_by_user_id = self._actor.id
        if po is not None:
            self._db.flush()
            self._update_order_status(po)
        self._commit()
        return self.get(grn.id)

    def _order(self, data: GrnCreate, supplier_id: int) -> PurchaseOrder | None:
        if data.purchase_order_id is None:
            if any(line.purchase_order_line_id for line in data.lines):
                raise _err("purchaseOrderId", "Choose the purchase order the lines belong to.")
            return None
        po = self._db.get(PurchaseOrder, data.purchase_order_id)
        if po is None or not self._actor.can_use_branch(po.branch_id):
            raise _err("purchaseOrderId", "Purchase order not found.")
        if po.supplier_id != supplier_id:
            raise _err("supplierId", f"Order {po.po_no} is from another supplier.")
        if po.status not in OPEN_FOR_RECEIPT:
            raise Conflict(f"Order {po.po_no} is {po.status.lower()}; goods can't be received against it.")
        return po

    def _order_line(
        self, po: PurchaseOrder | None, line_id: int | None, item: Item, index: int
    ) -> PurchaseOrderLine | None:
        if po is None:
            return None
        if line_id is None:
            raise _err(f"lines[{index}].purchaseOrderLineId", f"Say which line of {po.po_no} this receives.")
        line = self._db.get(PurchaseOrderLine, line_id)
        if line is None or line.purchase_order_id != po.id:
            raise _err(f"lines[{index}].purchaseOrderLineId", f"That line is not on order {po.po_no}.")
        if line.item_id != item.id:
            raise _err(f"lines[{index}].itemId", "The item differs from the order line.")
        return line

    def _update_order_status(self, po: PurchaseOrder) -> None:
        lines = self._db.scalars(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == po.id)).all()
        if all(line.qty_received >= line.quantity for line in lines):
            po.status = "Received"
        elif any(line.qty_received > 0 for line in lines):
            po.status = "Part received"
        po.updated_at = now()
        po.updated_by_user_id = self._actor.id

    # ------------------------------------------------------------------ reads

    def search(self, query: GrnQuery) -> Page[GrnListItem]:
        statement = self._select().where(visible_location(self._actor))
        if query.branch_id is not None:
            statement = statement.where(Grn.branch_id == query.branch_id)
        if query.location_id is not None:
            statement = statement.where(Grn.location_id == query.location_id)
        if query.supplier_id is not None:
            statement = statement.where(Grn.supplier_id == query.supplier_id)
        if query.purchase_order_id is not None:
            statement = statement.where(Grn.purchase_order_id == query.purchase_order_id)
        if query.from_date is not None:
            statement = statement.where(Grn.grn_date >= query.from_date)
        if query.to_date is not None:
            statement = statement.where(Grn.grn_date <= query.to_date)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Grn.grn_no.contains(term, autoescape=True),
                    Supplier.name.contains(term, autoescape=True),
                    Grn.supplier_invoice_no.contains(term, autoescape=True),
                    PurchaseOrder.po_no.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {"grnDate": Grn.grn_date, "grnNo": Grn.grn_no, "supplierName": Supplier.name},
            default="-grnDate",
            tiebreaker=Grn.id.desc(),
        )
        return paginate(self._db, statement, query, GrnListItem)

    def get(self, grn_id: int) -> GrnDetail:
        header = (
            self._db.execute(
                self._select()
                .add_columns(
                    Grn.supplier_invoice_date,
                    Grn.vehicle_no,
                    Grn.lr_no,
                    Grn.remarks,
                    AppUser.username.label("created_by"),
                )
                .outerjoin(AppUser, AppUser.id == Grn.created_by_user_id)
                .where(Grn.id == grn_id, visible_location(self._actor))
            )
            .mappings()
            .first()
        )
        if header is None:
            raise NotFound("GRN not found.")
        remaining = (
            select(LotBalance.stock_lot_id, func.sum(LotBalance.qty_on_hand).label("qty"))
            .group_by(LotBalance.stock_lot_id)
            .subquery()
        )
        entry_uom = aliased(Uom)
        lines = (
            self._db.execute(
                select(
                    GrnLine.id,
                    GrnLine.item_id,
                    Item.item_code,
                    Item.description.label("item_description"),
                    Uom.code.label("uom_code"),
                    GrnLine.entry_qty,
                    entry_uom.code.label("entry_uom_code"),
                    GrnLine.qty_received,
                    GrnLine.qty_accepted,
                    GrnLine.qty_rejected,
                    GrnLine.qty_invoiced,
                    GrnLine.unit_cost,
                    (GrnLine.qty_accepted * GrnLine.unit_cost).label("value"),
                    Bin.code.label("bin_code"),
                    GrnLine.rejection_reason,
                    GrnLine.purchase_order_line_id,
                    StockLot.id.label("stock_lot_id"),
                    StockLot.lot_no,
                    func.coalesce(remaining.c.qty, 0).label("qty_remaining"),
                )
                .join(Item, Item.id == GrnLine.item_id)
                .join(Uom, Uom.id == Item.uom_id)
                .outerjoin(entry_uom, entry_uom.id == GrnLine.entry_uom_id)
                .outerjoin(Bin, Bin.id == GrnLine.bin_id)
                .outerjoin(StockLot, StockLot.grn_line_id == GrnLine.id)
                .outerjoin(remaining, remaining.c.stock_lot_id == StockLot.id)
                .where(GrnLine.grn_id == grn_id)
                .order_by(GrnLine.id)
            )
            .mappings()
            .all()
        )
        return GrnDetail.model_validate({**header, "lines": [GrnLineOut.model_validate(line) for line in lines]})

    def uninvoiced(self, query: UninvoicedQuery) -> list[UninvoicedLine]:
        statement = (
            select(GrnLine, Grn, Item.item_code, Item.description, Uom.code, PurchaseOrderLine, PurchaseOrder.po_no)
            .join(Grn, Grn.id == GrnLine.grn_id)
            .join(Location, Location.id == Grn.location_id)
            .join(Item, Item.id == GrnLine.item_id)
            .join(Uom, Uom.id == Item.uom_id)
            .outerjoin(PurchaseOrderLine, PurchaseOrderLine.id == GrnLine.purchase_order_line_id)
            .outerjoin(PurchaseOrder, PurchaseOrder.id == Grn.purchase_order_id)
            .where(
                Grn.supplier_id == query.supplier_id,
                Grn.status == "Posted",
                GrnLine.qty_accepted > GrnLine.qty_invoiced,
                visible_location(self._actor),
            )
            .order_by(Grn.grn_date, Grn.id, GrnLine.id)
        )
        if query.grn_id is not None:
            statement = statement.where(Grn.id == query.grn_id)
        out = []
        for line, grn, code, description, uom, order_line, po_no in self._db.execute(statement).all():
            out.append(
                UninvoicedLine(
                    grn_id=grn.id,
                    grn_no=grn.grn_no,
                    grn_date=grn.grn_date,
                    grn_line_id=line.id,
                    purchase_order_id=grn.purchase_order_id,
                    po_no=po_no,
                    purchase_order_line_id=line.purchase_order_line_id,
                    item_id=line.item_id,
                    item_code=code,
                    item_description=description,
                    uom_code=uom,
                    qty_accepted=line.qty_accepted,
                    qty_invoiced=line.qty_invoiced,
                    qty_to_invoice=line.qty_accepted - line.qty_invoiced,
                    unit_cost=line.unit_cost,
                    discount_pct=(order_line.discount_pct or ZERO) if order_line else ZERO,
                    unit_price=order_line.unit_price if order_line else line.unit_cost,
                    gst_pct=order_line.gst_pct if order_line else _DEFAULT_GST,
                )
            )
        return out

    def _select(self) -> Select[*tuple[Any, ...]]:
        totals = (
            select(
                GrnLine.grn_id,
                func.count(GrnLine.id).label("line_count"),
                func.sum(GrnLine.qty_accepted).label("total_qty"),
                func.sum(GrnLine.qty_accepted * GrnLine.unit_cost).label("total_value"),
            )
            .group_by(GrnLine.grn_id)
            .subquery()
        )
        return (
            select(
                Grn.id,
                Grn.grn_no,
                Grn.grn_date,
                Grn.branch_id,
                Branch.name.label("branch_name"),
                Grn.location_id,
                Location.name.label("location_name"),
                Grn.supplier_id,
                Supplier.name.label("supplier_name"),
                Grn.purchase_order_id,
                PurchaseOrder.po_no,
                Grn.supplier_invoice_no,
                func.coalesce(totals.c.line_count, 0).label("line_count"),
                func.coalesce(totals.c.total_qty, 0).label("total_qty"),
                func.coalesce(totals.c.total_value, 0).label("total_value"),
                Grn.status,
                Grn.created_at,
            )
            .join(Branch, Branch.id == Grn.branch_id)
            .join(Location, Location.id == Grn.location_id)
            .join(Supplier, Supplier.id == Grn.supplier_id)
            .outerjoin(PurchaseOrder, PurchaseOrder.id == Grn.purchase_order_id)
            .outerjoin(totals, totals.c.grn_id == Grn.id)
        )

    def _commit(self) -> None:
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise Conflict("Stock changed while this was being saved. Check the quantities and try again.") from error


def _qty(value: Decimal) -> str:
    text = format(value.quantize(_QTY), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text
