"""Priced lines shared by quotations, orders and invoices: amounts per line and the document totals."""

from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import Field, model_validator
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.schemas import ApiModel, InputModel
from trishul_api.db.models import Item
from trishul_api.modules.sal.common import ZERO, money, sale_item, split_gst

QTY = Field(gt=0, max_digits=18, decimal_places=3)
PCT = Field(Decimal(0), ge=0, le=100, max_digits=5, decimal_places=2)
GST = Field(Decimal(18), ge=0, le=100, max_digits=5, decimal_places=2)
PRICE = Field(ge=0, max_digits=18, decimal_places=4, description="Per stock unit, before GST.")
MONEY = Field(Decimal(0), ge=0, max_digits=18, decimal_places=2)
_PRICE = Decimal("0.0001")


class PricedLineIn(InputModel):
    item_id: int | None = Field(None, description="Empty for a text-only line (a quotation can quote a service).")
    description: str | None = Field(None, max_length=300, description="Default: the item description.")
    quantity: Decimal = QTY
    unit_price: Decimal = PRICE
    discount_pct: Decimal = PCT
    gst_pct: Decimal = GST

    @model_validator(mode="after")
    def _item_or_text(self) -> "PricedLineIn":
        if self.item_id is None and not self.description:
            raise ValueError("a line needs an item or a description")
        return self


class ItemLineIn(PricedLineIn):
    item_id: int | None = Field(description="The item sold.")

    @model_validator(mode="after")
    def _item(self) -> "ItemLineIn":
        if self.item_id is None:
            raise ValueError("a line needs an item")
        return self


class PricedLineOut(ApiModel):
    id: int
    line_no: int
    item_id: int | None
    item_code: str | None
    description: str
    uom_code: str | None
    quantity: Decimal
    unit_price: Decimal
    discount_pct: Decimal
    gst_pct: Decimal
    net_price: Decimal = Field(description="Unit price after the discount, before GST.")
    taxable_value: Decimal
    tax_amount: Decimal
    line_total: Decimal


@dataclass
class Priced:
    item: Item | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount_pct: Decimal
    gst_pct: Decimal
    gross: Decimal
    discount: Decimal
    taxable: Decimal
    tax: Decimal

    @property
    def total(self) -> Decimal:
        return self.taxable + self.tax


@dataclass
class Totals:
    lines: list[Priced] = field(default_factory=list)
    gross: Decimal = ZERO
    discount: Decimal = ZERO
    taxable: Decimal = ZERO
    tax: Decimal = ZERO
    cgst: Decimal = ZERO
    sgst: Decimal = ZERO
    igst: Decimal = ZERO

    def total(self, other_charges: Decimal) -> Decimal:
        return self.taxable + self.tax + other_charges


def price_line(item: Item | None, description: str | None, quantity: Decimal, unit_price: Decimal,
               discount_pct: Decimal, gst_pct: Decimal) -> Priced:  # fmt: skip
    gross = money(quantity * unit_price)
    taxable = money(quantity * unit_price * (Decimal(100) - discount_pct) / Decimal(100))
    tax = money(taxable * gst_pct / Decimal(100))
    return Priced(
        item=item,
        description=description or (item.description if item else ""),
        quantity=quantity,
        unit_price=unit_price,
        discount_pct=discount_pct,
        gst_pct=gst_pct,
        gross=gross,
        discount=gross - taxable,
        taxable=taxable,
        tax=tax,
    )


def total_up(priced: list[Priced], *, inter_state: bool) -> Totals:
    totals = Totals(lines=priced)
    for line in priced:
        totals.gross += line.gross
        totals.discount += line.discount
        totals.taxable += line.taxable
        totals.tax += line.tax
    split = split_gst(totals.tax, inter_state=inter_state)
    totals.cgst, totals.sgst, totals.igst = split.cgst, split.sgst, split.igst
    totals.tax = money(totals.tax)
    return totals


def price_lines(db: Session, actor: CurrentUser, lines: list[PricedLineIn], principal_id: int, *,
                inter_state: bool) -> Totals:  # fmt: skip
    priced = []
    for index, line in enumerate(lines):
        item = sale_item(db, actor, line.item_id, principal_id, f"lines[{index}].itemId") if line.item_id else None
        priced.append(
            price_line(item, line.description, line.quantity, line.unit_price, line.discount_pct, line.gst_pct)
        )
    return total_up(priced, inter_state=inter_state)


def net_price(unit_price: Decimal, discount_pct: Decimal) -> Decimal:
    return (unit_price * (Decimal(100) - discount_pct) / Decimal(100)).quantize(_PRICE)
