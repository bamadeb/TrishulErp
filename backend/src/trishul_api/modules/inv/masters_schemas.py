"""Inventory masters: units of measure and conversions, item categories, locations and racks, suppliers,
and sales price lists."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, RowVersion
from trishul_api.db.models import (
    BranchBranchType,
    ItemCategoryItemNature,
    LocationLocationType,
    PriceListPriceListType,
)

StatusFilter = Literal["active", "inactive", "all"]

_CODE = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9_./-]*$")


class StatusQuery(ApiModel):
    status: StatusFilter = "active"


# ---------------------------------------------------------------- units of measure


class UomOut(ApiModel):
    id: int
    code: str
    name: str
    decimals: int = Field(description="Decimal places allowed in quantities (0 = whole numbers).")
    is_active: bool
    row_version: RowVersion


class UomCreate(InputModel):
    code: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9][A-Za-z0-9_./-]*$")
    name: str = Field(min_length=1, max_length=40)
    decimals: int = Field(0, ge=0, le=3)


class UomUpdate(InputModel):
    name: str | None = Field(None, min_length=1, max_length=40)
    decimals: int | None = Field(None, ge=0, le=3)
    is_active: bool | None = None


class ConversionQuery(StatusQuery):
    item_id: int | None = Field(None, description="Conversions for this item plus the general ones.")


class ConversionOut(ApiModel):
    """1 from-unit = factor to-units. itemId null: applies to every item."""

    id: int
    item_id: int | None
    item_code: str | None
    item_description: str | None
    from_uom_id: int
    from_uom_code: str
    to_uom_id: int
    to_uom_code: str
    factor: Decimal
    is_active: bool
    row_version: RowVersion


class ConversionCreate(InputModel):
    item_id: int | None = Field(None, description="Leave out for a conversion that applies to every item.")
    from_uom_id: int
    to_uom_id: int
    factor: Decimal = Field(gt=0, max_digits=18, decimal_places=6, description="1 from-unit = factor to-units.")


class ConversionUpdate(InputModel):
    factor: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)
    is_active: bool | None = None


# ---------------------------------------------------------------- item categories


class CategoryOut(ApiModel):
    id: int
    code: str
    name: str
    parent_category_id: int | None
    parent_name: str | None
    path: str = Field(description="Names from the top category down, e.g. 'Spare parts / Filters'.")
    level: int = Field(description="0 for a top category, 1 for a subcategory, ...")
    item_nature: ItemCategoryItemNature
    default_uom_id: int | None
    default_uom_code: str | None
    item_count: int
    is_active: bool
    row_version: RowVersion


class CategoryCreate(InputModel):
    code: str = _CODE
    name: str = Field(min_length=1, max_length=100)
    parent_category_id: int | None = Field(None, description="Set to make this a subcategory.")
    item_nature: ItemCategoryItemNature = "Spare part"
    default_uom_id: int | None = None


class CategoryUpdate(InputModel):
    """Only the fields sent are changed; send parentCategoryId null to make it a top category."""

    name: str | None = Field(None, min_length=1, max_length=100)
    parent_category_id: int | None = None
    item_nature: ItemCategoryItemNature | None = None
    default_uom_id: int | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------- locations and racks


class LocationQuery(StatusQuery):
    branch_id: int | None = None


class LocationOut(ApiModel):
    id: int
    branch_id: int
    branch_code: str
    branch_name: str
    branch_type: BranchBranchType
    code: str
    name: str
    location_type: LocationLocationType
    address: str | None
    is_stock_location: bool
    rack_count: int
    is_active: bool
    row_version: RowVersion


class LocationCreate(InputModel):
    branch_id: int = Field(description="The branch or warehouse the location belongs to.")
    code: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9][A-Za-z0-9_./-]*$")
    name: str = Field(min_length=1, max_length=120)
    location_type: LocationLocationType = "Main store"
    address: str | None = Field(None, max_length=500)
    is_stock_location: bool = True


class LocationUpdate(InputModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    location_type: LocationLocationType | None = None
    address: str | None = Field(None, max_length=500)
    is_stock_location: bool | None = None
    is_active: bool | None = None


class RackOut(ApiModel):
    id: int
    location_id: int
    location_code: str
    code: str = Field(description="Unique across every location.")
    rack: str | None
    shelf: str | None
    description: str | None
    is_active: bool
    row_version: RowVersion


class RackCreate(InputModel):
    code: str = _CODE
    rack: str | None = Field(None, max_length=10)
    shelf: str | None = Field(None, max_length=10)
    description: str | None = Field(None, max_length=100)


class RackUpdate(InputModel):
    code: str | None = Field(None, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9_./-]*$")
    rack: str | None = Field(None, max_length=10)
    shelf: str | None = Field(None, max_length=10)
    description: str | None = Field(None, max_length=100)
    is_active: bool | None = None


# ---------------------------------------------------------------- sales price lists


class PriceListOut(ApiModel):
    id: int
    code: str
    name: str
    price_list_type: PriceListPriceListType
    principal_id: int | None
    principal_code: str | None
    includes_tax: bool
    valid_from: dt.date | None
    valid_to: dt.date | None
    item_count: int
    is_active: bool
    row_version: RowVersion


class PriceListCreate(InputModel):
    code: str = _CODE
    name: str = Field(min_length=1, max_length=80)
    price_list_type: PriceListPriceListType = "Retail"
    principal_id: int | None = Field(None, description="Brand; leave out for a list of common items.")
    includes_tax: bool = False
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None


class PriceListUpdate(InputModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    price_list_type: PriceListPriceListType | None = None
    includes_tax: bool | None = None
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None
    is_active: bool | None = None


class BranchOption(ApiModel):
    id: int
    code: str
    name: str
    branch_type: BranchBranchType


class LookupOption(ApiModel):
    id: int
    code: str
    label: str
