"""Service settings kept in core.system_setting (global rows, company_id NULL)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.db.models import SystemSetting

MAX_PENDING_KEY = "SERVICE_MAX_PENDING_CALLS"
DEFAULT_MAX_PENDING_CALLS = 3


def _row(db: Session) -> SystemSetting | None:
    return db.scalars(
        select(SystemSetting)
        .where(
            SystemSetting.setting_key == MAX_PENDING_KEY, SystemSetting.company_id.is_(None), SystemSetting.is_active
        )
        .limit(1)
    ).first()


def max_pending_calls(db: Session) -> int:
    """Pending calls an engineer may have; more than this and no new call can be assigned."""
    row = _row(db)
    try:
        return max(0, int(row.setting_value)) if row is not None and row.setting_value else DEFAULT_MAX_PENDING_CALLS
    except ValueError:
        return DEFAULT_MAX_PENDING_CALLS


def set_max_pending_calls(db: Session, value: int, user_id: int) -> int:
    row = _row(db)
    if row is None:
        row = SystemSetting(
            company_id=None,
            setting_key=MAX_PENDING_KEY,
            data_type="Number",
            description="An engineer with more pending calls than this cannot be given another",
            created_by_user_id=user_id,
        )
        db.add(row)
    row.setting_value = str(value)
    row.updated_by_user_id = user_id
    db.commit()
    return value
