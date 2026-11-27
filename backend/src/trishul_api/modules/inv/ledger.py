"""The stock ledger: the only code that changes stock.

Stock is held per GRN batch (inv.stock_lot) and place (inv.lot_balance: location + rack). Every change
writes one inv.stock_move row (insert only) naming the batch, and keeps inv.stock_balance (per item,
location and rack) in step for screens that need totals.

  receive()  a new batch (GRN line, opening stock, stock found on adjustment) placed at a location
  put()      quantity of an existing batch arriving at a place (transfer in, adjustment +)
  take()     quantity leaving a place, oldest GRN date first unless a batch is named

A transfer is take() at the source then put() of the same batches at the destination, so the batch and
its GRN date never change: inventory age keeps counting from the original receipt.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.orm import Session

from trishul_api.common.errors import ApiError
from trishul_api.db.models import (
    Bin,
    Item,
    Location,
    LotBalance,
    MovementType,
    StockBalance,
    StockLot,
    StockLotSourceType,
    StockMove,
    StorageRack,
)
from trishul_api.modules.inv.common import ZERO

_QTY = Decimal("0.001")
# Cancellations put stock back where it was taken from, even if that bin was blocked or filled since.
_RETURNS_TO_ORIGIN = frozenset({"SALES_RETURN"})
_VALUE = Decimal("0.01")


@dataclass(frozen=True)
class Source:
    """The document a movement belongs to, written on every stock_move row."""

    document_type: str  # GRN, OPENING, STOCK_TRANSFER, STOCK_ADJUSTMENT
    document_id: int
    reference: str | None
    line_id: int | None = None


def not_blocked() -> Any:
    """LotBalance rows kept without a bin, or in a bin that is not blocked and not on a blocked rack: the stock a
    take without a named bin (and a pick list) may use."""
    free_bin = (
        select(Bin.id)
        .outerjoin(StorageRack, StorageRack.id == Bin.storage_rack_id)
        .where(
            Bin.id == LotBalance.bin_id,
            Bin.is_blocked == false(),
            or_(StorageRack.id.is_(None), StorageRack.is_blocked == false()),
        )
        .exists()
    )
    return or_(LotBalance.bin_id.is_(None), free_bin)


@dataclass(frozen=True)
class Taken:
    """Quantity of one batch taken from one place."""

    lot: StockLot
    bin_id: int | None
    quantity: Decimal


class StockLedger:
    def __init__(self, db: Session, *, company_id: int, user_id: int, at: datetime, as_found: bool = False) -> None:
        """as_found: a physical count records stock where it was found, so the bin rules (blocked, single item,
        capacity) are not applied to what it adds."""
        self._db = db
        self._as_found = as_found
        self._company_id = company_id
        self._user_id = user_id
        self._at = at
        self._movement_ids: dict[str, int] = {}

    # ------------------------------------------------------------------ in

    def receive(
        self,
        *,
        item: Item,
        location_id: int,
        bin_id: int | None,
        quantity: Decimal,
        unit_cost: Decimal,
        source_type: StockLotSourceType,
        grn_no: str,
        grn_date: date,
        movement: str,
        source: Source,
        supplier_id: int | None = None,
        grn_id: int | None = None,
        grn_line_id: int | None = None,
        stock_adjustment_id: int | None = None,
        remarks: str | None = None,
    ) -> StockLot:
        """A new batch whose age starts on grn_date, placed at the location (and rack)."""
        lot = StockLot(
            company_id=self._company_id,
            item_id=item.id,
            lot_no=f"N{uuid.uuid4().hex}",  # unique placeholder, replaced below once the id is known
            source_type=source_type,
            grn_id=grn_id,
            grn_line_id=grn_line_id,
            stock_adjustment_id=stock_adjustment_id,
            grn_no=grn_no,
            grn_date=grn_date,
            supplier_id=supplier_id,
            received_location_id=location_id,
            unit_cost=unit_cost,
            qty_received=quantity,
            remarks=remarks,
            created_by_user_id=self._user_id,
        )
        self._db.add(lot)
        self._db.flush()
        lot.lot_no = f"LOT{lot.id:07d}"
        self.put(lot, location_id, bin_id, quantity, movement, source)
        return lot

    def put(
        self, lot: StockLot, location_id: int, bin_id: int | None, quantity: Decimal, movement: str, source: Source
    ) -> None:
        """Quantity of an existing batch arriving at a place."""
        if quantity <= 0:
            raise ApiError("Quantity must be more than zero.")
        if movement not in _RETURNS_TO_ORIGIN and not self._as_found:
            self._check_place(lot.item_id, location_id, bin_id, quantity)
        balance = self._lot_balance(lot, location_id, bin_id)
        balance.qty_on_hand = balance.qty_on_hand + quantity
        balance.last_movement_at = self._at
        balance.updated_at = self._at
        balance.updated_by_user_id = self._user_id
        self._item_balance(lot.item_id, location_id, bin_id, quantity, lot.unit_cost)
        self._move(lot, location_id, bin_id, quantity, movement, source)

    # ------------------------------------------------------------------ out

    def take(
        self,
        *,
        item: Item,
        location_id: int,
        bin_id: int | None,
        quantity: Decimal,
        movement: str,
        source: Source,
        lot_id: int | None = None,
        location_label: str = "this location",
        unbinned_only: bool = False,
    ) -> list[Taken]:
        """Takes quantity from a place, oldest GRN date first (or only from lot_id).

        bin_id None takes from any rack of the location except blocked bins and racks (their stock leaves only
        when the bin is named), or with unbinned_only only stock kept without a bin.
        Fails, changing nothing, if there is not enough.
        """
        if quantity <= 0:
            raise ApiError("Quantity must be more than zero.")
        statement = (
            select(LotBalance, StockLot)
            .join(StockLot, StockLot.id == LotBalance.stock_lot_id)
            .where(
                LotBalance.item_id == item.id,
                LotBalance.location_id == location_id,
                LotBalance.qty_on_hand > 0,
            )
            .order_by(StockLot.grn_date, StockLot.id, LotBalance.id)
            # Hold the rows until commit so two users can't take the same stock.
            .with_hint(LotBalance, "WITH (UPDLOCK, ROWLOCK)", "mssql")
        )
        if bin_id is not None:
            statement = statement.where(LotBalance.bin_id == bin_id)
        elif unbinned_only:
            statement = statement.where(LotBalance.bin_id.is_(None))
        else:
            statement = statement.where(not_blocked())
        if lot_id is not None:
            statement = statement.where(LotBalance.stock_lot_id == lot_id)
        rows = self._db.execute(statement).all()

        available = sum((balance.qty_on_hand for balance, _ in rows), ZERO)
        if available < quantity:
            where = location_label
            if bin_id is not None:
                rack = self._db.get(Bin, bin_id)
                where += f", rack {rack.code if rack else bin_id}"
            elif unbinned_only:
                where += " without a bin"
            elif self._blocked_qty(item.id, location_id, lot_id) > 0:
                where += " outside blocked bins"
            batch = " in that batch" if lot_id is not None else ""
            raise ApiError(
                f"Only {_qty(available)} of {item.item_code} in stock at {where}{batch}; {_qty(quantity)} needed.",
                errors={"quantity": [f"Only {_qty(available)} available."]},
            )

        taken: list[Taken] = []
        left = quantity
        for balance, lot in rows:
            if left <= 0:
                break
            portion = min(left, balance.qty_on_hand)
            balance.qty_on_hand = balance.qty_on_hand - portion
            balance.last_movement_at = self._at
            balance.updated_at = self._at
            balance.updated_by_user_id = self._user_id
            self._item_balance(item.id, location_id, balance.bin_id, -portion, None)
            self._move(lot, location_id, balance.bin_id, -portion, movement, source)
            taken.append(Taken(lot=lot, bin_id=balance.bin_id, quantity=portion))
            left -= portion
        return taken

    # ------------------------------------------------------------------ helpers

    def _blocked_qty(self, item_id: int, location_id: int, lot_id: int | None) -> Decimal:
        statement = select(func.coalesce(func.sum(LotBalance.qty_on_hand), 0)).where(
            LotBalance.item_id == item_id,
            LotBalance.location_id == location_id,
            LotBalance.qty_on_hand > 0,
            and_(LotBalance.bin_id.is_not(None), ~not_blocked()),
        )
        if lot_id is not None:
            statement = statement.where(LotBalance.stock_lot_id == lot_id)
        return Decimal(self._db.scalar(statement) or 0)

    def _check_place(self, item_id: int, location_id: int, bin_id: int | None, quantity: Decimal) -> None:
        """Stock may arrive here: a bin when the location requires one; the bin (and its rack) not blocked;
        a single-item bin holding no other item; the bin's maximum quantity not exceeded."""
        if bin_id is None:
            location = self._db.get(Location, location_id)
            if location is not None and location.requires_bin:
                raise ApiError(
                    f"Location {location.code} keeps all stock in bins; choose a bin.",
                    errors={"binId": ["Required at this location."]},
                )
            return
        place = self._db.get(Bin, bin_id)
        if place is None:
            return
        rack = self._db.get(StorageRack, place.storage_rack_id) if place.storage_rack_id is not None else None
        if place.is_blocked or (rack is not None and rack.is_blocked):
            reason = place.blocked_reason if place.is_blocked else (rack.blocked_reason if rack else None)
            raise ApiError(
                f"Bin {place.code} is blocked{f' ({reason})' if reason else ''}; nothing can be put into it.",
                errors={"binId": ["Blocked."]},
            )
        if place.bin_type != "Single item" and place.max_qty is None:
            return
        held = self._db.execute(
            select(StockBalance.item_id, StockBalance.qty_on_hand).where(
                StockBalance.bin_id == bin_id, StockBalance.qty_on_hand > 0
            )
        ).all()
        if place.bin_type == "Single item" and any(other != item_id for other, _ in held):
            raise ApiError(
                f"Bin {place.code} holds only one item and already has another one.",
                errors={"binId": ["Single-item bin in use by another item."]},
            )
        if place.max_qty is not None:
            total = sum((qty for _, qty in held), ZERO) + quantity
            if total > place.max_qty:
                free = max(place.max_qty - (total - quantity), ZERO)
                raise ApiError(
                    f"Bin {place.code} holds at most {_qty(place.max_qty)}; only {_qty(free)} more fits.",
                    errors={"binId": ["Over its capacity."]},
                )

    def _lot_balance(self, lot: StockLot, location_id: int, bin_id: int | None) -> LotBalance:
        statement = select(LotBalance).where(
            LotBalance.stock_lot_id == lot.id,
            LotBalance.location_id == location_id,
            LotBalance.bin_id.is_(None) if bin_id is None else LotBalance.bin_id == bin_id,
        )
        balance = self._db.scalars(statement.with_hint(LotBalance, "WITH (UPDLOCK, ROWLOCK)", "mssql")).first()
        if balance is None:
            balance = LotBalance(
                stock_lot_id=lot.id,
                item_id=lot.item_id,
                location_id=location_id,
                bin_id=bin_id,
                qty_on_hand=ZERO,
                created_by_user_id=self._user_id,
            )
            self._db.add(balance)
        return balance

    def _item_balance(
        self, item_id: int, location_id: int, bin_id: int | None, change: Decimal, unit_cost: Decimal | None
    ) -> None:
        """Keeps inv.stock_balance (item totals per place) in step; avg_cost is a moving average of receipts."""
        statement = select(StockBalance).where(
            StockBalance.item_id == item_id,
            StockBalance.location_id == location_id,
            StockBalance.bin_id.is_(None) if bin_id is None else StockBalance.bin_id == bin_id,
        )
        row = self._db.scalars(statement.with_hint(StockBalance, "WITH (UPDLOCK, ROWLOCK)", "mssql")).first()
        if row is None:
            row = StockBalance(
                item_id=item_id,
                location_id=location_id,
                bin_id=bin_id,
                qty_on_hand=ZERO,
                qty_reserved=ZERO,
                qty_in_transit=ZERO,
                created_by_user_id=self._user_id,
            )
            self._db.add(row)
        before = row.qty_on_hand or ZERO
        after = before + change
        if change > 0 and unit_cost is not None:
            old_value = before * (row.avg_cost or unit_cost)
            row.avg_cost = (
                ((old_value + change * unit_cost) / after).quantize(Decimal("0.0001")) if after else unit_cost
            )
        row.qty_on_hand = after
        row.last_movement_at = self._at
        row.updated_at = self._at
        row.updated_by_user_id = self._user_id

    def _move(
        self, lot: StockLot, location_id: int, bin_id: int | None, quantity: Decimal, movement: str, source: Source
    ) -> None:
        self._db.add(
            StockMove(
                company_id=self._company_id,
                move_at=self._at,
                movement_type_id=self._movement_id(movement),
                item_id=lot.item_id,
                location_id=location_id,
                bin_id=bin_id,
                stock_lot_id=lot.id,
                quantity=quantity,
                unit_cost=lot.unit_cost,
                value=(quantity * lot.unit_cost).quantize(_VALUE),
                source_document_type=source.document_type,
                source_document_id=source.document_id,
                source_line_id=source.line_id,
                reference=source.reference,
                performed_by_user_id=self._user_id,
            )
        )

    def _movement_id(self, code: str) -> int:
        if code not in self._movement_ids:
            movement_id = self._db.scalar(select(MovementType.id).where(MovementType.code == code))
            if movement_id is None:
                raise ApiError(f"Movement type {code} is not set up.")
            self._movement_ids[code] = int(movement_id)
        return self._movement_ids[code]


def _qty(value: Decimal) -> str:
    """1.000 -> 1, 2.500 -> 2.5"""
    text = format(value.quantize(_QTY), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text
