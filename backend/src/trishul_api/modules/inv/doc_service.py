"""Stock documents, each posted to the stock ledger when saved.

  (GRN, goods received from a supplier, is in modules/pur/grn_service.py.)
  Opening stock  stock already on hand at go-live, entered with its original GRN number and date, so the
                 ageing is right from day one.
  Transfer       between branches, warehouses or racks (same location, different rack). Moves the same
                 batches, oldest GRN date first unless a batch is named, so their age carries on.
  Adjustment     + or - with a reason, by a user holding inv.stock.adjust (recorded as posted_by).
                 A decrease takes the oldest batch first (or the batch named); an increase adds to a named
                 batch or starts a new one dated on the adjustment.

Posted documents are not edited: a mistake is corrected with another transfer or adjustment, so the
history stays complete.
"""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, case, func, or_, select
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
    Item,
    Location,
    LookupType,
    LookupValue,
    LotBalance,
    StockAdjustment,
    StockAdjustmentLine,
    StockLot,
    StockMove,
    StockTransfer,
    StockTransferLine,
    Supplier,
    Uom,
    UomConversion,
)
from trishul_api.modules.inv.common import (
    ZERO,
    company_of_branch,
    now,
    rack_of,
    stock_item,
    stock_location,
    today,
    visible_location,
)
from trishul_api.modules.inv.doc_schemas import (
    AdjustmentCreate,
    AdjustmentDetail,
    AdjustmentLineOut,
    AdjustmentListItem,
    BatchMoved,
    DocumentQuery,
    LotListItem,
    LotQuery,
    OpeningStockCreate,
    TransferCreate,
    TransferDetail,
    TransferLineOut,
    TransferListItem,
)
from trishul_api.modules.inv.ledger import Source, StockLedger
from trishul_api.modules.inv.masters_service import ADJUSTMENT_REASON

_COST = Decimal("0.0001")
_QTY = Decimal("0.001")
_VALUE = Decimal("0.01")


def _err(field: str, message: str, detail: str | None = None) -> ApiError:
    return ApiError(message, errors={field: [detail or message]})


