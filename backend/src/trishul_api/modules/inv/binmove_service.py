"""Put-away and bin moves (stock between bins of one location), and an item's storage type and home bins.

Put-away list: the GRN batches sitting in a receiving bin, or kept at the location without a bin, each with a
suggested bin:
  1. the item's home bin in that location (storage rule);
  2. a bin that already holds the item;
  3. an empty bin: a single-item bin first for an Individual item, a shared / mixed bin for a Grouped one.
Blocked, inactive and receiving bins are never suggested.

A bin move is posted at once: the ledger takes the quantity from the source bin (oldest GRN batch first, or the
batch named) and puts the same batches into the target bin, so FIFO and ageing never reset. The target bin's
rules (blocked, single item, capacity) are checked by the ledger like any other arrival.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.common.paging import SortColumns, order_by_sort
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Bin,
    BinMove,
    BinMoveLine,
    Employee,
    Item,
    ItemStorageRule,
    Location,
    LotBalance,
    StockBalance,
    StockLot,
    Uom,
)
from trishul_api.modules.inv.binmove_schemas import (
    BinMoveCreate,
    BinMoveLineOut,
    BinMoveOut,
    BinMoveQuery,
    ItemStorageOut,
    ItemStorageUpdate,
    PutAwayRow,
    StorageRuleOut,
)
from trishul_api.modules.inv.common import (
    company_of_branch,
    now,
    rack_of,
    stock_item,
    visible_item,
    visible_location,
)
from trishul_api.modules.inv.ledger import Source, StockLedger

BINMOVE_MANAGE = "inv.binmove.manage"


class BinMoveService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ put-away list

    def putaway(self, location_id: int) -> list[PutAwayRow]:
        location = self._location(location_id)
        rows = self._db.execute(
            select(
                LotBalance.item_id,
                Item.item_code,
                Item.description,
                Uom.code.label("uom_code"),
                Item.storage_type,
                StockLot.id.label("stock_lot_id"),
                StockLot.lot_no,
                StockLot.grn_no,
                StockLot.grn_date,
                LotBalance.bin_id,
                Bin.code.label("bin_code"),
                LotBalance.qty_on_hand,
            )
            .join(StockLot, StockLot.id == LotBalance.stock_lot_id)
            .join(Item, Item.id == LotBalance.item_id)
            .join(Uom, Uom.id == Item.uom_id)
            .outerjoin(Bin, Bin.id == LotBalance.bin_id)
            .where(
                LotBalance.location_id == location.id,
                LotBalance.qty_on_hand > 0,
                or_(LotBalance.bin_id.is_(None), Bin.is_receiving == True),  # noqa: E712 - SQL Server needs = 1
                visible_item(self._actor),
            )
            .order_by(StockLot.grn_date, StockLot.id)
        ).all()
        suggestions: dict[int, tuple[int, str, str] | None] = {}
        out = []
        for r in rows:
            if r.item_id not in suggestions:
                suggestions[r.item_id] = self._suggest(location.id, r.item_id, r.storage_type)
            hint = suggestions[r.item_id]
            out.append(
                PutAwayRow(
                    item_id=r.item_id,
                    item_code=r.item_code,
                    item_description=r.description,
                    uom_code=r.uom_code,
                    storage_type=r.storage_type,
                    stock_lot_id=r.stock_lot_id,
                    lot_no=r.lot_no,
                    grn_no=r.grn_no,
                    grn_date=r.grn_date,
                    from_bin_id=r.bin_id,
                    from_bin_code=r.bin_code,
                    qty_on_hand=r.qty_on_hand,
                    suggested_bin_id=hint[0] if hint else None,
                    suggested_bin_code=hint[1] if hint else None,
                    suggestion=hint[2] if hint else None,
                )
            )
        return out

    def _usable(self) -> Any:
        return (Bin.is_active == True) & (Bin.is_blocked == False) & (Bin.is_receiving == False)  # noqa: E712

    def _suggest(self, location_id: int, item_id: int, storage_type: str | None) -> tuple[int, str, str] | None:
        home = self._db.execute(
            select(Bin.id, Bin.code)
            .join(ItemStorageRule, ItemStorageRule.bin_id == Bin.id)
            .where(
                ItemStorageRule.item_id == item_id,
                ItemStorageRule.location_id == location_id,
                ItemStorageRule.is_active == True,  # noqa: E712
                self._usable(),
            )
            .order_by(Bin.code)
            .limit(1)
        ).first()
        if home is not None:
            return home.id, home.code, "Home bin"
        stored = self._db.execute(
            select(Bin.id, Bin.code)
            .join(StockBalance, StockBalance.bin_id == Bin.id)
            .where(
                StockBalance.item_id == item_id,
                StockBalance.location_id == location_id,
                StockBalance.qty_on_hand > 0,
                self._usable(),
            )
            .order_by(StockBalance.qty_on_hand.desc(), Bin.code)
            .limit(1)
        ).first()
        if stored is not None:
            return stored.id, stored.code, "Already stored here"
        occupied = select(StockBalance.bin_id).where(StockBalance.qty_on_hand > 0, StockBalance.bin_id.is_not(None))
        preferred = ("Single item",) if storage_type == "Individual" else ("Shared", "Mixed")
        empty = self._db.execute(
            select(Bin.id, Bin.code)
            .where(Bin.location_id == location_id, self._usable(), Bin.id.not_in(occupied))
            .order_by(case((Bin.bin_type.in_(preferred), 0), else_=1), Bin.code)
            .limit(1)
        ).first()
        if empty is not None:
            return empty.id, empty.code, "Empty bin"
        return None

    # ------------------------------------------------------------------ moves

    def move(self, data: BinMoveCreate) -> BinMoveOut:
        location = self._location(data.location_id)
        move = BinMove(
            location_id=location.id,
            move_type=data.move_type,
            note=data.note,
            moved_by_user_id=self._actor.id,
            moved_at=now(),
        )
        self._db.add(move)
        self._db.flush()
        move.move_no = f"BM-{move.id:06d}"
        ledger = StockLedger(
            self._db, company_id=company_of_branch(self._db, location.branch_id), user_id=self._actor.id, at=now()
        )
        for index, line in enumerate(data.lines):
            field = f"lines[{index}]"
            item = stock_item(self._db, self._actor, line.item_id, f"{field}.itemId")
            to_bin = rack_of(self._db, location, line.to_bin_id, f"{field}.toBinId")
            from_bin = rack_of(self._db, location, line.from_bin_id, f"{field}.fromBinId")
            if to_bin == from_bin:
                raise ApiError(
                    "The stock is already in that bin.", errors={f"{field}.toBinId": ["Same as the source."]}
                )
            row = BinMoveLine(
                bin_move_id=move.id,
                item_id=item.id,
                stock_lot_id=line.stock_lot_id,
                from_bin_id=from_bin,
                to_bin_id=to_bin,
                quantity=line.quantity,
            )
            self._db.add(row)
            self._db.flush()
            source = Source("BIN_MOVE", move.id, move.move_no, row.id)
            taken = ledger.take(
                item=item,
                location_id=location.id,
                bin_id=from_bin,
                quantity=line.quantity,
                movement="BIN_OUT",
                source=source,
                lot_id=line.stock_lot_id,
                location_label=location.code,
                unbinned_only=from_bin is None,
            )
            for portion in taken:
                ledger.put(portion.lot, location.id, to_bin, portion.quantity, "BIN_IN", source)
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists("The move could not be saved; try again.") from error
        return self.get(move.id)

    def get(self, move_id: int) -> BinMoveOut:
        row = self._db.execute(self._select().where(BinMove.id == move_id)).mappings().one_or_none()
        if row is None or not self._can_see(row["location_id"]):
            raise NotFound("Bin move not found.")
        from_bin, to_bin = Bin.__table__.alias("from_bin"), Bin.__table__.alias("to_bin")
        lines = self._db.execute(
            select(
                BinMoveLine.item_id,
                Item.item_code,
                Item.description.label("item_description"),
                StockLot.lot_no,
                from_bin.c.code.label("from_bin_code"),
                to_bin.c.code.label("to_bin_code"),
                BinMoveLine.quantity,
            )
            .join(Item, Item.id == BinMoveLine.item_id)
            .outerjoin(StockLot, StockLot.id == BinMoveLine.stock_lot_id)
            .outerjoin(from_bin, from_bin.c.id == BinMoveLine.from_bin_id)
            .join(to_bin, to_bin.c.id == BinMoveLine.to_bin_id)
            .where(BinMoveLine.bin_move_id == move_id)
            .order_by(BinMoveLine.id)
        ).mappings()
        return BinMoveOut.model_validate({**row, "lines": [BinMoveLineOut.model_validate(x) for x in lines]})

    def search(self, query: BinMoveQuery) -> Page[BinMoveOut]:
        statement = self._select().where(visible_location(self._actor))
        if query.location_id is not None:
            statement = statement.where(BinMove.location_id == query.location_id)
        if query.move_type is not None:
            statement = statement.where(BinMove.move_type == query.move_type)
        if query.item_id is not None:
            statement = statement.where(
                BinMove.id.in_(select(BinMoveLine.bin_move_id).where(BinMoveLine.item_id == query.item_id))
            )
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(BinMove.move_no.contains(term, autoescape=True), BinMove.note.contains(term, autoescape=True))
            )
        sort: SortColumns = {"movedAt": BinMove.moved_at, "moveNo": BinMove.move_no}
        statement = order_by_sort(statement, query.sort, sort, default="-movedAt", tiebreaker=BinMove.id.desc())
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = self._db.execute(statement.offset((query.page - 1) * query.page_size).limit(query.page_size))
        return Page(
            items=[BinMoveOut.model_validate(r) for r in rows.mappings()],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def _select(self) -> Select[*tuple[Any, ...]]:
        name = func.coalesce(Employee.first_name, "") + " " + func.coalesce(Employee.last_name, "")
        lines = (
            select(BinMoveLine.bin_move_id, func.count(BinMoveLine.id).label("line_count"))
            .group_by(BinMoveLine.bin_move_id)
            .subquery()
        )
        return (
            select(
                BinMove.id,
                BinMove.move_no,
                BinMove.location_id,
                Location.code.label("location_code"),
                BinMove.move_type,
                BinMove.note,
                func.coalesce(func.nullif(func.trim(name), ""), AppUser.username).label("moved_by_name"),
                BinMove.moved_at,
                func.coalesce(lines.c.line_count, 0).label("line_count"),
            )
            .join(Location, Location.id == BinMove.location_id)
            .outerjoin(lines, lines.c.bin_move_id == BinMove.id)
            .outerjoin(AppUser, AppUser.id == BinMove.moved_by_user_id)
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
        )

    # ------------------------------------------------------------------ item storage type and home bins

    def storage(self, item_id: int) -> ItemStorageOut:
        item = self._item(item_id)
        held = (
            select(StockBalance.bin_id, func.sum(StockBalance.qty_on_hand).label("qty"))
            .where(StockBalance.item_id == item.id)
            .group_by(StockBalance.bin_id)
            .subquery()
        )
        rows = self._db.execute(
            select(
                ItemStorageRule.id,
                ItemStorageRule.location_id,
                Location.code.label("location_code"),
                ItemStorageRule.bin_id,
                Bin.code.label("bin_code"),
                ItemStorageRule.min_qty,
                ItemStorageRule.max_qty,
                func.coalesce(held.c.qty, 0).label("qty_on_hand"),
            )
            .join(Location, Location.id == ItemStorageRule.location_id)
            .join(Bin, Bin.id == ItemStorageRule.bin_id)
            .outerjoin(held, held.c.bin_id == ItemStorageRule.bin_id)
            .where(ItemStorageRule.item_id == item.id, ItemStorageRule.is_active == True)  # noqa: E712
            .order_by(Location.code, Bin.code)
        ).mappings()
        return ItemStorageOut(
            item_id=item.id,
            storage_type=item.storage_type,
            rules=[StorageRuleOut.model_validate(r) for r in rows],
            row_version=item.row_version,
        )

    def set_storage(self, item_id: int, expected: bytes, data: ItemStorageUpdate) -> ItemStorageOut:
        item = self._item(item_id)
        check_row_version(item.row_version, expected)
        wanted: dict[int, Any] = {}
        for index, rule in enumerate(data.rules):
            location = self._location(rule.location_id)
            bin_id = rack_of(self._db, location, rule.bin_id, f"rules[{index}].binId")
            assert bin_id is not None
            if rule.min_qty is not None and rule.max_qty is not None and rule.min_qty > rule.max_qty:
                raise ApiError(
                    "The minimum is more than the maximum.", errors={f"rules[{index}].minQty": ["Too high."]}
                )
            if bin_id in wanted:
                raise ApiError("A bin is listed twice.", errors={f"rules[{index}].binId": ["Listed twice."]})
            wanted[bin_id] = rule
        stamp = now()
        existing = {
            r.bin_id: r for r in self._db.scalars(select(ItemStorageRule).where(ItemStorageRule.item_id == item.id))
        }
        for bin_id, row in existing.items():
            if bin_id not in wanted and row.is_active:
                row.is_active = False
                row.updated_at, row.updated_by_user_id = stamp, self._actor.id
        for bin_id, rule in wanted.items():
            found = existing.get(bin_id)
            if found is None:
                found = ItemStorageRule(item_id=item.id, bin_id=bin_id, created_by_user_id=self._actor.id)
                self._db.add(found)
            else:
                found.updated_at, found.updated_by_user_id = stamp, self._actor.id
            found.location_id = rule.location_id
            found.min_qty, found.max_qty, found.is_active = rule.min_qty, rule.max_qty, True
        item.storage_type = data.storage_type
        item.updated_at, item.updated_by_user_id = stamp, self._actor.id
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists("The storage rules could not be saved; try again.") from error
        self._db.refresh(item)
        return self.storage(item.id)

    # ------------------------------------------------------------------ helpers

    def _location(self, location_id: int) -> Location:
        location = self._db.get(Location, location_id)
        if location is None or not self._actor.can_use_branch(location.branch_id):
            raise NotFound("Location not found.")
        return location

    def _can_see(self, location_id: int) -> bool:
        location = self._db.get(Location, location_id)
        return location is not None and self._actor.can_use_branch(location.branch_id)

    def _item(self, item_id: int) -> Item:
        item = self._db.scalar(select(Item).where(Item.id == item_id, visible_item(self._actor)))
        if item is None:
            raise NotFound("Item not found.")
        return item
