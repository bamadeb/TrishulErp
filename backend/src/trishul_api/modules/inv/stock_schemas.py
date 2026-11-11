"""Stock on hand by GRN batch, inventory ageing and the movement ledger."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, PageQuery, UtcDateTime
from trishul_api.db.models import BranchBranchType, StockLotSourceType

AgeingGroup = Literal["item", "grn", "branch", "location", "rack"]

#: (label, lowest age in days, highest age in days or None for "and older")
AGEING_BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("0-30 days", 0, 30),
    ("31-60 days", 31, 60),
    ("61-90 days", 61, 90),
    ("91-180 days", 91, 180),
    ("Above 180 days", 181, None),
)


class StockFilter(ApiModel):
    item_id: int | None = None
    category_id: int | None = Field(None, description="Items of this category and its subcategories.")
    branch_id: int | None = None
    location_id: int | None = None
    bin_id: int | None = Field(None, description="Rack.")
    search: str | None = Field(None, max_length=100, description="Item code or description, GRN or batch no.")


class StockQuery(StockFilter, PageQuery):
    pass


class StockRow(ApiModel):
    """Quantity of one GRN batch at one place. Age counts from the original GRN date."""

    lot_balance_id: int
    stock_lot_id: int
    lot_no: str
    source_type: StockLotSourceType
    item_id: int
    item_code: str
    item_description: str
    uom_code: str
    grn_no: str
    grn_date: dt.date
    age_days: int
    bucket: str
    supplier_name: str | None
    branch_id: int
    branch_code: str
    branch_name: str
    branch_type: BranchBranchType
    location_id: int
    location_code: str
    location_name: str
    bin_id: int | None
    bin_code: str | None
    qty_on_hand: Decimal
    unit_cost: Decimal
    value: Decimal


class AgeingQuery(StockFilter):
    group_by: AgeingGroup = "item"


class AgeingCell(ApiModel):
    qty: Decimal
    value: Decimal


class AgeingRow(ApiModel):
    key: str = Field(description="Stable id of the group, to drill into the batches.")
    code: str
    name: str
    context: str | None = Field(description="Where / what: e.g. the branch of a location, the supplier of a GRN.")
    item_id: int | None
    branch_id: int | None
    location_id: int | None
    bin_id: int | None
    grn_no: str | None
    oldest_grn_date: dt.date
    oldest_age_days: int
    buckets: list[AgeingCell] = Field(description="One per bucket, in the order of AgeingReport.buckets.")
    qty: Decimal
    value: Decimal


class AgeingReport(ApiModel):
    """Inventory ageing from the GRN date of every batch on hand, valued at each batch's actual GRN cost."""

    group_by: AgeingGroup
    as_of: dt.date
    buckets: list[str]
    rows: list[AgeingRow]
    totals: list[AgeingCell]
    total_qty: Decimal
    total_value: Decimal


class MovementQuery(PageQuery):
    item_id: int | None = None
    stock_lot_id: int | None = None
    branch_id: int | None = None
    location_id: int | None = None
    from_date: dt.date | None = None
    to_date: dt.date | None = None


class MovementRow(ApiModel):
    id: int
    move_at: UtcDateTime
    movement_code: str
    movement_name: str
    item_id: int
    item_code: str
    item_description: str
    branch_name: str
    location_code: str
    location_name: str
    bin_code: str | None
    stock_lot_id: int | None
    lot_no: str | None
    grn_no: str | None
    grn_date: dt.date | None
    quantity: Decimal
    unit_cost: Decimal | None
    value: Decimal | None
    source_document_type: str
    source_document_id: int
    reference: str | None
    performed_by: str | None
