"""Pick list for delivering a sales order: where in the warehouse to take each outstanding line from.

The stock is allocated exactly as a delivery without a chosen bin takes it: oldest GRN batch first, from every bin
of the location except blocked ones (and stock kept without a bin). Rows come in bin order, so the picker walks the
racks once; lines that can't be covered in full are listed as short.
"""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.schemas import ApiModel
from trishul_api.db.models import Bin, Item, LotBalance, SalesOrderLine, StockLot, Uom
from trishul_api.modules.inv.common import ZERO, stock_location
from trishul_api.modules.inv.ledger import not_blocked


class PickRow(ApiModel):
    order_line_id: int
    line_no: int
    item_id: int
    item_code: str
    item_description: str
    uom_code: str
    bin_id: int | None
    bin_code: str | None = Field(description="Empty = stock kept at the location without a bin.")
    stock_lot_id: int
    lot_no: str
    grn_no: str
    grn_date: dt.date
    quantity: Decimal = Field(description="To pick from this bin and batch.")


class PickShort(ApiModel):
    order_line_id: int
    item_code: str
    item_description: str
    quantity: Decimal = Field(description="Still to deliver but not in stock here (outside blocked bins).")


class PickList(ApiModel):
    order_id: int
    order_no: str
    location_id: int
    location_code: str
    rows: list[PickRow]
    short: list[PickShort]


def build_pick_list(db: Session, actor: CurrentUser, order_id: int, order_no: str, location_id: int) -> PickList:
    location = stock_location(db, actor, location_id)
    lines = db.execute(
        select(SalesOrderLine, Item.item_code, Item.description, Uom.code)
        .join(Item, Item.id == SalesOrderLine.item_id)
        .join(Uom, Uom.id == Item.uom_id)
        .where(SalesOrderLine.sales_order_id == order_id, Item.item_type == "Stock")
        .order_by(SalesOrderLine.line_no, SalesOrderLine.id)
    ).all()
    wanted = [(line, code, text, uom) for line, code, text, uom in lines if line.quantity > line.qty_delivered]
    item_ids = {line.item_id for line, *_ in wanted}
    stock: dict[int, list[tuple[LotBalance, StockLot, str | None]]] = defaultdict(list)
    if item_ids:
        for balance, lot, bin_code in db.execute(
            select(LotBalance, StockLot, Bin.code)
            .join(StockLot, StockLot.id == LotBalance.stock_lot_id)
            .outerjoin(Bin, Bin.id == LotBalance.bin_id)
            .where(
                LotBalance.item_id.in_(item_ids),
                LotBalance.location_id == location.id,
                LotBalance.qty_on_hand > 0,
                not_blocked(),
            )
            .order_by(StockLot.grn_date, StockLot.id, LotBalance.id)
        ).all():
            stock[balance.item_id].append((balance, lot, bin_code))

    left = {balance.id: balance.qty_on_hand for rows in stock.values() for balance, _, _ in rows}
    picks: list[PickRow] = []
    short: list[PickShort] = []
    for line, code, text, uom in wanted:
        need = line.quantity - line.qty_delivered
        for balance, lot, bin_code in stock[line.item_id]:
            if need <= 0:
                break
            portion = min(need, left[balance.id])
            if portion <= 0:
                continue
            left[balance.id] -= portion
            need -= portion
            picks.append(
                PickRow(
                    order_line_id=line.id,
                    line_no=line.line_no,
                    item_id=line.item_id,
                    item_code=code,
                    item_description=line.description or text,
                    uom_code=uom,
                    bin_id=balance.bin_id,
                    bin_code=bin_code,
                    stock_lot_id=lot.id,
                    lot_no=lot.lot_no,
                    grn_no=lot.grn_no,
                    grn_date=lot.grn_date,
                    quantity=portion,
                )
            )
        if need > ZERO:
            short.append(
                PickShort(
                    order_line_id=line.id, item_code=code, item_description=line.description or text, quantity=need
                )
            )
    picks.sort(key=lambda r: (r.bin_code is None, r.bin_code or "", r.item_code, r.grn_date))
    return PickList(
        order_id=order_id,
        order_no=order_no,
        location_id=location.id,
        location_code=location.code,
        rows=picks,
        short=short,
    )
