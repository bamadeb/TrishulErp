from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.modules.inv.common import ANY_INVENTORY, ITEM_MANAGE, LOCATION_MANAGE, STOCK_ADJUST
from trishul_api.modules.inv.masters_schemas import (
    BranchOption,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ConversionCreate,
    ConversionOut,
    ConversionQuery,
    ConversionUpdate,
    LocationCreate,
    LocationOut,
    LocationQuery,
    LocationUpdate,
    LookupOption,
    PriceListCreate,
    PriceListOut,
    PriceListUpdate,
    RackCreate,
    RackOut,
    RackUpdate,
    StatusQuery,
    UomCreate,
    UomOut,
    UomUpdate,
)
from trishul_api.modules.inv.masters_service import MastersService

router = APIRouter(prefix="/inv", tags=["inventory masters"])

CAN_READ = Depends(require_permission(*ANY_INVENTORY))
CAN_MANAGE_ITEMS = Depends(require_permission(ITEM_MANAGE))
CAN_MANAGE_LOCATIONS = Depends(require_permission(LOCATION_MANAGE))
CAN_ADJUST = Depends(require_permission(STOCK_ADJUST))

RowVersionDep = Annotated[bytes, Depends(if_match_row_version)]
UPDATE_RESPONSES = {**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES}


def _service(db: DbSession, actor: CurrentUserDep) -> MastersService:
    return MastersService(db, actor)


Masters = Annotated[MastersService, Depends(_service)]


# ---------------------------------------------------------------- units of measure


@router.get("/uoms", summary="Units of measure", dependencies=[CAN_READ])
def list_uoms(query: Annotated[StatusQuery, Query()], masters: Masters) -> list[UomOut]:
    return masters.uoms(query.status)


@router.post("/uoms", summary="Add a unit of measure", status_code=201, dependencies=[CAN_MANAGE_ITEMS])
def create_uom(data: UomCreate, masters: Masters) -> UomOut:
    return masters.create_uom(data)


@router.patch(
    "/uoms/{uomId}", summary="Change or deactivate a unit", dependencies=[CAN_MANAGE_ITEMS], responses=UPDATE_RESPONSES
)
def update_uom(
    uom_id: Annotated[int, Path(alias="uomId", gt=0)], data: UomUpdate, row_version: RowVersionDep, masters: Masters
) -> UomOut:
    return masters.update_uom(uom_id, row_version, data)


@router.get("/uom-conversions", summary="Unit conversions (general and per item)", dependencies=[CAN_READ])
def list_uom_conversions(query: Annotated[ConversionQuery, Query()], masters: Masters) -> list[ConversionOut]:
    return masters.conversions(query)


@router.post("/uom-conversions", summary="Add a unit conversion", status_code=201, dependencies=[CAN_MANAGE_ITEMS])
def create_uom_conversion(data: ConversionCreate, masters: Masters) -> ConversionOut:
    return masters.create_conversion(data)


@router.patch(
    "/uom-conversions/{conversionId}",
    summary="Change or deactivate a unit conversion",
    dependencies=[CAN_MANAGE_ITEMS],
    responses=UPDATE_RESPONSES,
)
def update_uom_conversion(
    conversion_id: Annotated[int, Path(alias="conversionId", gt=0)],
    data: ConversionUpdate,
    row_version: RowVersionDep,
    masters: Masters,
) -> ConversionOut:
    return masters.update_conversion(conversion_id, row_version, data)


# ---------------------------------------------------------------- item categories


@router.get("/item-categories", summary="Item categories and subcategories", dependencies=[CAN_READ])
def list_item_categories(query: Annotated[StatusQuery, Query()], masters: Masters) -> list[CategoryOut]:
    return masters.categories(query.status)


@router.post(
    "/item-categories", summary="Add a category or subcategory", status_code=201, dependencies=[CAN_MANAGE_ITEMS]
)
def create_item_category(data: CategoryCreate, masters: Masters) -> CategoryOut:
    return masters.create_category(data)


