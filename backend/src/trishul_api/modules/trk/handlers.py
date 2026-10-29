"""Per-module side effects of starting and stopping a trip.

The trk engine owns the trip and GPS trail; each module keeps its own status machine. A handler maps
a module's business record to a trk.trackable_activity and advances that module when a trip starts or
stops. Add a module by registering a handler here — the engine and the endpoints do not change.
"""

from datetime import datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trishul_api.common.errors import ApiError, NotFound
from trishul_api.db.models import (
    CallStatusLog,
    CustomerSite,
    SalesActivity,
    ServiceCall,
    ServiceCallCurrentStatus,
    ServiceVisit,
    TrackableActivity,
)
from trishul_api.modules.trk.schemas import ModuleCode


class ActivityHandler(Protocol):
    module_code: ModuleCode

    def resolve(
        self, session: Session, employee_id: int, reference_id: int, user_id: int, lat: float, lon: float, now: datetime
    ) -> TrackableActivity:
        """Return (creating if needed) the trackable activity for this trip, and advance the module
        to 'trip started'. Raise NotFound if the activity is not the employee's to travel to."""
        ...

    def on_stop(
        self, session: Session, activity: TrackableActivity, user_id: int, lat: float, lon: float, now: datetime
    ) -> None:
        """Record arrival in the module when the trip stops."""
        ...


def _get_or_create_activity(
    session: Session,
    *,
    module_code: ModuleCode,
    source_table: str,
    source_id: int,
    employee_id: int,
    customer_id: int | None,
    title: str | None,
    activity_kind: str,
    target_lat: float | None = None,
    target_lon: float | None = None,
    user_id: int,
) -> TrackableActivity:
    activity = session.scalars(
        select(TrackableActivity).where(
            TrackableActivity.module_code == module_code,
            TrackableActivity.source_table == source_table,
            TrackableActivity.source_id == source_id,
        )
    ).first()
    if activity is None:
        activity = TrackableActivity(
            module_code=module_code,
            activity_kind=activity_kind,
            source_schema=module_code.lower() if module_code != "SVC" else "svc",
            source_table=source_table,
            source_id=source_id,
            employee_id=employee_id,
            customer_id=customer_id,
            title=title,
            target_latitude=target_lat,
            target_longitude=target_lon,
            created_by_user_id=user_id,
        )
        session.add(activity)
        session.flush()
    return activity


class ServiceActivityHandler:
    module_code: ModuleCode = "SVC"

    def resolve(
        self, session: Session, employee_id: int, reference_id: int, user_id: int, lat: float, lon: float, now: datetime
    ) -> TrackableActivity:
        call = session.get(ServiceCall, reference_id)
        if call is None or not call.is_active or call.assigned_engineer_id != employee_id:
            raise NotFound("Service call not found, or not assigned to you.")
        if call.current_status in ("Closed", "Cancelled", "Completed"):
            raise ApiError(f"This call is {call.current_status.lower()}; you cannot start a trip for it.")

        visit = session.scalars(
            select(ServiceVisit)
            .where(
                ServiceVisit.service_call_id == call.id,
                ServiceVisit.engineer_employee_id == employee_id,
                ServiceVisit.is_active,
                ServiceVisit.status.in_(("Planned", "On the way")),
            )
            .order_by(ServiceVisit.id.desc())
        ).first()
        if visit is None:
            next_no = (
                session.scalar(
                    select(func.max(ServiceVisit.visit_no)).where(ServiceVisit.service_call_id == call.id)
                )
                or 0
            ) + 1
            visit = ServiceVisit(
                service_call_id=call.id,
                visit_no=next_no,
                visit_purpose="Inspection",
                engineer_employee_id=employee_id,
                status="On the way",
                created_by_user_id=user_id,
            )
            session.add(visit)
            session.flush()
        else:
            visit.status = "On the way"
            _touch(visit, user_id, now)

        target_lat, target_lon = self._site_target(session, call)
        activity = _get_or_create_activity(
            session,
            module_code="SVC",
            source_table="service_visit",
            source_id=visit.id,
            employee_id=employee_id,
            customer_id=call.customer_id,
            title=call.call_no,
            activity_kind="Service visit",
            target_lat=target_lat,
            target_lon=target_lon,
            user_id=user_id,
        )
        _advance_call(session, call, "Trip started", user_id, lat, lon, now)
        return activity

    def on_stop(
        self, session: Session, activity: TrackableActivity, user_id: int, lat: float, lon: float, now: datetime
    ) -> None:
        visit = session.get(ServiceVisit, activity.source_id)
        if visit is not None:
            visit.status = "On site"
            if visit.service_started_at is None:
                visit.service_started_at = now
            _touch(visit, user_id, now)
            call = session.get(ServiceCall, visit.service_call_id)
            if call is not None and call.current_status == "Trip started":
                _advance_call(session, call, "Reached site", user_id, lat, lon, now)

    @staticmethod
    def _site_target(session: Session, call: ServiceCall) -> tuple[float | None, float | None]:
        if call.customer_site_id is None:
            return None, None
        site = session.get(CustomerSite, call.customer_site_id)
        if site is None:
            return None, None
        return (
            float(site.latitude) if site.latitude is not None else None,
            float(site.longitude) if site.longitude is not None else None,
        )


