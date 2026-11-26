"""Item list import (Excel / CSV into the item master) and its history: /inv/item-imports."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Path, Query, Response, UploadFile

from trishul_api.auth import CurrentUserDep, DbSession, ScopeDep, require_permission
from trishul_api.common.errors import NOT_FOUND_RESPONSE, problem_response
from trishul_api.common.schemas import Page
from trishul_api.db.models.item_import import ItemImportDuplicateMode
from trishul_api.modules.inv.item_list_import import (
    ITEM_IMPORT,
    ITEM_IMPORT_VIEW,
    MAX_BYTES,
    XLSX,
    ItemListImportService,
)
from trishul_api.modules.inv.item_list_import_schemas import (
    ItemImportBatch,
    ItemImportLineOut,
    ItemImportLineQuery,
    ItemImportQuery,
    ItemImportUploader,
)

router = APIRouter(prefix="/inv", tags=["item-imports"])

CAN_IMPORT = Depends(require_permission(ITEM_IMPORT))
CAN_VIEW = Depends(require_permission(ITEM_IMPORT, ITEM_IMPORT_VIEW))
ImportId = Annotated[int, Path(alias="importId", gt=0)]
_XLSX_RESPONSE: dict[int | str, dict[str, Any]] = {200: {"content": {XLSX: {}}}}
_FILE_RESPONSE: dict[int | str, dict[str, Any]] = {
    **NOT_FOUND_RESPONSE,
    200: {"content": {"application/octet-stream": {}}},
}


def _service(db: DbSession, actor: CurrentUserDep) -> ItemListImportService:
    return ItemListImportService(db, actor)


Imports = Annotated[ItemListImportService, Depends(_service)]


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
    "/item-imports/template",
    summary="The sample item list workbook (.xlsx) with the valid codes",
    dependencies=[CAN_IMPORT],
    response_class=Response,
    responses=_XLSX_RESPONSE,
)
def get_item_import_template(imports: Imports) -> Response:
    return _download("item-import-template.xlsx", XLSX, imports.template())


@router.get(
    "/item-imports/uploaders",
    summary="Users who have uploaded item lists (for the history filter)",
    dependencies=[CAN_VIEW],
)
def list_item_import_uploaders(imports: Imports) -> list[ItemImportUploader]:
    return imports.uploaders()


@router.get("/item-imports", summary="History of item list imports, filtered and paged", dependencies=[CAN_VIEW])
def list_item_imports(query: Annotated[ItemImportQuery, Query()], imports: Imports) -> Page[ItemImportBatch]:
    return imports.search(query)


@router.post(
    "/item-imports",
    summary="Upload an item list: it is stored and checked row by row (status Pending); nothing is imported yet",
    status_code=201,
    dependencies=[CAN_IMPORT],
    responses={400: problem_response("The file cannot be used (type, size or content).")},
)
def upload_item_import(
    imports: Imports,
    scope: ScopeDep,
    file: Annotated[UploadFile, File(description="The item list (.xlsx, .xls or .csv)")],
    duplicate_mode: Annotated[ItemImportDuplicateMode, Form(alias="duplicateMode")] = "Skip",
) -> ItemImportBatch:
    raw = file.file.read(MAX_BYTES + 1)
    return imports.upload(file.filename or "items.xlsx", raw, duplicate_mode, scope)


@router.get(
    "/item-imports/{importId}", summary="One item list import", dependencies=[CAN_VIEW], responses=NOT_FOUND_RESPONSE
)
def get_item_import(import_id: ImportId, imports: Imports) -> ItemImportBatch:
    return imports.get(import_id)


@router.post(
    "/item-imports/{importId}/confirm",
    summary="Import the valid rows of a checked (Pending) upload, in one transaction",
    dependencies=[CAN_IMPORT],
    responses={**NOT_FOUND_RESPONSE, 409: problem_response("The import was already confirmed.")},
)
def confirm_item_import(import_id: ImportId, imports: Imports) -> ItemImportBatch:
    return imports.confirm(import_id)


@router.get(
    "/item-imports/{importId}/lines",
    summary="The rows of an item list import with what was (or will be) done to each",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def list_item_import_lines(
    import_id: ImportId, query: Annotated[ItemImportLineQuery, Query()], imports: Imports
) -> Page[ItemImportLineOut]:
    return imports.lines(import_id, query)


@router.get(
    "/item-imports/{importId}/file",
    summary="Download the uploaded file",
    dependencies=[CAN_VIEW],
    response_class=Response,
    responses=_FILE_RESPONSE,
)
def get_item_import_file(import_id: ImportId, imports: Imports) -> Response:
    return _download(*imports.original_file(import_id))


@router.get(
    "/item-imports/{importId}/error-report",
    summary="Download the rows with errors or skipped as duplicates (.xlsx)",
    dependencies=[CAN_VIEW],
    response_class=Response,
    responses={**NOT_FOUND_RESPONSE, **_XLSX_RESPONSE},
)
def get_item_import_error_report(import_id: ImportId, imports: Imports) -> Response:
    file_name, content = imports.error_report(import_id)
    return _download(file_name, XLSX, content)
