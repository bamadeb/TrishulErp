"""Physical stock counts: count sheets, counting by scan or typing, variance review and the posted adjustment."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, UtcDateTime
from trishul_api.db.models import StockCountScope, StockCountStatus

CountMode = Literal["set", "add"]


class StockCountCreate(InputModel):
    location_id: int
    scope: StockCountScope = Field(
        "Location", description="Location = every bin and the stock kept without a bin (a full count)."
    )
    storage_rack_id: int | None = Field(None, description="Scope Rack: the rack to count.")
    bin_ids: list[int] = Field(default_factory=list, max_length=500, description="Scope Bins: the bins to count.")
    is_blind: bool = Field(True, description="Hide the system quantity from counters until counting is finished.")
    count_date: dt.date | None = Field(None, description="Empty = today.")
    remarks: str | None = Field(None, max_length=300)


class StockCountEntry(InputModel):
    """A counted quantity of one item in one bin (or kept without a bin)."""

    item_id: int
    bin_id: int | None = Field(None, description="Empty = stock kept at the location without a bin.")
    quantity: Decimal = Field(ge=0, max_digits=18, decimal_places=3)
    mode: CountMode = Field("set", description="set = this is the count; add = add to what was counted (scanning).")
    remarks: str | None = Field(None, max_length=200)


class StockCountClose(InputModel):
    uncounted_as_zero: bool = Field(
        False, description="Lines nobody counted were counted as 0 (the stock is missing); else they are left out."
    )


class StockCountLineOut(ApiModel):
    id: int
    item_id: int
    item_code: str
    item_description: str
    uom_code: str
    bin_id: int | None
    bin_code: str | None
    system_qty: Decimal | None = Field(description="Hidden (empty) while a blind count is open.")
    counted_qty: Decimal | None = Field(description="Empty = not counted yet.")
    variance: Decimal | None = Field(description="Counted - system; empty until counted (or while blind).")
    unit_cost: Decimal | None = Field(description="Average cost of the item at the location; for the value.")
    variance_value: Decimal | None
    is_expected: bool = Field(description="False = found during the count, not in the system when it started.")
    counted_by_name: str | None
    counted_at: UtcDateTime | None
    moved_since_count: bool = Field(description="Stock of this item moved in or out of the bin after it was counted.")
    remarks: str | None


class StockCountOut(ApiModel):
    id: int
    count_no: str
    location_id: int
    location_code: str
    location_name: str
    count_date: dt.date
    count_type: str
    scope: StockCountScope
    storage_rack_id: int | None
    storage_rack_code: str | None
    bin_codes: list[str] = Field(default_factory=list, description="Scope Bins: the bins counted.")
    is_blind: bool
    status: StockCountStatus
    remarks: str | None
    created_by_name: str | None
    created_at: UtcDateTime
    closed_by_name: str | None
    closed_at: UtcDateTime | None
    posted_by_name: str | None
    posted_at: UtcDateTime | None
    adjustment_id: int | None
    adjustment_no: str | None
    line_count: int
    counted_count: int
    short_qty: Decimal | None = Field(None, description="Less found than the system says (hidden while blind).")
    excess_qty: Decimal | None = None
    short_value: Decimal | None = None
    excess_value: Decimal | None = None
    lines: list[StockCountLineOut] = Field(default_factory=list, description="Filled for one count, empty in lists.")


class StockCountQuery(PageQuery):
    location_id: int | None = None
    status: StockCountStatus | None = None
