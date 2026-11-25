from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, Query, Response, UploadFile

from trishul_api.auth import CurrentUserDep, DbSession, ScopeDep, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE, ApiError, problem_response
from trishul_api.common.schemas import Page
from trishul_api.modules.inv.common import ANY_INVENTORY, ITEM_MANAGE, ITEM_VIEW
from trishul_api.modules.inv.item_import import ItemImportService
from trishul_api.modules.inv.item_import_schemas import ItemImportPreview, ItemImportResult, PriceField
from trishul_api.modules.inv.item_schemas import (
    ItemCreate,
    ItemDetail,
    ItemFormOptions,
    ItemListItem,
    ItemPrices,
    ItemQuery,
    ItemUpdate,
    PurchasePriceCreate,
    PurchasePriceUpdate,
    SalesPriceCreate,
    SalesPriceUpdate,
)
from trishul_api.modules.inv.item_service import ItemService

router = APIRouter(prefix="/inv", tags=["items"])

# Any inventory user can search items (to pick one on a GRN, transfer or adjustment).
CAN_SEARCH = Depends(require_permission(*ANY_INVENTORY))
CAN_VIEW = Depends(require_permission(ITEM_VIEW, ITEM_MANAGE))
CAN_MANAGE = Depends(require_permission(ITEM_MANAGE))

ItemId = Annotated[int, Path(alias="itemId", gt=0)]
PriceId = Annotated[int, Path(alias="priceId", gt=0)]
RowVersionDep = Annotated[bytes, Depends(if_match_row_version)]
UPDATE_RESPONSES = {**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES}


def _service(db: DbSession, actor: CurrentUserDep) -> ItemService:
    return ItemService(db, actor)


Items = Annotated[ItemService, Depends(_service)]


@router.get("/items", summary="Items with stock on hand, filtered and paged", dependencies=[CAN_SEARCH])
def list_items(query: Annotated[ItemQuery, Query()], scope: ScopeDep, items: Items) -> Page[ItemListItem]:
    return items.search(scope, query)


_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
UploadCategory = Annotated[int | None, Form(alias="categoryId")]
UploadUom = Annotated[int | None, Form(alias="uomId")]
UploadPriceField = Annotated[PriceField, Form(alias="priceField")]
_BAD_FILE = {400: problem_response("The file is not the item price file.")}


def _read_upload(file: UploadFile) -> bytes:
    content = file.file.read()
    if not content:
        raise ApiError("The uploaded file is empty.")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise ApiError("That file is too large (10 MB at most).")
    return content


# Declared before /items/{itemId} so "import" is not parsed as an item id.
@router.post(
    "/items/import/preview",
    summary="Dry run of an item price file: what would be created or changed, and what is wrong with it",
    dependencies=[CAN_MANAGE],
    responses=_BAD_FILE,
)
def preview_item_import(
    actor: CurrentUserDep,
    scope: ScopeDep,
    db: DbSession,
    file: Annotated[UploadFile, File(description="The item price .xlsx")],
    category_id: UploadCategory = None,
    uom_id: UploadUom = None,
    price_field: UploadPriceField = "mrp",
) -> ItemImportPreview:
    return ItemImportService(db, actor).preview(
        _read_upload(file), file.filename or "upload.xlsx", scope, category_id, uom_id, price_field
    )


@router.post(
    "/items/import",
    summary="Import an item price file: create new items, update prices and missing HSN codes of existing ones",
    status_code=201,
    dependencies=[CAN_MANAGE],
    responses=_BAD_FILE,
)
def apply_item_import(
    actor: CurrentUserDep,
    scope: ScopeDep,
    db: DbSession,
    file: Annotated[UploadFile, File(description="The item price .xlsx")],
    category_id: UploadCategory = None,
    uom_id: UploadUom = None,
    price_field: UploadPriceField = "mrp",
) -> ItemImportResult:
    return ItemImportService(db, actor).apply(
        _read_upload(file), file.filename or "upload.xlsx", scope, category_id, uom_id, price_field
    )


# Declared before /items/{itemId} so "form-options" is not parsed as an item id.
@router.get("/items/form-options", summary="Dropdown values for the item form", dependencies=[CAN_MANAGE])
def get_item_form_options(items: Items) -> ItemFormOptions:
    return items.form_options()


@router.get("/items/{itemId}", summary="One item", dependencies=[CAN_SEARCH], responses=NOT_FOUND_RESPONSE)
def get_item(item_id: ItemId, items: Items) -> ItemDetail:
    return items.get(item_id)


@router.post("/items", summary="Add an item", status_code=201, dependencies=[CAN_MANAGE])
def create_item(data: ItemCreate, scope: ScopeDep, items: Items, response: Response) -> ItemDetail:
    created = items.create(data, scope)
    response.headers["Location"] = f"items/{created.id}"
    return created


@router.patch(
    "/items/{itemId}", summary="Change or deactivate an item", dependencies=[CAN_MANAGE], responses=UPDATE_RESPONSES
)
def update_item(item_id: ItemId, data: ItemUpdate, row_version: RowVersionDep, items: Items) -> ItemDetail:
    return items.update(item_id, row_version, data)


@router.get(
    "/items/{itemId}/prices",
    summary="Sales prices, purchase prices and costs of an item",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def get_item_prices(item_id: ItemId, items: Items) -> ItemPrices:
    return items.prices(item_id)


@router.post(
    "/items/{itemId}/sales-prices",
    summary="Add the item to a sales price list",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def create_sales_price(item_id: ItemId, data: SalesPriceCreate, items: Items) -> ItemPrices:
    return items.add_sales_price(item_id, data)


@router.patch(
    "/sales-prices/{priceId}",
    summary="Change or deactivate a sales price",
    dependencies=[CAN_MANAGE],
    responses=UPDATE_RESPONSES,
)
def update_sales_price(
    price_id: PriceId, data: SalesPriceUpdate, row_version: RowVersionDep, items: Items
) -> ItemPrices:
    return items.update_sales_price(price_id, row_version, data)


@router.post(
    "/items/{itemId}/purchase-prices",
    summary="Add a supplier's price for the item",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def create_purchase_price(item_id: ItemId, data: PurchasePriceCreate, items: Items) -> ItemPrices:
    return items.add_purchase_price(item_id, data)


@router.patch(
    "/purchase-prices/{priceId}",
    summary="Change or deactivate a supplier price",
    dependencies=[CAN_MANAGE],
    responses=UPDATE_RESPONSES,
)
def update_purchase_price(
    price_id: PriceId, data: PurchasePriceUpdate, row_version: RowVersionDep, items: Items
) -> ItemPrices:
    return items.update_purchase_price(price_id, row_version, data)
