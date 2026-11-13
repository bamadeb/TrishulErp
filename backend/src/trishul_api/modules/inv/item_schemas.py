import datetime as dt
from decimal import Decimal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models import ItemItemType, PriceListPriceListType
from trishul_api.modules.inv.masters_schemas import CategoryOut, StatusFilter, UomOut

_MONEY = Field(None, ge=0, max_digits=18, decimal_places=4)
_QTY = Field(None, ge=0, max_digits=18, decimal_places=3)


class ItemQuery(PageQuery):
    status: StatusFilter = "active"
    category_id: int | None = Field(None, description="Items of this category and its subcategories.")
    item_type: ItemItemType | None = None
    below_reorder: bool = Field(False, description="Only items whose stock is at or below the reorder level.")


class ItemListItem(ApiModel):
    id: int
    item_code: str
    description: str
    oem_part_number: str | None
    category_id: int
    category_name: str
    uom_id: int
    uom_code: str
    item_type: ItemItemType
    principal_id: int | None
    principal_code: str | None
    standard_cost: Decimal | None
    mrp: Decimal | None
    reorder_level: Decimal | None
    qty_on_hand: Decimal = Field(description="Across the stock locations of the user's branches.")
    stock_value: Decimal | None = Field(
        description="At each GRN batch's actual cost. Empty (as are the costs) for users who may not see costs."
    )
    is_active: bool


class ItemDetail(ItemListItem):
    long_description: str | None
    hsn_sac_id: int | None
    hsn_code: str | None
    is_serialized: bool
    is_batch_tracked: bool
    last_purchase_cost: Decimal | None
    reorder_qty: Decimal | None
    lead_time_days: int | None
    created_at: UtcDateTime
    row_version: RowVersion


class ItemCreate(InputModel):
    item_code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9_./ -]*$")
    description: str = Field(min_length=1, max_length=200)
    long_description: str | None = Field(None, max_length=1000)
    oem_part_number: str | None = Field(None, max_length=40)
    category_id: int
    uom_id: int | None = Field(None, description="Stock unit; defaults to the category's unit.")
    hsn_sac_id: int | None = None
    item_type: ItemItemType = "Stock"
    principal_id: int | None = Field(None, description="Brand; leave out for a common item (e.g. lubricants).")
    is_serialized: bool = False
    is_batch_tracked: bool = False
    standard_cost: Decimal | None = _MONEY
    mrp: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    reorder_level: Decimal | None = _QTY
    reorder_qty: Decimal | None = _QTY
    lead_time_days: int | None = Field(None, ge=0, le=999)


class ItemUpdate(InputModel):
    """Only the fields sent are changed. The stock unit can't change once the item has stock movements."""

    item_code: str | None = Field(None, min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9_./ -]*$")
    description: str | None = Field(None, min_length=1, max_length=200)
    long_description: str | None = Field(None, max_length=1000)
    oem_part_number: str | None = Field(None, max_length=40)
    category_id: int | None = None
    uom_id: int | None = None
    hsn_sac_id: int | None = None
    item_type: ItemItemType | None = None
    principal_id: int | None = None
    is_serialized: bool | None = None
    is_batch_tracked: bool | None = None
    standard_cost: Decimal | None = _MONEY
    mrp: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    reorder_level: Decimal | None = _QTY
    reorder_qty: Decimal | None = _QTY
    lead_time_days: int | None = Field(None, ge=0, le=999)
    is_active: bool | None = None


class PrincipalOption(ApiModel):
    id: int
    code: str
    name: str


class HsnOption(ApiModel):
    id: int
    code: str
    description: str | None


class ItemFormOptions(ApiModel):
    categories: list[CategoryOut]
    uoms: list[UomOut]
    principals: list[PrincipalOption]
    hsn_codes: list[HsnOption]


# ---------------------------------------------------------------- pricing


class SalesPriceOut(ApiModel):
    id: int
    price_list_id: int
    price_list_code: str
    price_list_name: str
    price_list_type: PriceListPriceListType
    includes_tax: bool
    valid_from: dt.date | None
    valid_to: dt.date | None
    min_qty: Decimal
    unit_price: Decimal
    is_active: bool
    row_version: RowVersion


class SalesPriceCreate(InputModel):
    price_list_id: int
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    min_qty: Decimal = Field(
        Decimal(1), gt=0, max_digits=18, decimal_places=3, description="Price applies from this qty."
    )


class SalesPriceUpdate(InputModel):
    unit_price: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=4)
    min_qty: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=3)
    is_active: bool | None = None


class PurchasePriceOut(ApiModel):
    id: int
    supplier_id: int
    supplier_code: str
    supplier_name: str
    supplier_part_no: str | None
    supplier_uom: str | None
    conversion_factor: Decimal
    price: Decimal
    valid_from: dt.date | None
    valid_to: dt.date | None
    lead_time_days: int | None
    is_active: bool
    row_version: RowVersion


class PurchasePriceCreate(InputModel):
    supplier_id: int
    price: Decimal = Field(ge=0, max_digits=18, decimal_places=4, description="Per supplier unit.")
    supplier_part_no: str | None = Field(None, max_length=40)
    supplier_uom: str | None = Field(None, max_length=10)
    conversion_factor: Decimal = Field(
        Decimal(1), gt=0, max_digits=12, decimal_places=4, description="Stock units in one supplier unit."
    )
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None
    lead_time_days: int | None = Field(None, ge=0, le=999)


class PurchasePriceUpdate(InputModel):
    price: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=4)
    supplier_part_no: str | None = Field(None, max_length=40)
    supplier_uom: str | None = Field(None, max_length=10)
    conversion_factor: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=4)
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None
    lead_time_days: int | None = Field(None, ge=0, le=999)
    is_active: bool | None = None


class ItemPrices(ApiModel):
    """Sales prices (per price list), purchase prices (per supplier) and the item's costs."""

    item_id: int
    standard_cost: Decimal | None = Field(description="Kept on the item for valuation and reporting.")
    last_purchase_cost: Decimal | None = Field(description="Stock-unit cost of the latest GRN.")
    mrp: Decimal | None
    average_cost: Decimal | None = Field(description="Value / quantity of the stock on hand (actual GRN costs).")
    sales_prices: list[SalesPriceOut]
    purchase_prices: list[PurchasePriceOut]
