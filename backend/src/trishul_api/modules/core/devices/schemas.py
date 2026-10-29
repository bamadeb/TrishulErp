from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, RowVersion, UtcDateTime
from trishul_api.db.models import UserDevicePlatform

# Platform values come from the core.user_device CHECK constraint, through the generated model.
DevicePlatform = UserDevicePlatform


class RegisterDeviceInput(InputModel):
    """Sent by the Android app on sign-in. The user is the signed-in account, so it is not in the body."""

    device_id: str = Field(min_length=1, max_length=100)
    platform: DevicePlatform
    app_version: str | None = Field(None, max_length=20)
    push_token: str | None = Field(None, max_length=500)


class UserDeviceOut(ApiModel):
    id: int
    device_id: str
    platform: DevicePlatform
    app_version: str | None
    push_token: str | None
    last_seen_at: UtcDateTime | None
    is_active: bool
    row_version: RowVersion
