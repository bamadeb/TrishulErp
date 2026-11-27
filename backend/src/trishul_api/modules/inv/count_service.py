"""Physical stock counts (inv.stock_count): count sheets, counting, variance review and the posted adjustment.

  Open      created for a location (every bin and the stock kept without a bin: a Full count), one rack or a list
            of bins (Cycle). A line is made for each item and bin holding stock; counters scan or type what they
            find, adding lines for items found where the system has none. Nothing is frozen: each line's system
            quantity is read when it is counted. A blind count hides the system quantity until counting ends.
  Counted   counting finished (it can be reopened); the variances are reviewed, and lines whose bin had stock
            moving in or out after they were counted are flagged.
  Adjusted  the differences were posted as one stock adjustment (reason Count difference) by a user holding
            inv.count.approve. Gains go in where they were found, even in a blocked or full bin.
  Cancelled nothing posted.

The posted difference is counted - system quantity at counting time, so moves after a line was counted (a
delivery, a GRN) are not counted twice.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, case, func, or_, select, true
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
    Employee,
    Item,
    Location,
    LookupType,
    LookupValue,
    LotBalance,
    StockAdjustment,
    StockAdjustmentLine,
    StockBalance,
    StockCount,
    StockCountBin,
    StockCountLine,
    StockLot,
    StockMove,
    StorageRack,
    Uom,
)
from trishul_api.modules.inv.common import (
    COST_VIEWERS,
    ZERO,
    company_of_branch,
    now,
    rack_of,
    stock_item,
    stock_location,
    today,
    visible_location,
)
from trishul_api.modules.inv.count_schemas import (
    StockCountClose,
    StockCountCreate,
    StockCountEntry,
    StockCountLineOut,
    StockCountOut,
    StockCountQuery,
)
from trishul_api.modules.inv.ledger import Source, StockLedger
from trishul_api.modules.inv.masters_service import ADJUSTMENT_REASON

COUNT_MANAGE = "inv.count.manage"
COUNT_APPROVE = "inv.count.approve"
COUNT_REASON = "COUNT_DIFFERENCE"
_COST = Decimal("0.0001")
_VALUE = Decimal("0.01")


def _err(field: str, message: str) -> ApiError:
    return ApiError(message, errors={field: [message]})


def _user_name(user: Any, employee: Any) -> Any:
    name = func.coalesce(employee.first_name, "") + " " + func.coalesce(employee.last_name, "")
    return func.coalesce(func.nullif(func.trim(name), ""), user.username)


def _same_bin(column: Any, bin_id: int | None) -> ColumnElement[bool]:
    return column.is_(None) if bin_id is None else column == bin_id


class StockCountService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ count sheets

    def create(self, data: StockCountCreate) -> StockCountOut:
        location = stock_location(self._db, self._actor, data.location_id)
        bin_ids: list[int] = []
        if data.scope == "Rack":
            rack = self._db.get(StorageRack, data.storage_rack_id) if data.storage_rack_id else None
            if rack is None or rack.location_id != location.id:
                raise _err("storageRackId", "Choose a rack of this location.")
        elif data.scope == "Bins":
            if not data.bin_ids:
                raise _err("binIds", "Choose the bins to count.")
            for index, bin_id in enumerate(dict.fromkeys(data.bin_ids)):
                checked = rack_of(self._db, location, bin_id, f"binIds[{index}]")
                assert checked is not None
                bin_ids.append(checked)

        count = StockCount(
            count_no=uuid.uuid4().hex[:30],  # placeholder, replaced once the id is known
            location_id=location.id,
            count_date=data.count_date or today(),
            count_type="Full" if data.scope == "Location" else "Cycle",
            status="Open",
            scope=data.scope,
            storage_rack_id=data.storage_rack_id if data.scope == "Rack" else None,
            is_blind=data.is_blind,
            remarks=data.remarks,
            created_by_user_id=self._actor.id,
        )
        if count.count_date > today():
            raise _err("countDate", "The date can't be in the future.")
        self._db.add(count)
        self._db.flush()
        count.count_no = f"SC-{count.id:06d}"
        for bin_id in bin_ids:
            self._db.add(StockCountBin(stock_count_id=count.id, bin_id=bin_id))

        balances = select(StockBalance.item_id, StockBalance.bin_id, StockBalance.qty_on_hand).where(
            StockBalance.location_id == location.id,
            StockBalance.qty_on_hand > 0,
            self._balance_in_scope(count, bin_ids),
        )
        for item_id, bin_id, quantity in self._db.execute(balances).all():
            self._db.add(
                StockCountLine(
                    stock_count_id=count.id,
                    item_id=item_id,
                    bin_id=bin_id,
                    system_qty=quantity,
                    is_expected=True,
                    created_by_user_id=self._actor.id,
                )
            )
        self._commit()
        return self.get(count.id)

    def search(self, query: StockCountQuery) -> Page[StockCountOut]:
        statement = self._select().where(visible_location(self._actor))
        if query.location_id is not None:
            statement = statement.where(StockCount.location_id == query.location_id)
        if query.status is not None:
            statement = statement.where(StockCount.status == query.status)
        if query.search and query.search.strip():
            term = query.search.strip()
            statement = statement.where(
                or_(StockCount.count_no.contains(term, autoescape=True), Location.code.contains(term, autoescape=True))
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {"countDate": StockCount.count_date, "countNo": StockCount.count_no, "status": StockCount.status},
            default="-countDate",
            tiebreaker=StockCount.id.desc(),
        )
        page = paginate(self._db, statement, query, StockCountOut)
        page.items = [self._hide(item) for item in page.items]
        return page

    def get(self, count_id: int) -> StockCountOut:
        count = self._count(count_id)
        row = self._db.execute(self._select().where(StockCount.id == count.id)).mappings().one()
        out = StockCountOut.model_validate(row)
        if count.scope == "Bins":
            out.bin_codes = list(
                self._db.scalars(
                    select(Bin.code)
                    .join(StockCountBin, StockCountBin.bin_id == Bin.id)
                    .where(StockCountBin.stock_count_id == count.id)
                    .order_by(Bin.code)
                )
            )
        out.lines = self._lines(count)
        return self._hide(out)

    # ------------------------------------------------------------------ counting

    def count(self, count_id: int, entry: StockCountEntry) -> StockCountLineOut:
        count = self._count(count_id)
        self._expect(count, ("Open",), "counted")
        location = self._db.get(Location, count.location_id)
        assert location is not None
        item = stock_item(self._db, self._actor, entry.item_id)
        bin_id = rack_of(self._db, location, entry.bin_id, "binId")
        if not self._in_scope(count, bin_id):
            raise _err("binId", "That bin is not part of this count.")

        line = self._db.scalars(
            select(StockCountLine)
            .where(
                StockCountLine.stock_count_id == count.id,
                StockCountLine.item_id == item.id,
                _same_bin(StockCountLine.bin_id, bin_id),
            )
            .with_hint(StockCountLine, "WITH (UPDLOCK, ROWLOCK)", "mssql")
        ).first()
        if line is None:
            if bin_id is None and location.requires_bin:
                raise _err("binId", f"Location {location.code} keeps all stock in bins; scan or choose the bin.")
            line = StockCountLine(
                stock_count_id=count.id,
                item_id=item.id,
                bin_id=bin_id,
                system_qty=ZERO,
                is_expected=False,
                created_by_user_id=self._actor.id,
            )
            self._db.add(line)
        counted = entry.quantity if entry.mode == "set" else (line.counted_qty or ZERO) + entry.quantity
        self._record(line, counted)
        if entry.remarks is not None:
            line.remarks = entry.remarks
        self._db.flush()
        line_id = line.id
        self._commit()
        return self._hide_line(count, self._lines(count, line_id=line_id)[0])

    def close(self, count_id: int, data: StockCountClose) -> StockCountOut:
        count = self._count(count_id)
        self._expect(count, ("Open",), "finished")
        lines = list(self._db.scalars(select(StockCountLine).where(StockCountLine.stock_count_id == count.id)))
        if data.uncounted_as_zero:
            for line in lines:
                if line.counted_qty is None:
                    self._record(line, ZERO)
        elif not any(line.counted_qty is not None for line in lines):
            raise ApiError("Nothing has been counted yet.")
        count.status = "Counted"
        count.closed_at, count.closed_by_user_id = now(), self._actor.id
        self._touch(count)
        self._commit()
        return self.get(count.id)

    def reopen(self, count_id: int) -> StockCountOut:
        count = self._count(count_id)
        self._expect(count, ("Counted",), "reopened")
        count.status = "Open"
        count.closed_at = count.closed_by_user_id = None
        self._touch(count)
        self._commit()
        return self.get(count.id)

    def cancel(self, count_id: int) -> StockCountOut:
        count = self._count(count_id)
        self._expect(count, ("Open", "Counted"), "cancelled")
        count.status = "Cancelled"
        self._touch(count)
        self._commit()
        return self.get(count.id)

    # ------------------------------------------------------------------ posting the differences

    def post(self, count_id: int) -> StockCountOut:
        count = self._count(count_id)
        self._expect(count, ("Counted",), "posted")
        location = self._db.get(Location, count.location_id)
        assert location is not None
        differences = [
            line
            for line in self._db.scalars(
                select(StockCountLine)
                .where(StockCountLine.stock_count_id == count.id, StockCountLine.counted_qty.is_not(None))
                .order_by(StockCountLine.id)
            )
            if line.counted_qty is not None and line.counted_qty != line.system_qty
        ]
        at = now()
        if differences:
            reason = self._db.scalar(
                select(LookupValue.id)
                .join(LookupType, LookupType.id == LookupValue.lookup_type_id)
                .where(LookupType.code == ADJUSTMENT_REASON, LookupValue.code == COUNT_REASON)
            )
            if reason is None:
                raise ApiError(f"Add the adjustment reason {COUNT_REASON} (Count difference) first.")
            company_id = company_of_branch(self._db, location.branch_id)
            adjustment = StockAdjustment(
                adjustment_no=next_document_no(
                    self._db, company_id=company_id, document_type="STOCK_ADJUSTMENT", branch_id=location.branch_id
                ),
                location_id=location.id,
                adjustment_date=today(),
                reason_lookup_id=reason,
                stock_count_id=count.id,
                status="Posted",
                remarks=f"Physical count {count.count_no}",
                posted_at=at,
                posted_by_user_id=self._actor.id,
                created_by_user_id=self._actor.id,
            )
            self._db.add(adjustment)
            self._db.flush()
            ledger = StockLedger(self._db, company_id=company_id, user_id=self._actor.id, at=at, as_found=True)
            costs = self._costs(location.id, {line.item_id for line in differences})
            for line in differences:
                assert line.counted_qty is not None
                change = line.counted_qty - line.system_qty
                self._post_line(ledger, adjustment, location, count.count_no, line, change, costs)
        count.status = "Adjusted"
        count.posted_at, count.posted_by_user_id = at, self._actor.id
        self._touch(count)
        self._commit()
        return self.get(count.id)

    def _post_line(
        self,
        ledger: StockLedger,
        adjustment: StockAdjustment,
        location: Location,
        count_no: str,
        line: StockCountLine,
        change: Decimal,
        costs: dict[int, Decimal],
    ) -> None:
        item = self._db.get(Item, line.item_id)
        assert item is not None
        row = StockAdjustmentLine(
            stock_adjustment_id=adjustment.id,
            item_id=item.id,
            bin_id=line.bin_id,
            qty_change=change,
            remarks=f"Counted {line.counted_qty:f}, system {line.system_qty:f}",
            created_by_user_id=self._actor.id,
        )
        self._db.add(row)
        self._db.flush()
        source = Source("STOCK_ADJUSTMENT", adjustment.id, adjustment.adjustment_no, row.id)
        if change > 0:
            cost = costs.get(item.id) or item.standard_cost or item.last_purchase_cost or ZERO
            lot = ledger.receive(
                item=item,
                location_id=location.id,
                bin_id=line.bin_id,
                quantity=change,
                unit_cost=cost,
                source_type="Adjustment",
                grn_no=adjustment.adjustment_no,
                grn_date=adjustment.adjustment_date,
                movement="ADJUST_IN",
                source=source,
                stock_adjustment_id=adjustment.id,
                remarks=f"Found in count {count_no}",
            )
            row.stock_lot_id, row.unit_cost = lot.id, lot.unit_cost
        else:
            taken = ledger.take(
                item=item,
                location_id=location.id,
                bin_id=line.bin_id,
                quantity=-change,
                movement="ADJUST_OUT",
                source=source,
                location_label=location.name,
                unbinned_only=line.bin_id is None,
            )
            value = sum((t.quantity * t.lot.unit_cost for t in taken), ZERO)
            row.unit_cost = (value / -change).quantize(_COST)

    # ------------------------------------------------------------------ queries

    def _select(self) -> Select[Any]:
        created, closed, posted = (aliased(AppUser) for _ in range(3))
        created_e, closed_e, posted_e = (aliased(Employee) for _ in range(3))
        totals = (
            select(
                StockCountLine.stock_count_id,
                func.count(StockCountLine.id).label("line_count"),
                func.count(StockCountLine.counted_qty).label("counted_count"),
            )
            .group_by(StockCountLine.stock_count_id)
            .subquery()
        )
        return (
            select(
                StockCount.id,
                StockCount.count_no,
                StockCount.location_id,
                Location.code.label("location_code"),
                Location.name.label("location_name"),
                StockCount.count_date,
                StockCount.count_type,
                StockCount.scope,
                StockCount.storage_rack_id,
                StorageRack.code.label("storage_rack_code"),
                StockCount.is_blind,
                StockCount.status,
                StockCount.remarks,
                _user_name(created, created_e).label("created_by_name"),
                StockCount.created_at,
                case((closed.id.is_not(None), _user_name(closed, closed_e))).label("closed_by_name"),
                StockCount.closed_at,
                case((posted.id.is_not(None), _user_name(posted, posted_e))).label("posted_by_name"),
                StockCount.posted_at,
                StockAdjustment.id.label("adjustment_id"),
                StockAdjustment.adjustment_no,
                func.coalesce(totals.c.line_count, 0).label("line_count"),
                func.coalesce(totals.c.counted_count, 0).label("counted_count"),
            )
            .join(Location, Location.id == StockCount.location_id)
            .outerjoin(StorageRack, StorageRack.id == StockCount.storage_rack_id)
            .outerjoin(created, created.id == StockCount.created_by_user_id)
            .outerjoin(created_e, created_e.id == created.employee_id)
            .outerjoin(closed, closed.id == StockCount.closed_by_user_id)
            .outerjoin(closed_e, closed_e.id == closed.employee_id)
            .outerjoin(posted, posted.id == StockCount.posted_by_user_id)
            .outerjoin(posted_e, posted_e.id == posted.employee_id)
            .outerjoin(StockAdjustment, StockAdjustment.stock_count_id == StockCount.id)
            .outerjoin(totals, totals.c.stock_count_id == StockCount.id)
        )

    def _lines(self, count: StockCount, line_id: int | None = None) -> list[StockCountLineOut]:
        counter, counter_e = aliased(AppUser), aliased(Employee)
        statement = (
            select(
                StockCountLine.id,
                StockCountLine.item_id,
                Item.item_code,
                Item.description.label("item_description"),
                Uom.code.label("uom_code"),
                StockCountLine.bin_id,
                Bin.code.label("bin_code"),
                StockCountLine.system_qty,
                StockCountLine.counted_qty,
                StockCountLine.is_expected,
                case((counter.id.is_not(None), _user_name(counter, counter_e))).label("counted_by_name"),
                StockCountLine.counted_at,
                StockCountLine.remarks,
            )
            .join(Item, Item.id == StockCountLine.item_id)
            .join(Uom, Uom.id == Item.uom_id)
            .outerjoin(Bin, Bin.id == StockCountLine.bin_id)
            .outerjoin(counter, counter.id == StockCountLine.counted_by_user_id)
            .outerjoin(counter_e, counter_e.id == counter.employee_id)
            .where(StockCountLine.stock_count_id == count.id)
            .order_by(Bin.code, Item.item_code, StockCountLine.id)
        )
        if line_id is not None:
            statement = statement.where(StockCountLine.id == line_id)
        rows = self._db.execute(statement).mappings().all()
        costs = (
            self._costs(count.location_id, {row["item_id"] for row in rows}) if self._actor.can(*COST_VIEWERS) else {}
        )
        moved = self._moved_since_count(count) if count.status in ("Open", "Counted") else set()
        lines = []
        for row in rows:
            counted = row["counted_qty"]
            variance = counted - row["system_qty"] if counted is not None else None
            cost = costs.get(row["item_id"])
            lines.append(
                StockCountLineOut(
                    **row,
                    variance=variance,
                    unit_cost=cost.quantize(_COST) if cost is not None else None,
                    variance_value=(variance * cost).quantize(_VALUE) if variance is not None and cost else None,
                    moved_since_count=row["id"] in moved,
                )
            )
        return lines

    def _costs(self, location_id: int, item_ids: set[int]) -> dict[int, Decimal]:
        """Average cost of each item's batches at the location; the item's own cost when it has none there."""
        rows = self._db.execute(
            select(
                LotBalance.item_id,
                func.sum(LotBalance.qty_on_hand * StockLot.unit_cost),
                func.sum(LotBalance.qty_on_hand),
            )
            .join(StockLot, StockLot.id == LotBalance.stock_lot_id)
            .where(LotBalance.location_id == location_id, LotBalance.qty_on_hand > 0)
            .group_by(LotBalance.item_id)
        ).all()
        costs = {item_id: Decimal(value) / Decimal(qty) for item_id, value, qty in rows if qty}
        missing = [item_id for item_id in item_ids if item_id not in costs]
        for start in range(0, len(missing), 1000):
            for item_id, cost in self._db.execute(
                select(Item.id, func.coalesce(Item.standard_cost, Item.last_purchase_cost)).where(
                    Item.id.in_(missing[start : start + 1000])
                )
            ).all():
                if cost is not None:
                    costs[item_id] = Decimal(cost)
        return costs

    def _moved_since_count(self, count: StockCount) -> set[int]:
        """Counted lines whose item moved in or out of that bin after it was counted."""
        statement = select(StockCountLine.id).where(
            StockCountLine.stock_count_id == count.id,
            StockCountLine.counted_at.is_not(None),
            select(StockMove.id)
            .where(
                StockMove.item_id == StockCountLine.item_id,
                StockMove.location_id == count.location_id,
                or_(
                    StockMove.bin_id == StockCountLine.bin_id,
                    and_(StockMove.bin_id.is_(None), StockCountLine.bin_id.is_(None)),
                ),
                StockMove.move_at > StockCountLine.counted_at,
            )
            .exists(),
        )
        return set(self._db.scalars(statement))

    # ------------------------------------------------------------------ helpers

    def _scope_bins(self, count: StockCount) -> list[int]:
        if count.scope != "Bins":
            return []
        return list(self._db.scalars(select(StockCountBin.bin_id).where(StockCountBin.stock_count_id == count.id)))

    def _in_scope(self, count: StockCount, bin_id: int | None) -> bool:
        """Whether a bin (None = stock kept without a bin, only in a full count) is part of the count."""
        if count.scope == "Location":
            return True
        if bin_id is None:
            return False
        if count.scope == "Rack":
            place = self._db.get(Bin, bin_id)
            return place is not None and place.storage_rack_id == count.storage_rack_id
        return bin_id in self._scope_bins(count)

    @staticmethod
    def _balance_in_scope(count: StockCount, bin_ids: list[int]) -> ColumnElement[bool]:
        """A condition on StockBalance.bin_id: the stock the count covers."""
        if count.scope == "Location":
            return true()
        if count.scope == "Rack":
            return StockBalance.bin_id.in_(select(Bin.id).where(Bin.storage_rack_id == count.storage_rack_id))
        return StockBalance.bin_id.in_(bin_ids)

    def _record(self, line: StockCountLine, counted: Decimal) -> None:
        """A counted quantity, with the system quantity read now."""
        count = self._db.get(StockCount, line.stock_count_id)
        assert count is not None
        line.system_qty = self._system_qty(line.item_id, count.location_id, line.bin_id)
        line.counted_qty = counted
        line.counted_by_user_id = self._actor.id
        line.counted_at = now()
        line.updated_at, line.updated_by_user_id = line.counted_at, self._actor.id

    def _system_qty(self, item_id: int, location_id: int, bin_id: int | None) -> Decimal:
        return Decimal(
            self._db.scalar(
                select(func.coalesce(func.sum(StockBalance.qty_on_hand), 0)).where(
                    StockBalance.item_id == item_id,
                    StockBalance.location_id == location_id,
                    _same_bin(StockBalance.bin_id, bin_id),
                )
            )
            or 0
        )

    def _hide(self, out: StockCountOut) -> StockCountOut:
        """Totals of the differences; nothing of the system quantity while a blind count is open."""
        blind = out.is_blind and out.status == "Open"
        out.lines = [self._hide_line_out(line, blind) for line in out.lines]
        if not blind and out.lines:
            shorts = [ln for ln in out.lines if ln.variance is not None and ln.variance < 0]
            excess = [ln for ln in out.lines if ln.variance is not None and ln.variance > 0]
            out.short_qty = -sum((ln.variance or ZERO for ln in shorts), ZERO)
            out.excess_qty = sum((ln.variance or ZERO for ln in excess), ZERO)
            if self._actor.can(*COST_VIEWERS):
                out.short_value = -sum((ln.variance_value or ZERO for ln in shorts), ZERO)
                out.excess_value = sum((ln.variance_value or ZERO for ln in excess), ZERO)
        return out

    def _hide_line(self, count: StockCount, line: StockCountLineOut) -> StockCountLineOut:
        return self._hide_line_out(line, count.is_blind and count.status == "Open")

    @staticmethod
    def _hide_line_out(line: StockCountLineOut, blind: bool) -> StockCountLineOut:
        if blind:
            line.system_qty = line.variance = line.variance_value = None
        return line

    def _count(self, count_id: int) -> StockCount:
        count = self._db.get(StockCount, count_id)
        if count is None:
            raise NotFound("Stock count not found.")
        location = self._db.get(Location, count.location_id)
        if location is None or not self._actor.can_use_branch(location.branch_id):
            raise NotFound("Stock count not found.")
        return count

    @staticmethod
    def _expect(count: StockCount, statuses: tuple[str, ...], action: str) -> None:
        if count.status not in statuses:
            raise Conflict(f"Count {count.count_no} is {count.status.lower()}, so it can't be {action}.")

    def _touch(self, count: StockCount) -> None:
        count.updated_at, count.updated_by_user_id = now(), self._actor.id

    def _commit(self) -> None:
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise Conflict("The count changed while this was being saved. Reload and try again.") from error
