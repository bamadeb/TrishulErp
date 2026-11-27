"""Item barcodes (optional), the scan / find lookup and label printing."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, RowVersion
from trishul_api.db.models import ItemBarcodeBarcodeType, ItemBarcodeSource, ScanResolvedType
from trishul_api.modules.inv.storage_schemas import BinStockRow


class ItemBarcodeOut(ApiModel):
    id: int
    item_id: int
    barcode: str
    barcode_type: ItemBarcodeBarcodeType
    source: ItemBarcodeSource
    pack_qty: Decimal = Field(description="Units one scan counts (1, or e.g. 100 for a box).")
    is_primary: bool = Field(description="Printed on the item's labels.")
    is_active: bool
    row_version: RowVersion


class ItemBarcodeCreate(InputModel):
    barcode: str = Field(min_length=1, max_length=60)
    barcode_type: ItemBarcodeBarcodeType = "Code128"
    source: Literal["Manufacturer", "Supplier"] = "Manufacturer"
    pack_qty: Decimal = Field(Decimal(1), gt=0, max_digits=18, decimal_places=3)
    is_primary: bool = False


class ItemBarcodeLink(ItemBarcodeCreate):
    """An unknown barcode scanned on the scan screen, linked to an item there."""

    item_id: int


class ItemBarcodeUpdate(InputModel):
    """The barcode itself never changes: deactivate it and add the right one."""

    barcode_type: ItemBarcodeBarcodeType | None = None
    pack_qty: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=3)
    is_primary: bool | None = None
    is_active: bool | None = None


ScanKind = Literal["Item", "Lot", "Bin", "Rack", "Location"]


class ScanMatch(ApiModel):
    kind: ScanKind
    id: int
    code: str
    name: str | None
    via: str = Field(description="How the code matched, e.g. Barcode, Item code, Part number, Bin code.")
    pack_qty: Decimal | None = Field(None, description="Units one scan of this barcode counts (items).")
    location_id: int | None = None


class BatchAge(ApiModel):
    """One receipt batch (GRN line, opening stock or adjustment) of an item, aged from its own GRN date."""

    stock_lot_id: int
    lot_no: str
    item_id: int
    item_code: str
    item_description: str
    uom_code: str
    source_type: str = Field(description="GRN, Opening, Adjustment ...")
    grn_no: str
    grn_date: dt.date
    supplier_name: str | None
    qty_received: Decimal
    qty_available: Decimal = Field(description="Still in stock, at the locations you may see.")
    places: list[str] = Field(description="Where it is: 'BBSR-MAIN · A1: 4'.")
    age_days: int
    age_years: int
    age_months: int = Field(description="Months after the whole years.")
    age_rest_days: int = Field(description="Days after the whole months.")
    age_text: str = Field(description="e.g. '1 year 2 months 5 days'.")


class ScanResult(ApiModel):
    code: str = Field(description="The value as scanned or typed.")
    resolved_type: ScanResolvedType
    matches: list[ScanMatch]
    stock: list[BinStockRow] = Field(description="Stock of the one match: by bin for an item, items for a place.")
    stock_total: int = Field(description="Stock rows in all (the list shows at most 200).")
    batches: list[BatchAge] = Field(
        default_factory=list,
        description="An item or batch scanned: its receipt batches still in stock, oldest GRN first, with their age.",
    )


LabelKind = Literal["Bin", "Rack", "Item", "Lot"]
LabelLayout = Literal["roll", "sheet"]


class LabelQuery(ApiModel):
    kind: LabelKind
    ids: list[int] = Field(
        default_factory=list, max_length=500, description="Bins, racks, items or GRN batches (stock lots) to label."
    )
    grn_id: int | None = Field(None, description="Batch labels: every batch received on this GRN.")
    one_per_unit: bool = Field(
        False, description="Batch labels: one label for each unit received (up to 500 a batch), times copies."
    )
    storage_rack_ids: list[int] = Field(
        default_factory=list, max_length=100, description="Bin labels: every active bin of these racks, rack by rack."
    )
    location_id: int | None = Field(None, description="Bin labels: the loose bins and yard spots of this location.")
    layout: LabelLayout = Field("roll", description="roll = one 50 x 25 mm label per page; sheet = A4, 3 x 8.")
    copies: int = Field(1, ge=1, le=20)
