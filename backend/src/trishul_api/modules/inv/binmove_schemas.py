"""Put-away and bin moves, and an item's storage type and home bins."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models import BinMoveType, ItemStorageType


class PutAwayRow(ApiModel):
    """Stock of one GRN batch waiting in a receiving bin, or kept at the location without a bin."""

    item_id: int
    item_code: str
    item_description: str
    uom_code: str
    storage_type: ItemStorageType | None
    stock_lot_id: int
    lot_no: str
    grn_no: str
    grn_date: dt.date
    from_bin_id: int | None
    from_bin_code: str | None = Field(description="The receiving bin; empty = kept without a bin.")
    qty_on_hand: Decimal
    suggested_bin_id: int | None
    suggested_bin_code: str | None
    suggestion: str | None = Field(description="Why: Home bin, Already stored here, Empty bin.")


class BinMoveLineIn(InputModel):
    item_id: int
    stock_lot_id: int | None = Field(None, description="Move this GRN batch; empty = oldest batches first.")
    from_bin_id: int | None = Field(None, description="Empty = stock kept at the location without a bin.")
    to_bin_id: int
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


class BinMoveCreate(InputModel):
    location_id: int
    move_type: BinMoveType = "Bin move"
    note: str | None = Field(None, max_length=200)
    lines: list[BinMoveLineIn] = Field(min_length=1, max_length=200)


class BinMoveLineOut(ApiModel):
    item_id: int
    item_code: str
    item_description: str
    lot_no: str | None
    from_bin_code: str | None
    to_bin_code: str
    quantity: Decimal


class BinMoveOut(ApiModel):
    id: int
    move_no: str | None
    location_id: int
    location_code: str
    move_type: BinMoveType
    note: str | None
    moved_by_name: str | None
    moved_at: UtcDateTime
    line_count: int
    lines: list[BinMoveLineOut] = Field(default_factory=list, description="Filled for one move, empty in lists.")


class BinMoveQuery(PageQuery):
    location_id: int | None = None
    item_id: int | None = None
    move_type: BinMoveType | None = None


class StorageRuleIn(InputModel):
    location_id: int
    bin_id: int
    min_qty: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=3)
    max_qty: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=3)


class StorageRuleOut(ApiModel):
    id: int
    location_id: int
    location_code: str
    bin_id: int
    bin_code: str
    min_qty: Decimal | None
    max_qty: Decimal | None
    qty_on_hand: Decimal = Field(description="Now in that bin.")


class ItemStorageOut(ApiModel):
    item_id: int
    storage_type: ItemStorageType | None
    rules: list[StorageRuleOut]
    row_version: RowVersion = Field(description="The item's; send it in If-Match to change the storage.")


class ItemStorageUpdate(InputModel):
    """Replaces the item's storage type and its home bins."""

    storage_type: ItemStorageType | None = None
    rules: list[StorageRuleIn] = Field(default_factory=list, max_length=50)


SuggestionKind = Literal["Home bin", "Already stored here", "Empty bin"]