class DocumentService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ================================================================ opening stock

    def create_opening(self, data: OpeningStockCreate) -> list[LotListItem]:
        location = stock_location(self._db, self._actor, data.location_id)
        prepared = []
        for index, line in enumerate(data.lines):
            item = stock_item(self._db, self._actor, line.item_id, f"lines[{index}].itemId")
            bin_id = rack_of(self._db, location, line.bin_id, f"lines[{index}].binId")
            self._not_future(line.grn_date, f"lines[{index}].grnDate")
            if line.supplier_id is not None:
                supplier = self._db.get(Supplier, line.supplier_id)
                if supplier is None:
                    raise _err(f"lines[{index}].supplierId", "Choose a supplier from the list.")
            prepared.append((line, item, bin_id))
        company_id = company_of_branch(self._db, location.branch_id)
        ledger = StockLedger(self._db, company_id=company_id, user_id=self._actor.id, at=now())
        lot_ids = []
        for line, item, bin_id in prepared:
            lot = ledger.receive(
                item=item,
                location_id=location.id,
                bin_id=bin_id,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
                source_type="Opening",
                grn_no=line.grn_no,
                grn_date=line.grn_date,
                movement="OPENING",
                source=Source("OPENING", 0, line.grn_no),
                supplier_id=line.supplier_id,
                remarks=line.remarks,
            )
            lot_ids.append(lot.id)
        # The ledger rows name the batch itself as their document.
        for move in self._db.scalars(
            select(StockMove).where(StockMove.stock_lot_id.in_(lot_ids), StockMove.source_document_type == "OPENING")
        ):
            move.source_document_id = move.stock_lot_id or 0
        self._commit()
        return [lot for lot in self._lots(select_ids=lot_ids)]

    # ================================================================ batches

    def lots(self, query: LotQuery) -> Page[LotListItem]:
        statement = self._lot_select()
        if query.item_id is not None:
            statement = statement.where(StockLot.item_id == query.item_id)
        if query.source_type is not None:
            statement = statement.where(StockLot.source_type == query.source_type)
        if query.branch_id is not None:
            statement = statement.where(Location.branch_id == query.branch_id)
        if query.in_stock:
            statement = statement.where(self._on_hand_column() > 0)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    StockLot.lot_no.contains(term, autoescape=True),
                    StockLot.grn_no.contains(term, autoescape=True),
                    Item.item_code.contains(term, autoescape=True),
                    Item.description.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {"grnDate": StockLot.grn_date, "lotNo": StockLot.lot_no, "itemCode": Item.item_code},
            default="-grnDate",
            tiebreaker=StockLot.id.desc(),
        )
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = self._db.execute(statement.offset((query.page - 1) * query.page_size).limit(query.page_size)).mappings()
        return Page(
            items=[self._lot_item(row) for row in rows], total=total, page=query.page, page_size=query.page_size
        )

    def _lots(self, select_ids: Iterable[int]) -> list[LotListItem]:
        statement = self._lot_select().where(StockLot.id.in_(list(select_ids))).order_by(StockLot.id)
        return [self._lot_item(row) for row in self._db.execute(statement).mappings()]

    def _on_hand_column(self) -> Any:
        return (
            select(func.coalesce(func.sum(LotBalance.qty_on_hand), 0))
            .where(LotBalance.stock_lot_id == StockLot.id)
            .correlate(StockLot)
            .scalar_subquery()
        )

    def _lot_select(self) -> Select[*tuple[Any, ...]]:
        on_hand = self._on_hand_column()
        return (
            select(
                StockLot.id,
                StockLot.lot_no,
                StockLot.source_type,
                StockLot.item_id,
                Item.item_code,
                Item.description.label("item_description"),
                Uom.code.label("uom_code"),
                StockLot.grn_id,
                StockLot.grn_no,
                StockLot.grn_date,
                Supplier.name.label("supplier_name"),
                Location.name.label("received_location_name"),
                Branch.name.label("received_branch_name"),
                StockLot.unit_cost,
                StockLot.qty_received,
                on_hand.label("qty_on_hand"),
                (on_hand * StockLot.unit_cost).label("value_on_hand"),
                StockLot.remarks,
                StockLot.created_at,
            )
            .join(Item, Item.id == StockLot.item_id)
            .join(Uom, Uom.id == Item.uom_id)
            .join(Location, Location.id == StockLot.received_location_id)
            .join(Branch, Branch.id == Location.branch_id)
            .outerjoin(Supplier, Supplier.id == StockLot.supplier_id)
            .where(visible_location(self._actor))
        )

    @staticmethod
    def _lot_item(row: Any) -> LotListItem:
        return LotListItem.model_validate({**row, "age_days": (today() - row["grn_date"]).days})

    # ================================================================ transfers

    def create_transfer(self, data: TransferCreate) -> TransferDetail:
        source = stock_location(self._db, self._actor, data.from_location_id, "fromLocationId")
        target = stock_location(self._db, self._actor, data.to_location_id, "toLocationId")
        same_place = source.id == target.id
        company_id = company_of_branch(self._db, source.branch_id)
        if company_of_branch(self._db, target.branch_id) != company_id:
            raise _err("toLocationId", "Stock can only be transferred within one company.")
        transfer_date = data.transfer_date or today()
        self._not_future(transfer_date, "transferDate")

        prepared = []
        for index, line in enumerate(data.lines):
            item = stock_item(self._db, self._actor, line.item_id, f"lines[{index}].itemId")
            from_bin = rack_of(self._db, source, line.from_bin_id, f"lines[{index}].fromBinId")
            to_bin = rack_of(self._db, target, line.to_bin_id, f"lines[{index}].toBinId")
            if same_place and (from_bin is None or to_bin is None or from_bin == to_bin):
                raise _err(
                    f"lines[{index}].toBinId",
                    "Within one location, choose the rack to move from and a different rack to move to.",
                )
            self._check_lot(line.stock_lot_id, item, f"lines[{index}].stockLotId")
            prepared.append((line, item, from_bin, to_bin))

        at = now()
        transfer = StockTransfer(
            transfer_no=next_document_no(
                self._db, company_id=company_id, document_type="STOCK_TRANSFER", branch_id=source.branch_id
            ),
            from_location_id=source.id,
            to_location_id=target.id,
            transfer_date=transfer_date,
            status="Received",
            dispatched_at=at,
            received_at=at,
            remarks=data.remarks,
            created_by_user_id=self._actor.id,
        )
        self._db.add(transfer)
        self._db.flush()
        ledger = StockLedger(self._db, company_id=company_id, user_id=self._actor.id, at=at)
        for line, item, from_bin, to_bin in prepared:
            row = StockTransferLine(
                stock_transfer_id=transfer.id,
                item_id=item.id,
                qty_sent=line.quantity,
                qty_received=line.quantity,
                from_bin_id=from_bin,
                to_bin_id=to_bin,
                created_by_user_id=self._actor.id,
            )
            self._db.add(row)
            self._db.flush()
            document = Source("STOCK_TRANSFER", transfer.id, transfer.transfer_no, row.id)
            taken = ledger.take(
                item=item,
                location_id=source.id,
                bin_id=from_bin,
                quantity=line.quantity,
                movement="TRANSFER_OUT",
                source=document,
                lot_id=line.stock_lot_id,
                location_label=source.name,
            )
            value = ZERO
            for portion in taken:
                ledger.put(portion.lot, target.id, to_bin, portion.quantity, "TRANSFER_IN", document)
                value += portion.quantity * portion.lot.unit_cost
            row.unit_value = (value / line.quantity).quantize(_COST)
            row.taxable_value = value.quantize(_VALUE)
        self._commit()
        return self.transfer(transfer.id)

    def transfers(self, query: DocumentQuery) -> Page[TransferListItem]:
        statement = self._transfer_select()
        if query.branch_id is not None:
            statement = statement.where(
                or_(self._from_loc.branch_id == query.branch_id, self._to_loc.branch_id == query.branch_id)
            )
        if query.location_id is not None:
            statement = statement.where(
                or_(
                    StockTransfer.from_location_id == query.location_id,
                    StockTransfer.to_location_id == query.location_id,
                )
            )
        if query.from_date is not None:
            statement = statement.where(StockTransfer.transfer_date >= query.from_date)
        if query.to_date is not None:
            statement = statement.where(StockTransfer.transfer_date <= query.to_date)
        if query.search:
            statement = statement.where(StockTransfer.transfer_no.contains(query.search.strip(), autoescape=True))
        statement = order_by_sort(
            statement,
            query.sort,
            {"transferDate": StockTransfer.transfer_date, "transferNo": StockTransfer.transfer_no},
            default="-transferDate",
            tiebreaker=StockTransfer.id.desc(),
        )
        return paginate(self._db, statement, query, TransferListItem)

    def transfer(self, transfer_id: int) -> TransferDetail:
        header = (
            self._db.execute(
                self._transfer_select()
                .add_columns(StockTransfer.remarks, AppUser.username.label("created_by"))
                .outerjoin(AppUser, AppUser.id == StockTransfer.created_by_user_id)
                .where(StockTransfer.id == transfer_id)
            )
            .mappings()
            .first()
        )
        if header is None:
            raise NotFound("Transfer not found.")
        from_bin, to_bin = aliased(Bin), aliased(Bin)
        lines = [
            TransferLineOut.model_validate(row)
            for row in self._db.execute(
                select(
                    StockTransferLine.id,
                    StockTransferLine.item_id,
                    Item.item_code,
                    Item.description.label("item_description"),
                    Uom.code.label("uom_code"),
                    StockTransferLine.qty_sent.label("quantity"),
                    from_bin.code.label("from_bin_code"),
                    to_bin.code.label("to_bin_code"),
                    StockTransferLine.taxable_value.label("value"),
                )
                .join(Item, Item.id == StockTransferLine.item_id)
                .join(Uom, Uom.id == Item.uom_id)
                .outerjoin(from_bin, from_bin.id == StockTransferLine.from_bin_id)
                .outerjoin(to_bin, to_bin.id == StockTransferLine.to_bin_id)
                .where(StockTransferLine.stock_transfer_id == transfer_id)
                .order_by(StockTransferLine.id)
            ).mappings()
        ]
        batches = self._batches("STOCK_TRANSFER", transfer_id, incoming_only=True)
        return TransferDetail.model_validate(
            {
                **header,
                "lines": lines,
                "batches": batches,
                "total_value": sum((b.value for b in batches), ZERO),
            }
        )

    def _transfer_select(self) -> Select[*tuple[Any, ...]]:
        self._from_loc, self._to_loc = aliased(Location), aliased(Location)
        from_branch, to_branch = aliased(Branch), aliased(Branch)
        totals = (
            select(
                StockTransferLine.stock_transfer_id,
                func.count(StockTransferLine.id).label("line_count"),
                func.sum(StockTransferLine.qty_sent).label("total_qty"),
            )
            .group_by(StockTransferLine.stock_transfer_id)
            .subquery()
        )
        statement = (
            select(
                StockTransfer.id,
                StockTransfer.transfer_no,
                StockTransfer.transfer_date,
                StockTransfer.from_location_id,
                self._from_loc.name.label("from_location_name"),
                from_branch.name.label("from_branch_name"),
                StockTransfer.to_location_id,
                self._to_loc.name.label("to_location_name"),
                to_branch.name.label("to_branch_name"),
                func.coalesce(totals.c.line_count, 0).label("line_count"),
                func.coalesce(totals.c.total_qty, 0).label("total_qty"),
                StockTransfer.status,
                StockTransfer.created_at,
            )
            .join(self._from_loc, self._from_loc.id == StockTransfer.from_location_id)
            .join(from_branch, from_branch.id == self._from_loc.branch_id)
            .join(self._to_loc, self._to_loc.id == StockTransfer.to_location_id)
            .join(to_branch, to_branch.id == self._to_loc.branch_id)
            .outerjoin(totals, totals.c.stock_transfer_id == StockTransfer.id)
        )
        if self._actor.branch_ids is not None:
            statement = statement.where(
                or_(
                    self._from_loc.branch_id.in_(self._actor.branch_ids),
                    self._to_loc.branch_id.in_(self._actor.branch_ids),
                )
            )
        return statement

    # ================================================================ adjustments

    def create_adjustment(self, data: AdjustmentCreate) -> AdjustmentDetail:
        location = stock_location(self._db, self._actor, data.location_id)
        reason = self._db.execute(
            select(LookupValue)
            .join(LookupType, LookupType.id == LookupValue.lookup_type_id)
            .where(LookupValue.id == data.reason_id, LookupType.code == ADJUSTMENT_REASON, LookupValue.is_active)
        ).scalar_one_or_none()
        if reason is None:
            raise _err("reasonId", "Choose a reason for the adjustment.")
        adjustment_date = data.adjustment_date or today()
        self._not_future(adjustment_date, "adjustmentDate")
        prepared = []
        for index, line in enumerate(data.lines):
            item = stock_item(self._db, self._actor, line.item_id, f"lines[{index}].itemId")
            bin_id = rack_of(self._db, location, line.bin_id, f"lines[{index}].binId")
            self._check_lot(line.stock_lot_id, item, f"lines[{index}].stockLotId")
            prepared.append((line, item, bin_id))

        company_id = company_of_branch(self._db, location.branch_id)
        at = now()
        adjustment = StockAdjustment(
            adjustment_no=next_document_no(
                self._db, company_id=company_id, document_type="STOCK_ADJUSTMENT", branch_id=location.branch_id
            ),
            location_id=location.id,
            adjustment_date=adjustment_date,
            reason_lookup_id=reason.id,
            status="Posted",
            remarks=data.remarks,
            posted_at=at,
            posted_by_user_id=self._actor.id,
            created_by_user_id=self._actor.id,
        )
        self._db.add(adjustment)
        self._db.flush()
        ledger = StockLedger(self._db, company_id=company_id, user_id=self._actor.id, at=at)
        for line, item, bin_id in prepared:
            row = StockAdjustmentLine(
                stock_adjustment_id=adjustment.id,
                item_id=item.id,
                bin_id=bin_id,
                stock_lot_id=line.stock_lot_id,
                qty_change=line.qty_change,
                remarks=line.remarks,
                created_by_user_id=self._actor.id,
            )
            self._db.add(row)
            self._db.flush()
            document = Source("STOCK_ADJUSTMENT", adjustment.id, adjustment.adjustment_no, row.id)
            if line.qty_change > 0:
                if line.stock_lot_id is not None:
                    lot = self._db.get(StockLot, line.stock_lot_id)
                    assert lot is not None  # checked above
                    ledger.put(lot, location.id, bin_id, line.qty_change, "ADJUST_IN", document)
                else:
                    cost = line.unit_cost
                    if cost is None:
                        cost = item.standard_cost or item.last_purchase_cost or ZERO
                    lot = ledger.receive(
                        item=item,
                        location_id=location.id,
                        bin_id=bin_id,
                        quantity=line.qty_change,
                        unit_cost=cost,
                        source_type="Adjustment",
                        grn_no=adjustment.adjustment_no,
                        grn_date=adjustment_date,
                        movement="ADJUST_IN",
                        source=document,
                        stock_adjustment_id=adjustment.id,
                        remarks=line.remarks,
                    )
                    row.stock_lot_id = lot.id
                row.unit_cost = lot.unit_cost
            else:
                taken = ledger.take(
                    item=item,
                    location_id=location.id,
                    bin_id=bin_id,
                    quantity=-line.qty_change,
                    movement="ADJUST_OUT",
                    source=document,
                    lot_id=line.stock_lot_id,
                    location_label=location.name,
                )
                value = sum((p.quantity * p.lot.unit_cost for p in taken), ZERO)
                row.unit_cost = (value / -line.qty_change).quantize(_COST)
        self._commit()
        return self.adjustment(adjustment.id)

    def adjustments(self, query: DocumentQuery) -> Page[AdjustmentListItem]:
        statement = self._adjustment_select().where(visible_location(self._actor))
        if query.branch_id is not None:
            statement = statement.where(Location.branch_id == query.branch_id)
        if query.location_id is not None:
            statement = statement.where(StockAdjustment.location_id == query.location_id)
        if query.from_date is not None:
            statement = statement.where(StockAdjustment.adjustment_date >= query.from_date)
        if query.to_date is not None:
            statement = statement.where(StockAdjustment.adjustment_date <= query.to_date)
        if query.search:
            statement = statement.where(StockAdjustment.adjustment_no.contains(query.search.strip(), autoescape=True))
        statement = order_by_sort(
            statement,
            query.sort,
            {"adjustmentDate": StockAdjustment.adjustment_date, "adjustmentNo": StockAdjustment.adjustment_no},
            default="-adjustmentDate",
            tiebreaker=StockAdjustment.id.desc(),
        )
        return paginate(self._db, statement, query, AdjustmentListItem)

    def adjustment(self, adjustment_id: int) -> AdjustmentDetail:
        header = (
            self._db.execute(
                self._adjustment_select()
                .add_columns(StockAdjustment.remarks)
                .where(StockAdjustment.id == adjustment_id, visible_location(self._actor))
            )
            .mappings()
            .first()
        )
        if header is None:
            raise NotFound("Adjustment not found.")
        lines = [
            AdjustmentLineOut.model_validate(row)
            for row in self._db.execute(
                select(
                    StockAdjustmentLine.id,
                    StockAdjustmentLine.item_id,
                    Item.item_code,
                    Item.description.label("item_description"),
                    Uom.code.label("uom_code"),
                    StockAdjustmentLine.qty_change,
                    Bin.code.label("bin_code"),
                    StockAdjustmentLine.unit_cost,
                    StockAdjustmentLine.remarks,
                )
                .join(Item, Item.id == StockAdjustmentLine.item_id)
                .join(Uom, Uom.id == Item.uom_id)
                .outerjoin(Bin, Bin.id == StockAdjustmentLine.bin_id)
                .where(StockAdjustmentLine.stock_adjustment_id == adjustment_id)
                .order_by(StockAdjustmentLine.id)
            ).mappings()
        ]
        batches = self._batches("STOCK_ADJUSTMENT", adjustment_id, incoming_only=False)
        return AdjustmentDetail.model_validate(
            {
                **header,
                "lines": lines,
                "batches": batches,
                "value_change": sum((b.value for b in batches), ZERO),
            }
        )

    def _adjustment_select(self) -> Select[*tuple[Any, ...]]:
        totals = (
            select(
                StockAdjustmentLine.stock_adjustment_id,
                func.count(StockAdjustmentLine.id).label("line_count"),
                func.sum(case((StockAdjustmentLine.qty_change > 0, StockAdjustmentLine.qty_change), else_=0)).label(
                    "qty_in"
                ),
                func.sum(case((StockAdjustmentLine.qty_change < 0, -StockAdjustmentLine.qty_change), else_=0)).label(
                    "qty_out"
                ),
            )
            .group_by(StockAdjustmentLine.stock_adjustment_id)
            .subquery()
        )
        return (
            select(
                StockAdjustment.id,
                StockAdjustment.adjustment_no,
                StockAdjustment.adjustment_date,
                StockAdjustment.location_id,
                Location.name.label("location_name"),
                Branch.name.label("branch_name"),
                LookupValue.label.label("reason"),
                func.coalesce(totals.c.line_count, 0).label("line_count"),
                func.coalesce(totals.c.qty_in, 0).label("qty_in"),
                func.coalesce(totals.c.qty_out, 0).label("qty_out"),
                StockAdjustment.status,
                AppUser.username.label("posted_by"),
                StockAdjustment.posted_at,
            )
            .join(Location, Location.id == StockAdjustment.location_id)
            .join(Branch, Branch.id == Location.branch_id)
            .join(LookupValue, LookupValue.id == StockAdjustment.reason_lookup_id)
            .outerjoin(AppUser, AppUser.id == StockAdjustment.posted_by_user_id)
            .outerjoin(totals, totals.c.stock_adjustment_id == StockAdjustment.id)
        )

    # ================================================================ helpers

    def _batches(self, document_type: str, document_id: int, *, incoming_only: bool) -> list[BatchMoved]:
        statement = (
            select(
                StockMove.source_line_id.label("line_id"),
                StockMove.stock_lot_id,
                StockLot.lot_no,
                StockLot.grn_no,
                StockLot.grn_date,
                Bin.code.label("bin_code"),
                StockMove.quantity,
                StockMove.unit_cost,
                StockMove.value,
            )
            .join(StockLot, StockLot.id == StockMove.stock_lot_id)
            .outerjoin(Bin, Bin.id == StockMove.bin_id)
            .where(StockMove.source_document_type == document_type, StockMove.source_document_id == document_id)
            .order_by(StockMove.source_line_id, StockMove.id)
        )
        if incoming_only:
            statement = statement.where(StockMove.quantity > 0)
        return [
            BatchMoved.model_validate({**row, "unit_cost": row["unit_cost"] or ZERO, "value": row["value"] or ZERO})
            for row in self._db.execute(statement).mappings()
        ]

    def unit_factor(self, item: Item, uom_id: int | None, field: str) -> Decimal:
        """Stock units in one received unit."""
        if uom_id is None or uom_id == item.uom_id:
            return Decimal(1)

        def find(item_id: int | None, from_uom: int, to_uom: int) -> Decimal | None:
            return self._db.scalar(
                select(UomConversion.factor).where(
                    UomConversion.is_active,
                    UomConversion.from_uom_id == from_uom,
                    UomConversion.to_uom_id == to_uom,
                    UomConversion.item_id.is_(None) if item_id is None else UomConversion.item_id == item_id,
                )
            )

        for item_id in (item.id, None):
            factor = find(item_id, uom_id, item.uom_id)
            if factor:
                return Decimal(factor)
            reverse = find(item_id, item.uom_id, uom_id)
            if reverse:
                return Decimal(1) / Decimal(reverse)
        raise _err(field, f"There is no conversion from that unit to {item.item_code}'s stock unit. Add one first.")

    def _check_lot(self, lot_id: int | None, item: Item, field: str) -> None:
        if lot_id is None:
            return
        lot = self._db.get(StockLot, lot_id)
        if lot is None or lot.item_id != item.id:
            raise _err(field, f"That batch is not a batch of {item.item_code}.")

    @staticmethod
    def _not_future(day: date, field: str) -> None:
        if day > today():
            raise _err(field, "The date can't be in the future.")

    def _commit(self) -> None:
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            # Stock went below zero (CHECK) or a document number clashed: someone posted at the same time.
            raise Conflict("Stock changed while this was being saved. Check the quantities and try again.") from error
