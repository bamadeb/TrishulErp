"""Item barcodes, the scan / find lookup and barcode labels."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE, Forbidden
from trishul_api.modules.inv.barcode_schemas import (
    ItemBarcodeCreate,
    ItemBarcodeLink,
    ItemBarcodeOut,
    ItemBarcodeUpdate,
    LabelQuery,
    ScanResult,
)
from trishul_api.modules.inv.barcode_service import BARCODE_LINK, BARCODE_MANAGE, BarcodeService
from trishul_api.modules.inv.common import ANY_INVENTORY, GRN_MANAGE, LOCATION_MANAGE
from trishul_api.modules.inv.labels import labels_pdf

router = APIRouter(prefix="/inv", tags=["barcodes"])

CAN_READ = Depends(require_permission(*ANY_INVENTORY))
CAN_MANAGE = Depends(require_permission(BARCODE_MANAGE))
CAN_LINK = Depends(require_permission(BARCODE_MANAGE, BARCODE_LINK))
CAN_PRINT = Depends(require_permission(BARCODE_MANAGE, LOCATION_MANAGE, GRN_MANAGE))
ItemId = Annotated[int, Path(alias="itemId", gt=0)]
BarcodeId = Annotated[int, Path(alias="barcodeId", gt=0)]
_PDF: dict[int | str, dict[str, Any]] = {200: {"content": {"application/pdf": {}}}}


def _service(db: DbSession, actor: CurrentUserDep) -> BarcodeService:
    return BarcodeService(db, actor)


Barcodes = Annotated[BarcodeService, Depends(_service)]


@router.get(
    "/items/{itemId}/barcodes",
    summary="Barcodes of an item (optional; its item code always works too)",
    dependencies=[CAN_READ],
    responses=NOT_FOUND_RESPONSE,
)
def list_item_barcodes(item_id: ItemId, barcodes: Barcodes) -> list[ItemBarcodeOut]:
    return barcodes.list(item_id)


@router.post(
    "/items/{itemId}/barcodes",
    summary="Register a manufacturer or supplier barcode of an item",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def add_item_barcode(item_id: ItemId, data: ItemBarcodeCreate, barcodes: Barcodes) -> ItemBarcodeOut:
    return barcodes.add(item_id, data)


@router.post(
    "/items/{itemId}/generate-barcode",
    summary="Generate an internal barcode for an item that has none",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def generate_item_barcode(item_id: ItemId, barcodes: Barcodes) -> ItemBarcodeOut:
    return barcodes.generate(item_id)


@router.post(
    "/item-barcodes",
    summary="Link an unknown scanned barcode to an item (from the scan screen)",
    status_code=201,
    dependencies=[CAN_LINK],
    responses=NOT_FOUND_RESPONSE,
)
def create_item_barcode(data: ItemBarcodeLink, barcodes: Barcodes) -> ItemBarcodeOut:
    return barcodes.add(data.item_id, ItemBarcodeCreate(**data.model_dump(exclude={"item_id"})))


@router.patch(
    "/item-barcodes/{barcodeId}",
    summary="Change a barcode's type or pack quantity, make it primary, or deactivate it",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_item_barcode(
    barcode_id: BarcodeId,
    data: ItemBarcodeUpdate,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
    barcodes: Barcodes,
) -> ItemBarcodeOut:
    return barcodes.update(barcode_id, row_version, data)


@router.get(
    "/scan",
    summary="What a scanned or typed code is (bin, rack, location or item) and the stock behind it",
    dependencies=[CAN_READ],
)
def get_scan_result(
    barcodes: Barcodes,
    code: Annotated[str, Query(min_length=1, max_length=100)],
    screen: Annotated[str | None, Query(max_length=40)] = None,
) -> ScanResult:
    return barcodes.scan(code, screen)


@router.get(
    "/labels",
    summary="Labels as a PDF: bins (all of a rack, or the loose bins of a location), racks, items or GRN batches",
    dependencies=[CAN_PRINT],
    response_class=Response,
    responses=_PDF,
)
def get_labels(query: Annotated[LabelQuery, Query()], actor: CurrentUserDep, db: DbSession) -> Response:
    if query.kind == "Item" and not actor.can(BARCODE_MANAGE):
        raise Forbidden("Printing item labels needs the barcode permission.")
    if query.kind in ("Bin", "Rack") and not actor.can(BARCODE_MANAGE, LOCATION_MANAGE):
        raise Forbidden("Printing bin and rack labels needs the barcode or location permission.")
    file_name, content = labels_pdf(db, actor, query)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{file_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )
