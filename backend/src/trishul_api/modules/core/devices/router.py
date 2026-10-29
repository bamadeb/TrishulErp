from typing import Annotated

from fastapi import APIRouter, Depends, Path

from trishul_api.auth import SIGNED_IN_USERS, CurrentUserDep, DbSession
from trishul_api.common.errors import NOT_FOUND_RESPONSE
from trishul_api.modules.core.devices.schemas import RegisterDeviceInput, UserDeviceOut
from trishul_api.modules.core.devices.service import DeviceService

router = APIRouter(prefix="/core", tags=["core"])


def get_device_service(db: DbSession) -> DeviceService:
    return DeviceService(db)


DeviceServiceDep = Annotated[DeviceService, Depends(get_device_service)]


@router.post(
    "/user-devices",
    summary="Register or update the signed-in user's mobile device",
    status_code=201,
    openapi_extra=SIGNED_IN_USERS,  # every signed-in user registers their own device on login
)
def create_user_device(data: RegisterDeviceInput, user: CurrentUserDep, service: DeviceServiceDep) -> UserDeviceOut:
    device, _ = service.register(user, data)
    return UserDeviceOut.model_validate(device)


@router.post(
    "/user-devices/{deviceId}/logout",
    summary="Sign the device out: stop push notifications and stamp last seen",
    responses=NOT_FOUND_RESPONSE,
    openapi_extra=SIGNED_IN_USERS,
)
def logout_user_device(
    device_id: Annotated[str, Path(alias="deviceId", max_length=100)],
    user: CurrentUserDep,
    service: DeviceServiceDep,
) -> UserDeviceOut:
    return UserDeviceOut.model_validate(service.logout(user, device_id))
