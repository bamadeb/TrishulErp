"""Stock documents: goods receipt (GRN), opening stock, transfers and adjustments. Each is posted to the
stock ledger when it is saved."""

import datetime as dt
from decimal import Decimal

from pydantic import Field, model_validator

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, UtcDateTime
from trishul_api.db.models import StockLotSourceType

_QTY = Field(gt=0, max_digits=18, decimal_places=3)
_COST = Field(ge=0, max_digits=18, decimal_places=4)


class DocumentQuery(PageQuery):
    branch_id: int | None = Field(None, description="Documents of this branch (from or to, for transfers).")
    location_id: int | None = None
    from_date: dt.date | None = None
    to_date: dt.date | None = None


class BatchMoved(ApiModel):
    """Quantity of one GRN batch a document line moved; the GRN date is the batch's original receipt."""

    line_id: int
    stock_lot_id: int
    lot_no: str
    grn_no: str
    grn_date: dt.date
    bin_code: str | None
    quantity: Decimal
    unit_cost: Decimal
    value: Decimal


# ---------------------------------------------------------------- opening stock


class OpeningLineIn(InputModel):
    item_id: int
    quantity: Decimal = _QTY
    unit_cost: Decimal = _COST
    bin_id: int | None = None
    grn_no: str = Field(min_length=1, max_length=30, description="The original GRN number (old system or paper).")
    grn_date: dt.date = Field(description="The original GRN date: the stock's age counts from it.")
    supplier_id: int | None = None
    remarks: str | None = Field(None, max_length=200)


class OpeningStockCreate(InputModel):
    location_id: int
    lines: list[OpeningLineIn] = Field(min_length=1, max_length=500)


# ---------------------------------------------------------------- transfers


class TransferLineIn(InputModel):
    item_id: int
    quantity: Decimal = _QTY
    from_bin_id: int | None = Field(None, description="Rack to take from; leave out for any rack (oldest first).")
    to_bin_id: int | None = Field(None, description="Rack to put into at the destination.")
    stock_lot_id: int | None = Field(None, description="Move only this GRN batch; default oldest GRN date first.")


class TransferCreate(InputModel):
    from_location_id: int
    to_location_id: int = Field(description="May be the same location, to move stock between racks.")
    transfer_date: dt.date | None = Field(None, description="Default today.")
    remarks: str | None = Field(None, max_length=300)
    lines: list[TransferLineIn] = Field(min_length=1, max_length=200)


class TransferListItem(ApiModel):
    id: int
    transfer_no: str
    transfer_date: dt.date
    from_location_id: int
    from_location_name: str
    from_branch_name: str
    to_location_id: int
    to_location_name: str
    to_branch_name: str
    line_count: int
    total_qty: Decimal
    status: str
    created_at: UtcDateTime


class TransferLineOut(ApiModel):
    id: int
    item_id: int
    item_code: str
    item_description: str
    uom_code: str
    quantity: Decimal
    from_bin_code: str | None
    to_bin_code: str | None
    value: Decimal | None


class TransferDetail(TransferListItem):
    remarks: str | None
    created_by: str | None
    total_value: Decimal
    lines: list[TransferLineOut]
    batches: list[BatchMoved] = Field(description="GRN batches moved; each keeps its original GRN date.")


# ---------------------------------------------------------------- adjustments


class AdjustmentLineIn(InputModel):
    item_id: int
    qty_change: Decimal = Field(max_digits=18, decimal_places=3, description="+ adds stock, - removes it.")
    bin_id: int | None = Field(None, description="Rack; for a decrease, leave out to take from any rack.")
    stock_lot_id: int | None = Field(
        None,
        description="Batch to change. A decrease without one takes the oldest; an increase without one is a new batch.",
    )
    unit_cost: Decimal | None = Field(
        None, ge=0, max_digits=18, decimal_places=4, description="For a new batch; default the item's standard cost."
    )
    remarks: str | None = Field(None, max_length=200)

    @model_validator(mode="after")
    def _not_zero(self) -> "AdjustmentLineIn":
        if self.qty_change == 0:
            raise ValueError("qtyChange must not be zero")
        return self


class AdjustmentCreate(InputModel):
    location_id: int
    reason_id: int = Field(description="From GET /inv/adjustment-reasons.")
    adjustment_date: dt.date | None = Field(None, description="Default today.")
    remarks: str | None = Field(None, max_length=300)
    lines: list[AdjustmentLineIn] = Field(min_length=1, max_length=200)


class AdjustmentListItem(ApiModel):
    id: int
    adjustment_no: str
    adjustment_date: dt.date
    location_id: int
    location_name: str
    branch_name: str
    reason: str
    line_count: int
    qty_in: Decimal
    qty_out: Decimal
    status: str
    posted_by: str | None
    posted_at: UtcDateTime | None


class AdjustmentLineOut(ApiModel):
    id: int
    item_id: int
    item_code: str
    item_description: str
    uom_code: str
    qty_change: Decimal
    bin_code: str | None
    unit_cost: Decimal | None
    remarks: str | None


class AdjustmentDetail(AdjustmentListItem):
    remarks: str | None
    value_change: Decimal
    lines: list[AdjustmentLineOut]
    batches: list[BatchMoved]


# ---------------------------------------------------------------- batches


class LotQuery(PageQuery):
    item_id: int | None = None
    source_type: StockLotSourceType | None = None
    branch_id: int | None = Field(None, description="Batches received at this branch.")
    in_stock: bool = Field(False, description="Only batches with stock left.")


class LotListItem(ApiModel):
    """A GRN batch: what was received, when (the age start) and how much of it is left."""

    id: int
    lot_no: str
    source_type: StockLotSourceType
    item_id: int
    item_code: str
    item_description: str
    uom_code: str
    grn_id: int | None
    grn_no: str
    grn_date: dt.date
    age_days: int
    supplier_name: str | None
    received_location_name: str
    received_branch_name: str
    unit_cost: Decimal
    qty_received: Decimal
    qty_on_hand: Decimal
    value_on_hand: Decimal
    remarks: str | None
    created_at: UtcDateTime
