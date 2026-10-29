from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.db.models import UserDevice


class DeviceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_user(self, app_user_id: int, device_id: str) -> UserDevice | None:
        return self._session.scalars(
            select(UserDevice).where(UserDevice.app_user_id == app_user_id, UserDevice.device_id == device_id)
        ).first()

    def others_with_same_device(self, app_user_id: int, device_id: str) -> list[UserDevice]:
        """Active registrations of the same physical device under a different user (device handoff)."""
        return list(
            self._session.scalars(
                select(UserDevice).where(
                    UserDevice.device_id == device_id,
                    UserDevice.app_user_id != app_user_id,
                    UserDevice.is_active,
                )
            )
        )

    def add(self, device: UserDevice) -> None:
        self._session.add(device)
