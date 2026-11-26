"""Bulk item price import and its history (/inv/price-imports), the price change limit (/inv/price-settings)
and an item's price change log (/inv/items/{itemId}/price-history)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Path, Query, Response, UploadFile

from trishul_api.auth import CurrentUserDep, DbSession, ScopeDep, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE, problem_response
from trishul_api.common.schemas import Page
from trishul_api.db.models.price_import import PriceField
from trishul_api.modules.inv.common import ANY_INVENTORY, ITEM_MANAGE, ITEM_VIEW
from trishul_api.modules.inv.item_list_import import MAX_BYTES, XLSX
from trishul_api.modules.inv.price_import import PriceImportService
from trishul_api.modules.inv.price_import_schemas import (
    ItemPriceChange,
    PriceImportBatch,
    PriceImportConfirm,
    PriceImportDecision,
    PriceImportLineOut,
    PriceImportLineQuery,
    PriceImportOptions,
    PriceImportQuery,
    PriceImportUploader,
    PriceSettings,
    PriceSettingsUpdate,
)
from trishul_api.modules.inv.prices import (
    PRICE_APPROVE,
    PRICE_IMPORT,
    PRICE_IMPORT_VIEW,
    max_change_pct,
    set_max_change_pct,
    settings_version,
)

router = APIRouter(prefix="/inv", tags=["price-imports"])

CAN_IMPORT = Depends(require_permission(PRICE_IMPORT))
CAN_VIEW = Depends(require_permission(PRICE_IMPORT, PRICE_IMPORT_VIEW, PRICE_APPROVE))
CAN_APPROVE = Depends(require_permission(PRICE_APPROVE))
CAN_SEE_PRICES = Depends(require_permission(ITEM_VIEW, ITEM_MANAGE, PRICE_IMPORT, PRICE_IMPORT_VIEW, PRICE_APPROVE))
ImportId = Annotated[int, Path(alias="importId", gt=0)]
ItemId = Annotated[int, Path(alias="itemId", gt=0)]
_XLSX_RESPONSE: dict[int | str, dict[str, Any]] = {200: {"content": {XLSX: {}}}}
_FILE_RESPONSE: dict[int | str, dict[str, Any]] = {
    **NOT_FOUND_RESPONSE,
    200: {"content": {"application/octet-stream": {}}},
}
_CONFLICT = {**NOT_FOUND_RESPONSE, 409: problem_response("The batch is not in the state this needs.")}


def _service(db: DbSession, actor: CurrentUserDep) -> PriceImportService:
    return PriceImportService(db, actor)


Imports = Annotated[PriceImportService, Depends(_service)]


def _download(file_name: str, content_type: str, content: bytes) -> Response:
    quoted = file_name.replace('"', "'")
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{quoted}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/price-imports/template",
    summary="The sample price workbook (.xlsx)",
    dependencies=[CAN_IMPORT],
    response_class=Response,
    responses=_XLSX_RESPONSE,
)
def get_price_import_template(imports: Imports) -> Response:
    return _download("item-price-template.xlsx", XLSX, imports.template())


@router.get(
    "/price-imports/options",
    summary="Price lists to import selling prices into, and the change limit",
    dependencies=[CAN_IMPORT],
)
def get_price_import_options(imports: Imports, scope: ScopeDep) -> PriceImportOptions:
    return imports.options(scope)


@router.get("/price-imports/uploaders", summary="Users who uploaded price files", dependencies=[CAN_VIEW])
def list_price_import_uploaders(imports: Imports) -> list[PriceImportUploader]:
    return imports.uploaders()


@router.get("/price-imports", summary="History of price imports, filtered and paged", dependencies=[CAN_VIEW])
def list_price_imports(query: Annotated[PriceImportQuery, Query()], imports: Imports) -> Page[PriceImportBatch]:
    return imports.search(query)


@router.post(
    "/price-imports",
    summary="Upload a price file: it is stored and compared with the current prices (Pending); nothing changes yet",
    status_code=201,
    dependencies=[CAN_IMPORT],
    responses={400: problem_response("The file or the options cannot be used.")},
)
def upload_price_import(
    imports: Imports,
    scope: ScopeDep,
    file: Annotated[UploadFile, File(description="The price file (.xlsx, .xls or .csv)")],
    reason: Annotated[str, Form(max_length=300, description="Why the prices change; kept in the price history.")],
    price_list_id: Annotated[int | None, Form(alias="priceListId")] = None,
    sap_price_field: Annotated[PriceField | None, Form(alias="sapPriceField")] = None,
) -> PriceImportBatch:
    raw = file.file.read(MAX_BYTES + 1)
    return imports.upload(
        file.filename or "prices.xlsx",
        raw,
        price_list_id=price_list_id,
        sap_price_field=sap_price_field,
        reason=reason,
        scope=scope,
    )


@router.get(
    "/price-imports/{importId}", summary="One price import", dependencies=[CAN_VIEW], responses=NOT_FOUND_RESPONSE
)
def get_price_import(import_id: ImportId, imports: Imports) -> PriceImportBatch:
    return imports.get(import_id)


@router.post(
    "/price-imports/{importId}/confirm",
    summary="Apply the checked price changes (or send them for approval when over the limit)",
    dependencies=[CAN_IMPORT],
    responses=_CONFLICT,
)
def confirm_price_import(import_id: ImportId, data: PriceImportConfirm, imports: Imports) -> PriceImportBatch:
    return imports.confirm(import_id, data.import_again)


@router.post(
    "/price-imports/{importId}/approve",
    summary="Approve a price import waiting for approval, and apply it",
    dependencies=[CAN_APPROVE],
    responses=_CONFLICT,
)
def approve_price_import(import_id: ImportId, data: PriceImportDecision, imports: Imports) -> PriceImportBatch:
    return imports.approve(import_id, data.note)


@router.post(
    "/price-imports/{importId}/reject",
    summary="Reject a price import waiting for approval; no price changes",
    dependencies=[CAN_APPROVE],
    responses=_CONFLICT,
)
def reject_price_import(import_id: ImportId, data: PriceImportDecision, imports: Imports) -> PriceImportBatch:
    return imports.reject(import_id, data.note)


@router.get(
    "/price-imports/{importId}/lines",
    summary="The rows of a price import: current and new prices, and what was (or will be) done",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def list_price_import_lines(
    import_id: ImportId, query: Annotated[PriceImportLineQuery, Query()], imports: Imports
) -> Page[PriceImportLineOut]:
    return imports.lines(import_id, query)


@router.get(
    "/price-imports/{importId}/file",
    summary="Download the uploaded price file",
    dependencies=[CAN_VIEW],
    response_class=Response,
    responses=_FILE_RESPONSE,
)
def get_price_import_file(import_id: ImportId, imports: Imports) -> Response:
    return _download(*imports.original_file(import_id))


@router.get(
    "/price-imports/{importId}/error-report",
    summary="Download the rows with errors, duplicates or that failed (.xlsx)",
    dependencies=[CAN_VIEW],
    response_class=Response,
    responses={**NOT_FOUND_RESPONSE, **_XLSX_RESPONSE},
)
def get_price_import_error_report(import_id: ImportId, imports: Imports) -> Response:
    file_name, content = imports.error_report(import_id)
    return _download(file_name, XLSX, content)


@router.get(
    "/price-settings",
    summary="The price change limit (percent) above which a price import needs approval",
    dependencies=[Depends(require_permission(*ANY_INVENTORY, PRICE_IMPORT, PRICE_IMPORT_VIEW, PRICE_APPROVE))],
)
def get_price_settings(db: DbSession) -> PriceSettings:
    return PriceSettings(max_change_pct=max_change_pct(db), row_version=settings_version(db))


@router.put(
    "/price-settings",
    summary="Change the price change limit",
    dependencies=[CAN_APPROVE],
    responses=CONCURRENCY_RESPONSES,
)
def update_price_settings(
    data: PriceSettingsUpdate,
    actor: CurrentUserDep,
    db: DbSession,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> PriceSettings:
    value = set_max_change_pct(db, data.max_change_pct, actor.id, row_version)
    return PriceSettings(max_change_pct=value, row_version=settings_version(db))


@router.get(
    "/items/{itemId}/price-history",
    summary="Every price change of an item: selling, purchase (standard cost) and MRP, who and when",
    dependencies=[CAN_SEE_PRICES],
    responses=NOT_FOUND_RESPONSE,
)
def list_item_price_history(
    item_id: ItemId,
    imports: Imports,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=200)] = 20,
) -> Page[ItemPriceChange]:
    return imports.item_history(item_id, page, page_size)