class PreSalesActivityHandler:
    module_code: ModuleCode = "PRE"

    def resolve(
        self, session: Session, employee_id: int, reference_id: int, user_id: int, lat: float, lon: float, now: datetime
    ) -> TrackableActivity:
        sa = session.get(SalesActivity, reference_id)
        if sa is None or not sa.is_active or sa.employee_id != employee_id:
            raise NotFound("Sales activity not found, or not assigned to you.")
        if sa.ended_at is not None:
            raise ApiError("This activity is already completed; you cannot start a trip for it.")
        if sa.started_at is None:
            sa.started_at = now
            _touch(sa, user_id, now)
        return _get_or_create_activity(
            session,
            module_code="PRE",
            source_table="sales_activity",
            source_id=sa.id,
            employee_id=employee_id,
            customer_id=sa.customer_id,
            title=f"{sa.activity_type}",
            activity_kind="Sales activity",
            user_id=user_id,
        )

    def on_stop(
        self, session: Session, activity: TrackableActivity, user_id: int, lat: float, lon: float, now: datetime
    ) -> None:
        sa = session.get(SalesActivity, activity.source_id)
        # Arrival only; the salesperson records the outcome and completes the activity separately.
        if sa is not None and sa.started_at is None:
            sa.started_at = now
            _touch(sa, user_id, now)


_HANDLERS: dict[ModuleCode, ActivityHandler] = {
    "SVC": ServiceActivityHandler(),
    "PRE": PreSalesActivityHandler(),
}


def handler_for(module_code: ModuleCode) -> ActivityHandler:
    handler = _HANDLERS.get(module_code)
    if handler is None:  # pragma: no cover - the schema Literal already constrains module
        raise ApiError(f"Unsupported module '{module_code}'.")
    return handler


def _advance_call(
    session: Session,
    call: ServiceCall,
    to_status: ServiceCallCurrentStatus,
    user_id: int,
    lat: float,
    lon: float,
    now: datetime,
) -> None:
    from_status = call.current_status
    call.current_status = to_status
    _touch(call, user_id, now)
    session.add(
        CallStatusLog(
            service_call_id=call.id,
            from_status=from_status,
            to_status=to_status,
            changed_at=now,
            changed_by_user_id=user_id,
            latitude=lat,
            longitude=lon,
        )
    )


def _touch(row: object, user_id: int, now: datetime) -> None:
    row.updated_at = now  # type: ignore[attr-defined]
    row.updated_by_user_id = user_id  # type: ignore[attr-defined]
