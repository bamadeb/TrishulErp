from datetime import UTC, datetime

from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import NotFound
from trishul_api.db.models import UserDevice
from trishul_api.modules.core.devices.repository import DeviceRepository
from trishul_api.modules.core.devices.schemas import RegisterDeviceInput


def _utcnow() -> datetime:
    # DATETIME2 columns hold naive UTC (SYSUTCDATETIME); match that.
    return datetime.now(UTC).replace(tzinfo=None)


class DeviceService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = DeviceRepository(db)

    def register(self, user: CurrentUser, data: RegisterDeviceInput) -> tuple[UserDevice, bool]:
        """Upsert this user's device (unique on app_user_id + device_id). Returns (device, created)."""
        now = _utcnow()
        # Device handoff: the same phone signed in as someone else before. Stop its push and
        # deactivate it so notifications and sync never reach the previous user.
        for other in self._repo.others_with_same_device(user.id, data.device_id):
            other.is_active = False
            other.push_token = None
            other.updated_at = now
            other.updated_by_user_id = user.id

        device = self._repo.get_for_user(user.id, data.device_id)
        created = device is None
        if device is None:
            device = UserDevice(
                app_user_id=user.id,
                device_id=data.device_id,
                platform=data.platform,
                created_by_user_id=user.id,
            )
            self._repo.add(device)
        else:
            device.updated_at = now
            device.updated_by_user_id = user.id
        device.platform = data.platform
        device.app_version = data.app_version
        device.push_token = data.push_token
        device.last_seen_at = now
        device.is_active = True
        self._db.commit()
        return device, created

    def logout(self, user: CurrentUser, device_id: str) -> UserDevice:
        device = self._repo.get_for_user(user.id, device_id)
        if device is None or not device.is_active:
            raise NotFound("No active device registration found for this user and device.")
        now = _utcnow()
        device.push_token = None  # stop push notifications for the signed-out device
        device.last_seen_at = now
        device.updated_at = now
        device.updated_by_user_id = user.id
        self._db.commit()
        return device
