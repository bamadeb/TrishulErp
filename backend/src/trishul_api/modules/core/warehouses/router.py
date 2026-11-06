"""Warehouse management routes (Administration > Warehouses), shown in Swagger under the warehouses tag."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.modules.core.warehouses.schemas import (
    BranchWarehouseUpdate,
    WarehouseBranch,
    WarehouseCreate,
    WarehouseMap,
    WarehouseOut,
    WarehouseUpdate,
)
from trishul_api.modules.core.warehouses.service import WarehouseService

router = APIRouter(prefix="/core", tags=["warehouses"])

CAN_VIEW = Depends(require_permission("core.warehouse.view", "core.warehouse.manage"))
CAN_MANAGE = Depends(require_permission("core.warehouse.manage"))

WarehouseId = Annotated[int, Path(alias="warehouseId", gt=0)]
BranchId = Annotated[int, Path(alias="branchId", gt=0)]
Match = Annotated[bytes, Depends(if_match_row_version)]


def get_warehouse_service(db: DbSession, actor: CurrentUserDep) -> WarehouseService:
    return WarehouseService(db, actor)


Warehouses = Annotated[WarehouseService, Depends(get_warehouse_service)]


@router.get("/warehouses", summary="Warehouses and the branches each one supplies", dependencies=[CAN_VIEW])
def get_warehouse_map(service: Warehouses) -> WarehouseMap:
    return service.overview()


@router.post("/warehouses", summary="Add a warehouse", status_code=201, dependencies=[CAN_MANAGE])
def create_warehouse(data: WarehouseCreate, service: Warehouses, response: Response) -> WarehouseOut:
    created = service.create(data)
    response.headers["Location"] = f"warehouses/{created.id}"
    return created


@router.patch(
    "/warehouses/{warehouseId}",
    summary="Rename, recode, activate or deactivate a warehouse",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_warehouse(
    warehouse_id: WarehouseId, data: WarehouseUpdate, service: Warehouses, row_version: Match
) -> WarehouseOut:
    return service.update(warehouse_id, row_version, data)


@router.put(
    "/branches/{branchId}/warehouse",
    summary="Set the warehouse that supplies a branch (or none)",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_branch_warehouse(
    branch_id: BranchId, data: BranchWarehouseUpdate, service: Warehouses, row_version: Match
) -> WarehouseBranch:
    return service.assign_branch(branch_id, row_version, data)
