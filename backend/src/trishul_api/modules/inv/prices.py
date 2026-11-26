"""Item prices shared by the price import and the item screens: the change history, the allowed change limit
and the item's selling price on a price list.

Prices of an item:
  * selling price   sal.price_list_item.unit_price on a price list (the row with the lowest minimum quantity);
  * purchase price  core.item.standard_cost;
  * MRP             core.item.mrp.
Every change is added to inv.item_price_history (never updated or deleted).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.common.concurrency import check_row_version
from trishul_api.db.models import Item, ItemPriceHistory, PriceListItem, SystemSetting
from trishul_api.db.models.price_import import PriceChangeSource
from trishul_api.modules.inv.common import now

PRICE_IMPORT = "inv.price.import"
PRICE_IMPORT_VIEW = "inv.price.import.view"
PRICE_APPROVE = "inv.price.approve"

MAX_CHANGE_KEY = "INV_PRICE_MAX_CHANGE_PCT"
DEFAULT_MAX_CHANGE_PCT = Decimal(20)

Pair = tuple[Decimal | None, Decimal | None]


def _same(old: Decimal | None, new: Decimal | None) -> bool:
    if old is None or new is None:
        return old is new
    return Decimal(old) == Decimal(new)


def record_price_change(
    db: Session,
    item: Item,
    *,
    user_id: int | None,
    source: PriceChangeSource,
    selling: Pair | None = None,
    price_list_id: int | None = None,
    min_qty: Decimal | None = None,
    purchase: Pair | None = None,
    mrp: Pair | None = None,
    import_id: int | None = None,
    reason: str | None = None,
) -> ItemPriceHistory | None:
    """Adds one history row for the prices that really changed; None when nothing did."""
    selling = selling if selling and not _same(*selling) else None
    purchase = purchase if purchase and not _same(*purchase) else None
    mrp = mrp if mrp and not _same(*mrp) else None
    if selling is None and purchase is None and mrp is None:
        return None
    row = ItemPriceHistory(
        item_id=item.id,
        item_code=item.item_code,
        price_list_id=price_list_id if selling else None,
        min_qty=min_qty if selling else None,
        old_selling=selling[0] if selling else None,
        new_selling=selling[1] if selling else None,
        old_purchase=purchase[0] if purchase else None,
        new_purchase=purchase[1] if purchase else None,
        old_mrp=mrp[0] if mrp else None,
        new_mrp=mrp[1] if mrp else None,
        source=source,
        import_id=import_id,
        reason=(reason or "")[:300] or None,
        changed_by_user_id=user_id,
        changed_at=now(),
    )
    db.add(row)
    return row


def base_selling_row(db: Session, price_list_id: int, item_id: int) -> PriceListItem | None:
    """The item's price on the list: the active row with the lowest minimum quantity, else an inactive row
    for quantity 1 (which an import reactivates), else None."""
    rows = db.scalars(
        select(PriceListItem)
        .where(PriceListItem.price_list_id == price_list_id, PriceListItem.item_id == item_id)
        .order_by(PriceListItem.min_qty, PriceListItem.id)
    ).all()
    active = [r for r in rows if r.is_active]
    if active:
        return active[0]
    return next((r for r in rows if Decimal(r.min_qty) == 1), None)


def _setting(db: Session) -> SystemSetting | None:
    return db.scalars(
        select(SystemSetting)
        .where(SystemSetting.setting_key == MAX_CHANGE_KEY, SystemSetting.company_id.is_(None), SystemSetting.is_active)
        .limit(1)
    ).first()


def max_change_pct(db: Session) -> Decimal:
    """A price changed by more than this percent (up or down) needs approval."""
    row = _setting(db)
    try:
        value = Decimal(row.setting_value) if row is not None and row.setting_value else DEFAULT_MAX_CHANGE_PCT
    except ArithmeticError:
        return DEFAULT_MAX_CHANGE_PCT
    return value if value >= 0 else DEFAULT_MAX_CHANGE_PCT


def settings_version(db: Session) -> bytes | None:
    """Row version of the limit setting (sent back in If-Match to change it); None until it is saved once."""
    row = _setting(db)
    return row.row_version if row is not None else None


def set_max_change_pct(db: Session, value: Decimal, user_id: int, expected: bytes) -> Decimal:
    row = _setting(db)
    if row is not None:
        check_row_version(row.row_version, expected)
    else:
        row = SystemSetting(
            company_id=None,
            setting_key=MAX_CHANGE_KEY,
            data_type="Number",
            description="A price import changing a price by more than this percent needs approval",
            created_by_user_id=user_id,
        )
        db.add(row)
    row.setting_value = f"{value.normalize():f}"
    row.updated_by_user_id = user_id
    row.updated_at = now()
    db.commit()
    return max_change_pct(db)
