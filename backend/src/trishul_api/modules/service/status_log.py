"""Every status change on a service call is recorded in svc.call_status_log."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from trishul_api.db.models import CallStatusLog


def record_status_change(
    db: Session,
    call_id: int,
    from_status: str | None,
    to_status: str,
    user_id: int | None,
    remarks: str | None = None,
) -> None:
    """Add a log row for a change (from_status is None for a call's first status). The caller commits."""
    db.add(
        CallStatusLog(
            service_call_id=call_id,
            from_status=from_status,
            to_status=to_status,
            changed_at=datetime.now(UTC).replace(tzinfo=None),
            changed_by_user_id=user_id,
            remarks=remarks,
        )
    )
