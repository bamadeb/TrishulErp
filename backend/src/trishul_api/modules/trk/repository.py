from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import RequestScope
from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page, PageQuery
from trishul_api.db.models import (
    AppUser,
    Employee,
    ServiceVisit,
    TrackableActivity,
    TrkTrip,
    TrkTripDistanceAdjustment,
    TrkTripGpsDiagnostic,
    TrkTripGpsPoint,
    UserDevice,
)
from trishul_api.modules.trk.constants import IN_PROGRESS
from trishul_api.modules.trk.distance import GpsFix
from trishul_api.modules.trk.schemas import (
    CallTripHistoryItem,
    GpsDiagnosticItem,
    GpsQuality,
    RoutePoint,
    TripAdjustmentItem,
    TripListItem,
    TripListQuery,
)

# The distance used for reporting: the Team Lead's manual value wins, else the Maps value, else GPS.
POOR_ACCURACY_M = 50
MAX_ROUTE_POINTS = 1000
_EFFECTIVE_DISTANCE_KM = func.coalesce(
    TrkTrip.adjusted_distance_km, TrkTrip.map_distance_km, TrkTrip.gps_distance_km
)

_SORT_COLUMNS: SortColumns = {
    "startAt": TrkTrip.start_at,
    "status": TrkTrip.status,
}


class TripRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, obj: object) -> None:
        self._session.add(obj)

    def flush(self) -> None:
        self._session.flush()

    def get_trip(self, trip_id: int) -> TrkTrip | None:
        return self._session.get(TrkTrip, trip_id)

    def get_activity(self, activity_id: int) -> TrackableActivity | None:
        return self._session.get(TrackableActivity, activity_id)

    def trip_by_client_uuid(self, client_uuid: object) -> TrkTrip | None:
        return self._session.scalars(select(TrkTrip).where(TrkTrip.client_uuid == client_uuid)).first()

    def active_trip_for_employee(self, employee_id: int) -> TrkTrip | None:
        return self._session.scalars(
            select(TrkTrip).where(
                TrkTrip.employee_id == employee_id, TrkTrip.status == IN_PROGRESS, TrkTrip.is_active
            )
        ).first()

    def device_id_for(self, app_user_id: int, device_id: str) -> int | None:
        return self._session.scalar(
            select(UserDevice.id).where(UserDevice.app_user_id == app_user_id, UserDevice.device_id == device_id)
        )

    def existing_gps_times(self, trip_id: int, recorded_ats: list[datetime]) -> set[datetime]:
        if not recorded_ats:
            return set()
        return set(
            self._session.scalars(
                select(TrkTripGpsPoint.recorded_at).where(
                    TrkTripGpsPoint.trip_id == trip_id, TrkTripGpsPoint.recorded_at.in_(recorded_ats)
                )
            )
        )

    def existing_diagnostic_ids(self, trip_id: int, event_ids: list[UUID]) -> set[UUID]:
        if not event_ids:
            return set()
        return set(
            self._session.scalars(
                select(TrkTripGpsDiagnostic.event_id).where(
                    TrkTripGpsDiagnostic.trip_id == trip_id, TrkTripGpsDiagnostic.event_id.in_(event_ids)
                )
            )
        )

    def diagnostics_for_trip(self, trip_id: int, query: PageQuery) -> Page[GpsDiagnosticItem]:
        """A trip's diagnostic events in the order they happened."""
        statement = (
            select(*TrkTripGpsDiagnostic.__table__.c)
            .where(TrkTripGpsDiagnostic.trip_id == trip_id)
            .order_by(TrkTripGpsDiagnostic.recorded_at, TrkTripGpsDiagnostic.id)
        )
        return paginate(self._session, statement, query, GpsDiagnosticItem)

    def gps_point_stats(self, trip_id: int) -> tuple[int, datetime | None, datetime | None]:
        """Stored GPS points of a trip: count, first and last capture time."""
        count, first, last = self._session.execute(
            select(func.count(), func.min(TrkTripGpsPoint.recorded_at), func.max(TrkTripGpsPoint.recorded_at)).where(
                TrkTripGpsPoint.trip_id == trip_id
            )
        ).one()
        return count, first, last

    def diagnostic_stats(self, trip_id: int) -> tuple[int, datetime | None, datetime | None]:
        """Stored diagnostic events of a trip: count, first and last event time."""
        count, first, last = self._session.execute(
            select(
                func.count(), func.min(TrkTripGpsDiagnostic.recorded_at), func.max(TrkTripGpsDiagnostic.recorded_at)
            ).where(TrkTripGpsDiagnostic.trip_id == trip_id)
        ).one()
        return count, first, last

    def employee_branch_id(self, employee_id: int) -> int | None:
        return self._session.scalar(select(Employee.branch_id).where(Employee.id == employee_id))

    def adjustments_for_trip(self, trip_id: int) -> list[TripAdjustmentItem]:
        """The manual-adjustment audit trail of a trip, newest first."""
        adjuster = func.nullif(func.concat_ws(" ", Employee.first_name, Employee.last_name), "")
        rows = self._session.execute(
            select(
                TrkTripDistanceAdjustment.id,
                TrkTripDistanceAdjustment.trip_id,
                TrkTripDistanceAdjustment.previous_distance_km,
                TrkTripDistanceAdjustment.new_distance_km,
                TrkTripDistanceAdjustment.gps_distance_km_at_adjustment,
                TrkTripDistanceAdjustment.reason,
                TrkTripDistanceAdjustment.adjusted_by_user_id,
                func.coalesce(adjuster, AppUser.username).label("adjusted_by_name"),
                TrkTripDistanceAdjustment.adjusted_at,
            )
            .outerjoin(AppUser, AppUser.id == TrkTripDistanceAdjustment.adjusted_by_user_id)
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .where(TrkTripDistanceAdjustment.trip_id == trip_id)
            .order_by(TrkTripDistanceAdjustment.adjusted_at.desc(), TrkTripDistanceAdjustment.id.desc())
        )
        return [TripAdjustmentItem.model_validate(row) for row in rows.mappings()]

    def trips_for_service_call(self, call_id: int) -> list[CallTripHistoryItem]:
        """Every trip of a service call, across all its visits, oldest first.

        Trips hang off trk.trackable_activity, which for SVC points at a svc.service_visit; the visit
        carries the service_call_id. The (module_code, source_table) filter keeps the source_id join
        to service_visit sound despite trackable_activity being polymorphic."""
        adjustment_count = (
            select(func.count())
            .select_from(TrkTripDistanceAdjustment)
            .where(TrkTripDistanceAdjustment.trip_id == TrkTrip.id)
            .scalar_subquery()
        )
        def last_fix(column: Any) -> Any:
            return (
                select(column)
                .where(TrkTripGpsPoint.trip_id == TrkTrip.id)
                .order_by(TrkTripGpsPoint.recorded_at.desc(), TrkTripGpsPoint.id.desc())
                .limit(1)
                .correlate(TrkTrip)
                .scalar_subquery()
            )

        def first_battery() -> Any:
            return (
                select(TrkTripGpsPoint.battery_pct)
                .where(TrkTripGpsPoint.trip_id == TrkTrip.id, TrkTripGpsPoint.battery_pct.is_not(None))
                .order_by(TrkTripGpsPoint.recorded_at, TrkTripGpsPoint.id)
                .limit(1)
                .correlate(TrkTrip)
                .scalar_subquery()
            )

        rows = self._session.execute(
            select(
                TrkTrip.id,
                ServiceVisit.visit_no,
                TrkTrip.trip_type,
                TrkTrip.status,
                TrkTrip.employee_id.label("engineer_employee_id"),
                func.nullif(func.concat_ws(" ", Employee.first_name, Employee.last_name), "").label("engineer_name"),
                TrkTrip.start_at,
                TrkTrip.end_at,
                TrkTrip.duration_minutes,
                TrkTrip.start_latitude,
                TrkTrip.start_longitude,
                TrkTrip.end_latitude,
                TrkTrip.end_longitude,
                TrkTrip.gps_distance_km,
                TrkTrip.map_distance_km,
                TrkTrip.adjusted_distance_km,
                TrkTrip.is_distance_adjusted,
                _EFFECTIVE_DISTANCE_KM.label("effective_distance_km"),
                adjustment_count.label("adjustment_count"),
                last_fix(TrkTripGpsPoint.latitude).label("last_latitude"),
                last_fix(TrkTripGpsPoint.longitude).label("last_longitude"),
                last_fix(TrkTripGpsPoint.recorded_at).label("last_gps_at"),
                first_battery().label("start_battery_pct"),
                last_fix(TrkTripGpsPoint.battery_pct).label("end_battery_pct"),
                UserDevice.manufacturer.label("device_manufacturer"),
                UserDevice.model.label("device_model"),
                UserDevice.platform.label("device_platform"),
                UserDevice.os_version.label("device_os_version"),
                UserDevice.app_version.label("device_app_version"),
                TrkTrip.row_version,
            )
            .join(TrackableActivity, TrackableActivity.id == TrkTrip.trackable_activity_id)
            .join(ServiceVisit, ServiceVisit.id == TrackableActivity.source_id)
            .join(Employee, Employee.id == TrkTrip.employee_id)
            .outerjoin(UserDevice, UserDevice.id == TrkTrip.user_device_id)
            .where(
                TrackableActivity.module_code == "SVC",
                TrackableActivity.source_table == "service_visit",
                ServiceVisit.service_call_id == call_id,
                TrkTrip.is_active,
            )
            .order_by(TrkTrip.start_at, TrkTrip.id)
        )
        return [CallTripHistoryItem.model_validate(row) for row in rows.mappings()]

    def route_points(self, trip_id: int) -> tuple[list[RoutePoint], GpsQuality]:
        rows = self._session.execute(
            select(
                TrkTripGpsPoint.recorded_at,
                TrkTripGpsPoint.latitude,
                TrkTripGpsPoint.longitude,
                TrkTripGpsPoint.accuracy_m,
                TrkTripGpsPoint.is_mock_location,
            )
            .where(TrkTripGpsPoint.trip_id == trip_id)
            .order_by(TrkTripGpsPoint.recorded_at, TrkTripGpsPoint.id)
        ).mappings().all()
        accuracies = [float(r["accuracy_m"]) for r in rows if r["accuracy_m"] is not None]
        quality = GpsQuality(
            point_count=len(rows),
            avg_accuracy_m=round(sum(accuracies) / len(accuracies), 1) if accuracies else None,
            max_accuracy_m=max(accuracies) if accuracies else None,
            poor_accuracy_count=sum(1 for a in accuracies if a > POOR_ACCURACY_M),
            mock_location_count=sum(1 for r in rows if r["is_mock_location"]),
            first_recorded_at=rows[0]["recorded_at"] if rows else None,
            last_recorded_at=rows[-1]["recorded_at"] if rows else None,
        )
        # Thin long trails evenly for drawing, always keeping the first and last point.
        step = max(1, -(-len(rows) // MAX_ROUTE_POINTS))
        kept = rows[::step]
        if rows and kept[-1] is not rows[-1]:
            kept = [*kept, rows[-1]]
        return [RoutePoint.model_validate(r) for r in kept], quality

    def gps_fixes(self, trip_id: int) -> list[GpsFix]:
        rows = self._session.execute(
            select(
                TrkTripGpsPoint.recorded_at,
                TrkTripGpsPoint.latitude,
                TrkTripGpsPoint.longitude,
                TrkTripGpsPoint.accuracy_m,
                TrkTripGpsPoint.is_mock_location,
            )
            .where(TrkTripGpsPoint.trip_id == trip_id)
            .order_by(TrkTripGpsPoint.recorded_at)
        )
        return [
            GpsFix(
                recorded_at=at,
                latitude=float(lat),
                longitude=float(lon),
                accuracy_m=float(acc) if acc is not None else None,
                is_mock_location=bool(mock),
            )
            for at, lat, lon, acc, mock in rows
        ]

    def list(self, scope: RequestScope, query: TripListQuery) -> Page[TripListItem]:
        return paginate(self._session, self.list_statement(scope, query), query, TripListItem)

    @staticmethod
    def list_statement(scope: RequestScope, query: TripListQuery) -> Select[*tuple[Any, ...]]:
        statement = (
            select(
                TrkTrip.id,
                TrkTrip.employee_id,
                func.nullif(func.concat_ws(" ", Employee.first_name, Employee.last_name), "").label("employee_name"),
                TrackableActivity.module_code.label("module"),
                TrackableActivity.title.label("activity_title"),
                TrkTrip.trip_type,
                TrkTrip.status,
                TrkTrip.start_at,
                TrkTrip.end_at,
                TrkTrip.gps_distance_km,
                TrkTrip.adjusted_distance_km,
                TrkTrip.is_distance_adjusted,
                _EFFECTIVE_DISTANCE_KM.label("effective_distance_km"),
                TrkTrip.duration_minutes,
            )
            .join(TrackableActivity, TrackableActivity.id == TrkTrip.trackable_activity_id)
            .join(Employee, Employee.id == TrkTrip.employee_id)
            .where(TrkTrip.is_active)
        )
        # Managers see trips of their branch; row-level security is the backstop.
        if scope.branch_id is not None:
            statement = statement.where(Employee.branch_id == scope.branch_id)
        if query.employee_id is not None:
            statement = statement.where(TrkTrip.employee_id == query.employee_id)
        if query.status:
            statement = statement.where(TrkTrip.status.in_(query.status))
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    TrackableActivity.title.contains(term, autoescape=True),
                    Employee.first_name.contains(term, autoescape=True),
                    Employee.last_name.contains(term, autoescape=True),
                )
            )
        return order_by_sort(
            statement, query.sort, _SORT_COLUMNS, default="-startAt", tiebreaker=TrkTrip.id.desc()
        )
