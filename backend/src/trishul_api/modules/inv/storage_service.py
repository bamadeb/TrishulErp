"""Warehouse storage, phase 1: racks of a location with levels x positions of bins, and stock by rack and bin.

Every location stays flexible. Stock may be kept
  * in a bin of a rack     BBSR-MAIN-R01-L2-B05 (generated when the rack is created or grows);
  * in a loose bin or spot a bin with no rack, e.g. a yard spot BBSR-YARD-S03 (masters: "racks" endpoints);
  * at the location only   no bin at all, unless the location is set to require one.
The stock itself stays in inv.lot_balance / inv.stock_balance, changed only by the stock ledger.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Select, case, func, or_, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.common.paging import SortColumns, order_by_sort
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    Bin,
    Branch,
    Item,
    Location,
    LotBalance,
    StockBalance,
    StockLot,
    StorageRack,
    Uom,
)
from trishul_api.modules.inv.common import COST_VIEWERS, now, visible_location
from trishul_api.modules.inv.storage_schemas import (
    BinStockQuery,
    BinStockRow,
    StorageRackCreate,
    StorageRackOut,
    StorageRackQuery,
    StorageRackUpdate,
)


def bin_code(rack_code: str, level: int, position: int) -> str:
    """BBSR-MAIN-R01 + level 2 + position 5 -> BBSR-MAIN-R01-L2-B05."""
    return f"{rack_code}-L{level}-B{position:02d}"


class StorageService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ racks

    def racks(self, query: StorageRackQuery) -> list[StorageRackOut]:
        statement = self._rack_select().where(visible_location(self._actor))
        if query.location_id is not None:
            statement = statement.where(StorageRack.location_id == query.location_id)
        if query.status != "all":
            statement = statement.where(StorageRack.is_active == (query.status == "active"))
        statement = statement.order_by(Location.code, StorageRack.short_code)
        return [StorageRackOut.model_validate(r) for r in self._db.execute(statement).mappings()]

    def get(self, rack_id: int) -> StorageRackOut:
        row = self._db.execute(self._rack_select().where(StorageRack.id == rack_id)).mappings().one_or_none()
        if row is None or not self._actor.can_use_branch(self._location(row["location_id"]).branch_id):
            raise NotFound("Rack not found.")
        return StorageRackOut.model_validate(row)

    def create(self, location_id: int, data: StorageRackCreate) -> StorageRackOut:
        location = self._location(location_id)
        short = data.short_code.upper()
        code = f"{location.code}-{short}"
        if self._db.scalar(select(StorageRack.id).where(StorageRack.code == code).limit(1)) is not None:
            raise AlreadyExists(f"Rack {short} already exists in {location.code}.")
        rack = StorageRack(
            location_id=location.id,
            code=code,
            short_code=short,
            name=data.name,
            rack_type=data.rack_type,
            levels=data.levels,
            positions=data.positions,
            max_weight_kg=data.max_weight_kg,
            created_by_user_id=self._actor.id,
        )
        self._db.add(rack)
        self._db.flush()
        self._lay_out(rack, location, data.bin_type)
        self._commit(f"A bin code of rack {code} is already used by another bin.")
        return self.get(rack.id)

    def update(self, rack_id: int, expected: bytes, data: StorageRackUpdate) -> StorageRackOut:
        rack = self._db.get(StorageRack, rack_id)
        if rack is None:
            raise NotFound("Rack not found.")
        location = self._location(rack.location_id)
        check_row_version(rack.row_version, expected)
        changed = data.model_fields_set
        if data.is_active is False and rack.is_active:
            self._refuse_if_stock(rack, "deactivate it", None, None)
            for bin_ in self._bins(rack):
                bin_.is_active = False
            rack.is_active = False
        elif data.is_active is True and not rack.is_active:
            rack.is_active = True
        for field in ("name", "rack_type", "is_blocked"):
            if field in changed and getattr(data, field) is not None:
                setattr(rack, field, getattr(data, field))
        if "max_weight_kg" in changed:
            rack.max_weight_kg = data.max_weight_kg
        if "blocked_reason" in changed or "is_blocked" in changed:
            rack.blocked_reason = data.blocked_reason if rack.is_blocked else None
        levels = data.levels if data.levels is not None else rack.levels
        positions = data.positions if data.positions is not None else rack.positions
        if (levels, positions) != (rack.levels, rack.positions) or (data.is_active is True and rack.is_active):
            self._refuse_if_stock(rack, "shrink it", levels, positions)
            rack.levels, rack.positions = levels, positions
            self._lay_out(rack, location, "Mixed")
        rack.updated_at = now()
        rack.updated_by_user_id = self._actor.id
        self._commit(f"A bin code of rack {rack.code} is already used by another bin.")
        return self.get(rack.id)

    def _lay_out(self, rack: StorageRack, location: Location, bin_type: str) -> None:
        """Every level x position has an active bin (new or reactivated); bins outside them are deactivated."""
        existing = {(b.level_no, b.position_no): b for b in self._bins(rack)}
        stamp = now()
        for level in range(1, rack.levels + 1):
            for position in range(1, rack.positions + 1):
                found = existing.pop((level, position), None)
                if found is not None:
                    if rack.is_active and not found.is_active:
                        found.is_active = True
                        found.updated_at = stamp
                        found.updated_by_user_id = self._actor.id
                    continue
                self._db.add(
                    Bin(
                        location_id=location.id,
                        code=bin_code(rack.code, level, position),
                        rack=rack.short_code,
                        shelf=f"L{level}",
                        storage_rack_id=rack.id,
                        level_no=level,
                        position_no=position,
                        bin_type=bin_type,
                        is_active=rack.is_active,
                        created_by_user_id=self._actor.id,
                    )
                )
        for left_over in existing.values():  # beyond the new size; checked empty before
            if left_over.is_active:
                left_over.is_active = False
                left_over.updated_at = stamp
                left_over.updated_by_user_id = self._actor.id

    def _refuse_if_stock(self, rack: StorageRack, doing: str, levels: int | None, positions: int | None) -> None:
        """No stock may sit in a bin that would be dropped (all of them when levels/positions are None)."""
        statement = (
            select(Bin.code, func.sum(StockBalance.qty_on_hand))
            .join(StockBalance, StockBalance.bin_id == Bin.id)
            .where(Bin.storage_rack_id == rack.id, StockBalance.qty_on_hand > 0)
            .group_by(Bin.code)
            .order_by(Bin.code)
        )
        if levels is not None and positions is not None:
            statement = statement.where(or_(Bin.level_no > levels, Bin.position_no > positions))
        held = self._db.execute(statement.limit(5)).all()
        if held:
            codes = ", ".join(code for code, _ in held)
            raise ApiError(f"Cannot {doing}: stock is still kept in {codes}. Move it out first, or block the rack.")

    def _bins(self, rack: StorageRack) -> list[Bin]:
        return list(self._db.scalars(select(Bin).where(Bin.storage_rack_id == rack.id)).all())

    def _rack_select(self) -> Select[*tuple[Any, ...]]:
        stock = (
            select(
                StockBalance.bin_id,
                func.sum(StockBalance.qty_on_hand).label("qty"),
            )
            .where(StockBalance.qty_on_hand > 0)
            .group_by(StockBalance.bin_id)
            .subquery()
        )
        counts = (
            select(
                Bin.storage_rack_id,
                func.count(Bin.id).label("bin_count"),
                func.sum(case((stock.c.qty > 0, 1), else_=0)).label("occupied_bins"),
                func.sum(case((Bin.is_blocked == true(), 1), else_=0)).label("blocked_bins"),
                func.sum(func.coalesce(stock.c.qty, 0)).label("qty_on_hand"),
            )
            .outerjoin(stock, stock.c.bin_id == Bin.id)
            .where(Bin.storage_rack_id.is_not(None), Bin.is_active)
            .group_by(Bin.storage_rack_id)
            .subquery()
        )
        return (
            select(
                StorageRack.id,
                StorageRack.location_id,
                Location.code.label("location_code"),
                StorageRack.code,
                StorageRack.short_code,
                StorageRack.name,
                StorageRack.rack_type,
                StorageRack.levels,
                StorageRack.positions,
                StorageRack.max_weight_kg,
                StorageRack.is_blocked,
                StorageRack.blocked_reason,
                func.coalesce(counts.c.bin_count, 0).label("bin_count"),
                func.coalesce(counts.c.occupied_bins, 0).label("occupied_bins"),
                func.coalesce(counts.c.blocked_bins, 0).label("blocked_bins"),
                func.coalesce(counts.c.qty_on_hand, 0).label("qty_on_hand"),
                StorageRack.is_active,
                StorageRack.row_version,
            )
            .join(Location, Location.id == StorageRack.location_id)
            .outerjoin(counts, counts.c.storage_rack_id == StorageRack.id)
        )

    def _location(self, location_id: int) -> Location:
        location = self._db.get(Location, location_id)
        if location is None or not self._actor.can_use_branch(location.branch_id):
            raise NotFound("Location not found.")
        return location

    def _commit(self, duplicate: str) -> None:
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists(duplicate) from error

    # ------------------------------------------------------------------ stock by rack and bin

    def bin_stock(self, query: BinStockQuery) -> Page[BinStockRow]:
        """Stock per location, bin and item from the GRN batches, with value at batch cost and the oldest GRN date.

        Boolean columns are compared explicitly (`== true()`, rendered `= 1`): SQL Server refuses a bare BIT
        as a CASE condition."""
        quantity = func.sum(LotBalance.qty_on_hand)
        statement: Select[*tuple[Any, ...]] = (
            select(
                Location.id.label("location_id"),
                Location.code.label("location_code"),
                Branch.name.label("branch_name"),
                StorageRack.id.label("storage_rack_id"),
                StorageRack.code.label("storage_rack_code"),
                Bin.id.label("bin_id"),
                Bin.code.label("bin_code"),
                Bin.bin_type,
                func.max(case((or_(Bin.is_blocked == true(), StorageRack.is_blocked == true()), 1), else_=0)).label(
                    "bin_blocked"
                ),
                Item.id.label("item_id"),
                Item.item_code,
                Item.description.label("item_description"),
                Uom.code.label("uom_code"),
                quantity.label("qty_on_hand"),
                func.sum(LotBalance.qty_on_hand * StockLot.unit_cost).label("value"),
                func.min(StockLot.grn_date).label("oldest_grn_date"),
            )
            .join(StockLot, StockLot.id == LotBalance.stock_lot_id)
            .join(Item, Item.id == LotBalance.item_id)
            .join(Uom, Uom.id == Item.uom_id)
            .join(Location, Location.id == LotBalance.location_id)
            .join(Branch, Branch.id == Location.branch_id)
            .outerjoin(Bin, Bin.id == LotBalance.bin_id)
            .outerjoin(StorageRack, StorageRack.id == Bin.storage_rack_id)
            .where(LotBalance.qty_on_hand > 0, visible_location(self._actor))
            .group_by(
                Location.id,
                Location.code,
                Branch.name,
                StorageRack.id,
                StorageRack.code,
                Bin.id,
                Bin.code,
                Bin.bin_type,
                Item.id,
                Item.item_code,
                Item.description,
                Uom.code,
            )
        )
        if self._actor.principal_ids is not None:
            statement = statement.where(
                or_(Item.principal_id.is_(None), Item.principal_id.in_(self._actor.principal_ids or [0]))
            )
        if query.location_id is not None:
            statement = statement.where(LotBalance.location_id == query.location_id)
        if query.storage_rack_id is not None:
            statement = statement.where(Bin.storage_rack_id == query.storage_rack_id)
        if query.bin_id is not None:
            statement = statement.where(LotBalance.bin_id == query.bin_id)
        if query.item_id is not None:
            statement = statement.where(LotBalance.item_id == query.item_id)
        if query.without_bin:
            statement = statement.where(LotBalance.bin_id.is_(None))
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Item.item_code.contains(term, autoescape=True),
                    Item.description.contains(term, autoescape=True),
                    Item.oem_part_number.contains(term, autoescape=True),
                    Bin.code.contains(term, autoescape=True),
                )
            )
        sort: SortColumns = {
            "binCode": Bin.code,
            "itemCode": Item.item_code,
            "qtyOnHand": quantity,
            "oldestGrnDate": func.min(StockLot.grn_date),
            "locationCode": Location.code,
        }
        statement = order_by_sort(
            statement, query.sort, sort, default="binCode", tiebreaker=Item.id.asc()
        )  # not a sort column: SQL Server refuses one twice
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = self._db.execute(statement.offset((query.page - 1) * query.page_size).limit(query.page_size))
        see_cost = self._actor.can(*COST_VIEWERS)
        items = []
        for r in rows.mappings():
            row = BinStockRow.model_validate({**r, "bin_blocked": bool(r["bin_blocked"])})
            row.value = Decimal(r["value"]).quantize(Decimal("0.01")) if see_cost and r["value"] is not None else None
            items.append(row)
        return Page(items=items, total=total, page=query.page, page_size=query.page_size)