@router.patch(
    "/item-categories/{categoryId}",
    summary="Change, move or deactivate a category",
    dependencies=[CAN_MANAGE_ITEMS],
    responses=UPDATE_RESPONSES,
)
def update_item_category(
    category_id: Annotated[int, Path(alias="categoryId", gt=0)],
    data: CategoryUpdate,
    row_version: RowVersionDep,
    masters: Masters,
) -> CategoryOut:
    return masters.update_category(category_id, row_version, data)


# ---------------------------------------------------------------- branches, locations, racks


@router.get("/branches", summary="Branches and warehouses the user works in", dependencies=[CAN_READ])
def list_inventory_branches(masters: Masters) -> list[BranchOption]:
    return masters.branches()


@router.get("/locations", summary="Stock locations of the user's branches and warehouses", dependencies=[CAN_READ])
def list_locations(query: Annotated[LocationQuery, Query()], masters: Masters) -> list[LocationOut]:
    return masters.locations(query)


@router.post("/locations", summary="Add a stock location", status_code=201, dependencies=[CAN_MANAGE_LOCATIONS])
def create_location(data: LocationCreate, masters: Masters) -> LocationOut:
    return masters.create_location(data)


@router.patch(
    "/locations/{locationId}",
    summary="Change or deactivate a location",
    dependencies=[CAN_MANAGE_LOCATIONS],
    responses=UPDATE_RESPONSES,
)
def update_location(
    location_id: Annotated[int, Path(alias="locationId", gt=0)],
    data: LocationUpdate,
    row_version: RowVersionDep,
    masters: Masters,
) -> LocationOut:
    return masters.update_location(location_id, row_version, data)


@router.get(
    "/locations/{locationId}/racks",
    summary="Racks of a location",
    dependencies=[CAN_READ],
    responses=NOT_FOUND_RESPONSE,
)
def list_racks(
    location_id: Annotated[int, Path(alias="locationId", gt=0)],
    query: Annotated[StatusQuery, Query()],
    masters: Masters,
) -> list[RackOut]:
    return masters.racks(location_id, query.status)


@router.post(
    "/locations/{locationId}/racks",
    summary="Add a rack (its code must be unique across all locations)",
    dependencies=[CAN_MANAGE_LOCATIONS],
    responses=NOT_FOUND_RESPONSE,
)
def create_rack(
    location_id: Annotated[int, Path(alias="locationId", gt=0)], data: RackCreate, masters: Masters
) -> RackOut:
    return masters.create_rack(location_id, data)


@router.patch(
    "/racks/{rackId}",
    summary="Change or deactivate a rack",
    dependencies=[CAN_MANAGE_LOCATIONS],
    responses=UPDATE_RESPONSES,
)
def update_rack(
    rack_id: Annotated[int, Path(alias="rackId", gt=0)], data: RackUpdate, row_version: RowVersionDep, masters: Masters
) -> RackOut:
    return masters.update_rack(rack_id, row_version, data)


# ---------------------------------------------------------------- sales price lists


@router.get("/price-lists", summary="Sales price lists", dependencies=[CAN_READ])
def list_price_lists(query: Annotated[StatusQuery, Query()], masters: Masters) -> list[PriceListOut]:
    return masters.price_lists(query.status)


@router.post("/price-lists", summary="Add a sales price list", status_code=201, dependencies=[CAN_MANAGE_ITEMS])
def create_price_list(data: PriceListCreate, masters: Masters) -> PriceListOut:
    return masters.create_price_list(data)


@router.patch(
    "/price-lists/{priceListId}",
    summary="Change or deactivate a price list",
    dependencies=[CAN_MANAGE_ITEMS],
    responses=UPDATE_RESPONSES,
)
def update_price_list(
    price_list_id: Annotated[int, Path(alias="priceListId", gt=0)],
    data: PriceListUpdate,
    row_version: RowVersionDep,
    masters: Masters,
) -> PriceListOut:
    return masters.update_price_list(price_list_id, row_version, data)


# ---------------------------------------------------------------- lookups


@router.get("/adjustment-reasons", summary="Reasons for a stock adjustment", dependencies=[CAN_ADJUST])
def list_adjustment_reasons(masters: Masters) -> list[LookupOption]:
    return masters.adjustment_reasons()
