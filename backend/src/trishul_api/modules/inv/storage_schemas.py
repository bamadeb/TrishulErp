"""Warehouse storage: racks with levels x positions of bins, and the rack-wise / bin-wise stock report."""

from datetime import date
from decimal import Decimal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion
from trishul_api.db.models import BinBinType, StorageRackType
from trishul_api.modules.inv.masters_schemas import StatusQuery


class StorageRackQuery(StatusQuery):
    location_id: int | None = Field(None, description="Racks of this location; all your locations when empty.")


class StorageRackOut(ApiModel):
    id: int
    location_id: int
    location_code: str
    code: str = Field(description="<location>-<rack>, e.g. BBSR-MAIN-R01; unique across every location.")
    short_code: str
    name: str | None
    rack_type: StorageRackType
    levels: int
    positions: int = Field(description="Bins per level.")
    max_weight_kg: Decimal | None
    is_blocked: bool
    blocked_reason: str | None
    bin_count: int = Field(description="Active bins.")
    occupied_bins: int = Field(description="Active bins holding stock.")
    blocked_bins: int
    qty_on_hand: Decimal = Field(description="Total quantity in the rack, all items.")
    is_active: bool
    row_version: RowVersion


_SHORT = Field(min_length=1, max_length=8, pattern=r"^[A-Za-z0-9]+$", description="e.g. R01; letters and digits.")
_WEIGHT = Field(None, gt=0, max_digits=10, decimal_places=2)


class StorageRackCreate(InputModel):
    short_code: str = _SHORT
    name: str | None = Field(None, max_length=80)
    rack_type: StorageRackType = "Rack"
    levels: int = Field(ge=1, le=20)
    positions: int = Field(ge=1, le=99, description="Bins per level.")
    bin_type: BinBinType = Field("Mixed", description="Type of the generated bins; each can be changed later.")
    max_weight_kg: Decimal | None = _WEIGHT


class StorageRackUpdate(InputModel):
    """Levels and positions may grow (new bins) or shrink (bins beyond them are deactivated, only if empty)."""

    name: str | None = Field(None, max_length=80)
    rack_type: StorageRackType | None = None
    levels: int | None = Field(None, ge=1, le=20)
    positions: int | None = Field(None, ge=1, le=99)
    max_weight_kg: Decimal | None = _WEIGHT
    is_blocked: bool | None = None
    blocked_reason: str | None = Field(None, max_length=200)
    is_active: bool | None = None


class BinStockQuery(PageQuery):
    location_id: int | None = None
    storage_rack_id: int | None = None
    bin_id: int | None = None
    item_id: int | None = None
    without_bin: bool = Field(False, description="Only stock kept at a location without a bin.")


class BinStockRow(ApiModel):
    location_id: int
    location_code: str
    branch_name: str
    storage_rack_id: int | None
    storage_rack_code: str | None
    bin_id: int | None
    bin_code: str | None
    bin_type: BinBinType | None
    bin_blocked: bool
    item_id: int
    item_code: str
    item_description: str
    uom_code: str
    qty_on_hand: Decimal
    value: Decimal | None = Field(description="At GRN batch cost; empty for users who may not see costs.")
    oldest_grn_date: date | None = Field(description="GRN date of the oldest batch in this place.")
