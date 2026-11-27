"""Warehouse storage: racks with levels x positions (/inv/storage-racks) and stock by rack and bin
(/inv/reports/bin-stock). Bins themselves keep their existing endpoints (/inv/locations/{id}/racks, /inv/racks/{id})."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.modules.inv.common import ANY_INVENTORY, LOCATION_MANAGE
from trishul_api.modules.inv.storage_schemas import (
    BinStockQuery,
    BinStockRow,
    StorageRackCreate,
    StorageRackOut,
    StorageRackQuery,
    StorageRackUpdate,
)
from trishul_api.modules.inv.storage_service import StorageService

router = APIRouter(prefix="/inv", tags=["storage"])

CAN_READ = Depends(require_permission(*ANY_INVENTORY))
CAN_MANAGE = Depends(require_permission(LOCATION_MANAGE))
StorageRackId = Annotated[int, Path(alias="storageRackId", gt=0)]


def _service(db: DbSession, actor: CurrentUserDep) -> StorageService:
    return StorageService(db, actor)


Storage = Annotated[StorageService, Depends(_service)]


@router.get("/storage-racks", summary="Racks of your locations, with bins in use and blocked", dependencies=[CAN_READ])
def list_storage_racks(query: Annotated[StorageRackQuery, Query()], storage: Storage) -> list[StorageRackOut]:
    return storage.racks(query)


@router.get("/storage-racks/{storageRackId}", summary="One rack", dependencies=[CAN_READ], responses=NOT_FOUND_RESPONSE)
def get_storage_rack(storage_rack_id: StorageRackId, storage: Storage) -> StorageRackOut:
    return storage.get(storage_rack_id)


@router.post(
    "/locations/{locationId}/storage-racks",
    summary="Add a rack: its levels x positions of bins are created with their codes",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def create_storage_rack(
    location_id: Annotated[int, Path(alias="locationId", gt=0)], data: StorageRackCreate, storage: Storage
) -> StorageRackOut:
    return storage.create(location_id, data)


@router.patch(
    "/storage-racks/{storageRackId}",
    summary="Change, resize, block or deactivate a rack",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_storage_rack(
    storage_rack_id: StorageRackId,
    data: StorageRackUpdate,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
    storage: Storage,
) -> StorageRackOut:
    return storage.update(storage_rack_id, row_version, data)


@router.get(
    "/reports/bin-stock",
    summary="Stock by location, rack, bin and item (or kept without a bin), with value and oldest GRN date",
    dependencies=[CAN_READ],
)
def list_bin_stock(query: Annotated[BinStockQuery, Query()], storage: Storage) -> Page[BinStockRow]:
    return storage.bin_stock(query)
