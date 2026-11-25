"""Internal FastAPI routes for biometric device management and gated synchronization."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.errors import NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.config import Settings, get_settings
from trishul_api.modules.hr.biometric.config import load_biometric_settings
from trishul_api.modules.hr.biometric.schemas import (
    BiometricDashboardOut,
    BiometricDeviceCreate,
    BiometricDeviceOut,
    BiometricDeviceUpdate,
    BiometricMappingCreate,
    BiometricMappingOut,
    BiometricMappingUpdate,
    BiometricPunchOut,
    BiometricPunchQuery,
    BiometricSyncLogOut,
    BiometricSyncLogQuery,
    BiometricSyncRequest,
)
from trishul_api.modules.hr.biometric.service import BiometricService
from trishul_api.secrets import SecretProvider

router = APIRouter(prefix="/hr/biometric", tags=["biometric"])

CAN_VIEW = Depends(require_permission("hr.biometric.view", "hr.biometric.manage"))
CAN_MANAGE = Depends(require_permission("hr.biometric.manage"))
CAN_SYNC = Depends(require_permission("hr.biometric.sync", "hr.biometric.manage"))


def get_biometric_service(request: Request, db: DbSession) -> BiometricService:
    secrets: SecretProvider | None = getattr(request.app.state, "secret_provider", None)
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        settings = get_settings()
    return BiometricService(
        db,
        settings=settings,
        secret_provider=secrets,
        biometric_settings=load_biometric_settings(settings),
    )


Biometric = Annotated[BiometricService, Depends(get_biometric_service)]
DeviceId = Annotated[int, Path(alias="deviceId", gt=0)]
MappingId = Annotated[int, Path(alias="mappingId", gt=0)]


@router.get("/dashboard", summary="Biometric dashboard summary", dependencies=[CAN_MANAGE])
def dashboard(biometric: Biometric) -> BiometricDashboardOut:
    return biometric.dashboard()


@router.get("/devices", summary="List biometric devices", dependencies=[CAN_MANAGE])
def list_devices(biometric: Biometric) -> list[BiometricDeviceOut]:
    return biometric.list_devices()


@router.post(
    "/devices",
    summary="Register a biometric device",
    status_code=201,
    dependencies=[CAN_MANAGE],
)
def create_device(
    data: BiometricDeviceCreate, actor: CurrentUserDep, biometric: Biometric
) -> BiometricDeviceOut:
    return biometric.create_device(actor, data)


@router.get(
    "/devices/{deviceId}",
    summary="Get one biometric device",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def get_device(device_id: DeviceId, biometric: Biometric) -> BiometricDeviceOut:
    return biometric.get_device(device_id)


@router.patch(
    "/devices/{deviceId}",
    summary="Update a biometric device",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def update_device(
    device_id: DeviceId, data: BiometricDeviceUpdate, actor: CurrentUserDep, biometric: Biometric
) -> BiometricDeviceOut:
    return biometric.update_device(actor, device_id, data)


@router.get("/mappings", summary="List biometric employee mappings", dependencies=[CAN_MANAGE])
def list_mappings(
    biometric: Biometric,
    employee_id: Annotated[int | None, Query(alias="employeeId", gt=0)] = None,
    device_id: Annotated[int | None, Query(alias="deviceId", gt=0)] = None,
) -> list[BiometricMappingOut]:
    return biometric.list_mappings(employee_id=employee_id, device_id=device_id)


@router.post(
    "/mappings",
    summary="Create a biometric employee mapping",
    status_code=201,
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def create_mapping(
    data: BiometricMappingCreate, actor: CurrentUserDep, biometric: Biometric
) -> BiometricMappingOut:
    return biometric.create_mapping(actor, data)


@router.patch(
    "/mappings/{mappingId}",
    summary="Update a biometric employee mapping",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def update_mapping(
    mapping_id: MappingId, data: BiometricMappingUpdate, actor: CurrentUserDep, biometric: Biometric
) -> BiometricMappingOut:
    return biometric.update_mapping(actor, mapping_id, data)


@router.delete(
    "/mappings/{mappingId}",
    summary="Deactivate (unmap) a biometric employee mapping",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def deactivate_mapping(
    mapping_id: MappingId, actor: CurrentUserDep, biometric: Biometric
) -> BiometricMappingOut:
    return biometric.deactivate_mapping(actor, mapping_id)


@router.get("/punches", summary="View biometric punch logs", dependencies=[CAN_MANAGE])
def list_punches(query: Annotated[BiometricPunchQuery, Query()], biometric: Biometric) -> Page[BiometricPunchOut]:
    return biometric.list_punches(query)


@router.post(
    "/sync",
    summary="Run a manual biometric synchronization",
    dependencies=[CAN_SYNC],
)
def run_sync(
    data: BiometricSyncRequest, actor: CurrentUserDep, biometric: Biometric
) -> BiometricSyncLogOut:
    return biometric.run_manual_sync(actor, data)


@router.get("/sync-logs", summary="Biometric synchronization history", dependencies=[CAN_MANAGE])
def list_sync_logs(
    query: Annotated[BiometricSyncLogQuery, Query()], biometric: Biometric
) -> Page[BiometricSyncLogOut]:
    return biometric.list_sync_logs(query)
