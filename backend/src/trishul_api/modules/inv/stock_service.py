"""Stock on hand, inventory ageing and stock movements, read from the GRN batches.

Age is today minus the batch's GRN date: a transfer moves the batch, it never re-dates it. The ageing
buckets are counted with date comparisons (grn_date >= today - 30, ...), so the same SQL works on
SQL Server and in the SQLite tests. Values use each batch's actual GRN cost.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, case, func, or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.paging import order_by_sort
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Bin,
    Branch,
    Item,
    ItemCategory,
    Location,
    LotBalance,
    MovementType,
    StockLot,
    StockMove,
    Supplier,
    Uom,
)
from trishul_api.modules.inv.common import ZERO, today, visible_item, visible_location
from trishul_api.modules.inv.stock_schemas import (
    AGEING_BUCKETS,
    AgeingCell,
    AgeingQuery,
    AgeingReport,
    AgeingRow,
    MovementQuery,
    MovementRow,
    StockFilter,
    StockQuery,
    StockRow,
)

_NO_RACK = "No rack"


def bucket_of(age_days: int) -> str:
    for label, low, high in AGEING_BUCKETS:
        if age_days >= low and (high is None or age_days <= high):
            return label
    return AGEING_BUCKETS[0][0]  # a GRN dated in the future counts as new stock


def _bucket_condition(as_of: date, low: int, high: int | None) -> ColumnElement[bool]:
    """Batches aged low..high days on as_of (inclusive), compared on the GRN date.
    The first bucket has no lower limit, so a GRN dated after as_of still lands in it."""
    conditions: list[ColumnElement[bool]] = []
    if low > 0:
        conditions.append(StockLot.grn_date <= as_of - timedelta(days=low))
    if high is not None:
        conditions.append(StockLot.grn_date >= as_of - timedelta(days=high))
    return and_(*conditions)


class StockService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ stock by batch

    def _base(self, scope: RequestScope, filters: StockFilter) -> Select[*tuple[Any, ...]]:
        """Batch balances with stock, joined to everything the screens show, within the user's limits."""
        statement = (
            select(LotBalance)
            .join(StockLot, StockLot.id == LotBalance.stock_lot_id)
            .join(Item, Item.id == LotBalance.item_id)
            .join(Uom, Uom.id == Item.uom_id)
            .join(Location, Location.id == LotBalance.location_id)
            .join(Branch, Branch.id == Location.branch_id)
            .outerjoin(Bin, Bin.id == LotBalance.bin_id)
            .outerjoin(Supplier, Supplier.id == StockLot.supplier_id)
            .where(LotBalance.qty_on_hand > 0, visible_location(self._actor), visible_item(self._actor, scope))
        )
        if filters.item_id is not None:
            statement = statement.where(LotBalance.item_id == filters.item_id)
        if filters.category_id is not None:
            statement = statement.where(Item.category_id.in_(self._category_and_children(filters.category_id)))
        if filters.branch_id is not None:
            statement = statement.where(Location.branch_id == filters.branch_id)
        if filters.location_id is not None:
            statement = statement.where(LotBalance.location_id == filters.location_id)
        if filters.bin_id is not None:
            statement = statement.where(LotBalance.bin_id == filters.bin_id)
        if filters.search:
            term = filters.search.strip()
            statement = statement.where(
                or_(
                    Item.item_code.contains(term, autoescape=True),
                    Item.description.contains(term, autoescape=True),
                    StockLot.grn_no.contains(term, autoescape=True),
                    StockLot.lot_no.contains(term, autoescape=True),
                )
            )
        return statement

    def stock(self, scope: RequestScope, query: StockQuery) -> Page[StockRow]:
        statement: Select[*tuple[Any, ...]] = self._base(scope, query).with_only_columns(
            LotBalance.id.label("lot_balance_id"),
            StockLot.id.label("stock_lot_id"),
            StockLot.lot_no,
            StockLot.source_type,
            Item.id.label("item_id"),
            Item.item_code,
            Item.description.label("item_description"),
            Uom.code.label("uom_code"),
            StockLot.grn_no,
            StockLot.grn_date,
            Supplier.name.label("supplier_name"),
            Branch.id.label("branch_id"),
            Branch.code.label("branch_code"),
            Branch.name.label("branch_name"),
            Branch.branch_type,
            Location.id.label("location_id"),
            Location.code.label("location_code"),
            Location.name.label("location_name"),
            Bin.id.label("bin_id"),
            Bin.code.label("bin_code"),
            LotBalance.qty_on_hand,
            StockLot.unit_cost,
            (LotBalance.qty_on_hand * StockLot.unit_cost).label("value"),
            maintain_column_froms=True,
        )
        statement = order_by_sort(
            statement,
            query.sort,
            {
                "grnDate": StockLot.grn_date,
                "itemCode": Item.item_code,
                "locationCode": Location.code,
                "binCode": Bin.code,
                "qtyOnHand": LotBalance.qty_on_hand,
                "value": LotBalance.qty_on_hand * StockLot.unit_cost,
            },
            default="grnDate",
            tiebreaker=LotBalance.id.asc(),
        )
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = self._db.execute(statement.offset((query.page - 1) * query.page_size).limit(query.page_size)).mappings()
        as_of = today()
        items = []
        for row in rows:
            age = (as_of - row["grn_date"]).days
            items.append(StockRow.model_validate({**row, "age_days": age, "bucket": bucket_of(age)}))
        return Page(items=items, total=total, page=query.page, page_size=query.page_size)

    # ------------------------------------------------------------------ ageing

    def ageing(self, scope: RequestScope, query: AgeingQuery) -> AgeingReport:
        as_of = today()
        qty = LotBalance.qty_on_hand
        value = LotBalance.qty_on_hand * StockLot.unit_cost
        sums: list[Any] = []
        for index, (_, low, high) in enumerate(AGEING_BUCKETS):
            condition = _bucket_condition(as_of, low, high)
            sums.append(func.sum(case((condition, qty), else_=0)).label(f"q{index}"))
            sums.append(func.sum(case((condition, value), else_=0)).label(f"v{index}"))

        keys = self._group_columns(query)
        statement = (
            self._base(scope, query)
            .with_only_columns(
                *keys,
                func.min(StockLot.grn_date).label("oldest"),
                func.sum(qty).label("qty"),
                func.sum(value).label("value"),
                *sums,
                maintain_column_froms=True,
            )
            .group_by(*keys)
        )
        rows = []
        for row in self._db.execute(statement).mappings():
            rows.append(self._ageing_row(query, row, as_of))
        rows.sort(key=lambda r: (-r.value, r.code))

        totals = [
            AgeingCell(
                qty=sum((r.buckets[i].qty for r in rows), ZERO), value=sum((r.buckets[i].value for r in rows), ZERO)
            )
            for i in range(len(AGEING_BUCKETS))
        ]
        return AgeingReport(
            group_by=query.group_by,
            as_of=as_of,
            buckets=[label for label, _, _ in AGEING_BUCKETS],
            rows=rows,
            totals=totals,
            total_qty=sum((r.qty for r in rows), ZERO),
            total_value=sum((r.value for r in rows), ZERO),
        )

    @staticmethod
    def _group_columns(query: AgeingQuery) -> list[Any]:
        match query.group_by:
            case "item":
                return [Item.id.label("item_id"), Item.item_code, Item.description, Uom.code.label("uom_code")]
            case "grn":
                return [StockLot.grn_no, StockLot.source_type, Supplier.name.label("supplier_name")]
            case "branch":
                return [
                    Branch.id.label("branch_id"),
                    Branch.code.label("branch_code"),
                    Branch.name.label("branch_name"),
                    Branch.branch_type,
                ]
            case "location":
                return [
                    Location.id.label("location_id"),
                    Location.code.label("location_code"),
                    Location.name.label("location_name"),
                    Branch.name.label("branch_name"),
                ]
            case "rack":
                return [
                    Location.id.label("location_id"),
                    Location.code.label("location_code"),
                    Branch.name.label("branch_name"),
                    Bin.id.label("bin_id"),
                    Bin.code.label("bin_code"),
                    Bin.description.label("bin_description"),
                ]

    @staticmethod
    def _ageing_row(query: AgeingQuery, row: Any, as_of: date) -> AgeingRow:
        buckets = [
            AgeingCell(qty=Decimal(row[f"q{i}"] or 0), value=Decimal(row[f"v{i}"] or 0))
            for i in range(len(AGEING_BUCKETS))
        ]
        fields: dict[str, Any] = {
            "item_id": None,
            "branch_id": None,
            "location_id": None,
            "bin_id": None,
            "grn_no": None,
            "context": None,
        }
        match query.group_by:
            case "item":
                fields |= {
                    "key": f"item-{row['item_id']}",
                    "code": row["item_code"],
                    "name": row["description"],
                    "context": row["uom_code"],
                    "item_id": row["item_id"],
                }
            case "grn":
                fields |= {
                    "key": f"grn-{row['grn_no']}",
                    "code": row["grn_no"],
                    "name": row["supplier_name"] or row["source_type"],
                    "context": row["source_type"],
                    "grn_no": row["grn_no"],
                }
            case "branch":
                fields |= {
                    "key": f"branch-{row['branch_id']}",
                    "code": row["branch_code"],
                    "name": row["branch_name"],
                    "context": row["branch_type"],
                    "branch_id": row["branch_id"],
                }
            case "location":
                fields |= {
                    "key": f"location-{row['location_id']}",
                    "code": row["location_code"],
                    "name": row["location_name"],
                    "context": row["branch_name"],
                    "location_id": row["location_id"],
                }
            case "rack":
                fields |= {
                    "key": f"rack-{row['location_id']}-{row['bin_id'] or 0}",
                    "code": row["bin_code"] or _NO_RACK,
                    "name": row["bin_description"] or (row["bin_code"] and f"Rack {row['bin_code']}") or _NO_RACK,
                    "context": f"{row['location_code']} · {row['branch_name']}",
                    "location_id": row["location_id"],
                    "bin_id": row["bin_id"],
                }
        oldest: date = row["oldest"]
        return AgeingRow(
            **fields,
            oldest_grn_date=oldest,
            oldest_age_days=(as_of - oldest).days,
            buckets=buckets,
            qty=Decimal(row["qty"] or 0),
            value=Decimal(row["value"] or 0),
        )

    # ------------------------------------------------------------------ movements

    def movements(self, query: MovementQuery) -> Page[MovementRow]:
        statement: Select[*tuple[Any, ...]] = (
            select(
                StockMove.id,
                StockMove.move_at,
                MovementType.code.label("movement_code"),
                MovementType.name.label("movement_name"),
                StockMove.item_id,
                Item.item_code,
                Item.description.label("item_description"),
                Branch.name.label("branch_name"),
                Location.code.label("location_code"),
                Location.name.label("location_name"),
                Bin.code.label("bin_code"),
                StockMove.stock_lot_id,
                StockLot.lot_no,
                StockLot.grn_no,
                StockLot.grn_date,
                StockMove.quantity,
                StockMove.unit_cost,
                StockMove.value,
                StockMove.source_document_type,
                StockMove.source_document_id,
                StockMove.reference,
                AppUser.username.label("performed_by"),
            )
            .join(MovementType, MovementType.id == StockMove.movement_type_id)
            .join(Item, Item.id == StockMove.item_id)
            .join(Location, Location.id == StockMove.location_id)
            .join(Branch, Branch.id == Location.branch_id)
            .outerjoin(Bin, Bin.id == StockMove.bin_id)
            .outerjoin(StockLot, StockLot.id == StockMove.stock_lot_id)
            .outerjoin(AppUser, AppUser.id == StockMove.performed_by_user_id)
            .where(visible_location(self._actor), visible_item(self._actor))
        )
        if query.item_id is not None:
            statement = statement.where(StockMove.item_id == query.item_id)
        if query.stock_lot_id is not None:
            statement = statement.where(StockMove.stock_lot_id == query.stock_lot_id)
        if query.branch_id is not None:
            statement = statement.where(Location.branch_id == query.branch_id)
        if query.location_id is not None:
            statement = statement.where(StockMove.location_id == query.location_id)
        if query.from_date is not None:
            statement = statement.where(StockMove.move_at >= query.from_date)
        if query.to_date is not None:
            statement = statement.where(StockMove.move_at < query.to_date + timedelta(days=1))
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    StockMove.reference.contains(term, autoescape=True),
                    Item.item_code.contains(term, autoescape=True),
                    StockLot.grn_no.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement, query.sort, {"moveAt": StockMove.move_at}, default="-moveAt", tiebreaker=StockMove.id.desc()
        )
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = self._db.execute(statement.offset((query.page - 1) * query.page_size).limit(query.page_size)).mappings()
        return Page(
            items=[MovementRow.model_validate(row) for row in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    # ------------------------------------------------------------------ helpers

    def _category_and_children(self, category_id: int) -> list[int]:
        parents = dict(self._db.execute(select(ItemCategory.id, ItemCategory.parent_category_id)).all())
        wanted = {category_id}
        grew = True
        while grew:
            grew = False
            for child, parent in parents.items():
                if parent in wanted and child not in wanted:
                    wanted.add(child)
                    grew = True
        return sorted(wanted)
