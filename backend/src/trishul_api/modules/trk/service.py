from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, Conflict, NotFound
from trishul_api.common.schemas import Page, PageQuery
from trishul_api.db.models import (
    ServiceCall,
    TrackableActivity,
    TrkTrip,
    TrkTripDistanceAdjustment,
    TrkTripGpsDiagnostic,
    TrkTripGpsPoint,
)
from trishul_api.modules.trk.constants import COMPLETED, IN_PROGRESS, LATE_UPLOAD_GRACE_DAYS
from trishul_api.modules.trk.distance import route_distance_km
from trishul_api.modules.trk.handlers import handler_for
from trishul_api.modules.trk.master_service import TripMasterService
from trishul_api.modules.trk.repository import TripRepository
from trishul_api.modules.trk.schemas import (
    AdjustDistanceInput,
    CallTripHistoryItem,
    GpsBatchInput,
    GpsDiagnosticBatchInput,
    GpsDiagnosticItem,
    GpsDiagnosticUploadResult,
    GpsUploadResult,
    MyTripListQuery,
    StartTripInput,
    StopTripInput,
    SyncSection,
    TripAdjustmentItem,
    TripListItem,
    TripListQuery,
    TripOut,
    TripSyncQuery,
    TripSyncStatus,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _naive_utc(value: datetime) -> datetime:
    """DATETIME2 columns hold naive UTC; incoming UtcDateTime values are tz-aware. Match the DB so
    equality checks (GPS dedup) and arithmetic (duration) work."""
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo is not None else value


class TripService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = TripRepository(db)
        self._master = TripMasterService(db)

    def _require_engineer(self, user: CurrentUser) -> int:
        if user.employee_id is None:
            raise NotFound("Your account is not linked to an employee, so it cannot own trips.")
        return user.employee_id

    def start(self, user: CurrentUser, data: StartTripInput) -> TripOut:
        employee_id = self._require_engineer(user)

        existing = self._repo.trip_by_client_uuid(data.client_uuid)
        if existing is not None:  # idempotent: a retried start returns the same trip
            return self._to_out(existing)

        if self._repo.active_trip_for_employee(employee_id) is not None:
            raise Conflict("You already have a trip in progress. Stop it before starting another.")

        # Master values are checked after the idempotent replay above, so a retry still returns the
        # trip even if its vehicle type has since been deactivated.
        trip_type = self._master.resolve_start(data.module, data.trip_type, data.vehicle_type)

        now = _naive_utc(data.started_at) if data.started_at else _utcnow()
        activity = handler_for(data.module).resolve(
            self._db,
            employee_id,
            data.reference_id,
            user.id,
            data.start_latitude,
            data.start_longitude,
            now,
            data.client_uuid,
        )
        device_pk = self._repo.device_id_for(user.id, data.device_id) if data.device_id else None
        trip = TrkTrip(
            trackable_activity_id=activity.id,
            employee_id=employee_id,
            user_device_id=device_pk,
            client_uuid=data.client_uuid,
            trip_type=trip_type,
            start_at=now,
            start_latitude=data.start_latitude,
            start_longitude=data.start_longitude,
            vehicle_type=data.vehicle_type,
            status=IN_PROGRESS,
            created_by_user_id=user.id,
        )
        self._repo.add(trip)
        self._db.commit()
        return self._to_out(trip, activity)

    def upload_gps(self, user: CurrentUser, trip_id: int, batch: GpsBatchInput) -> GpsUploadResult:
        trip = self._own_trip(user, trip_id)
        self._require_open_for_upload(trip, "GPS points")
        times = [_naive_utc(p.recorded_at) for p in batch.points]
        seen = self._repo.existing_gps_times(trip_id, times)
        accepted = duplicates = 0
        for point in batch.points:
            recorded_at = _naive_utc(point.recorded_at)
            if recorded_at in seen:  # dedup across retries and within the batch
                duplicates += 1
                continue
            seen.add(recorded_at)
            self._repo.add(
                TrkTripGpsPoint(
                    trip_id=trip_id,
                    recorded_at=recorded_at,
                    latitude=point.latitude,
                    longitude=point.longitude,
                    accuracy_m=point.accuracy_m,
                    speed_kmph=point.speed_kmph,
                    battery_pct=point.battery_pct,
                    is_mock_location=point.is_mock_location,
                )
            )
            accepted += 1
        if accepted and trip.status != IN_PROGRESS:
            # Points that arrive after the stop (device was offline) change the route: recompute.
            self._refresh_gps_distance(trip, user.id)
        self._db.commit()
        return GpsUploadResult(accepted=accepted, duplicates_ignored=duplicates, trip_status=trip.status)

    def upload_gps_diagnostics(
        self, user: CurrentUser, trip_id: int, batch: GpsDiagnosticBatchInput
    ) -> GpsDiagnosticUploadResult:
        trip = self._own_trip(user, trip_id)
        self._require_open_for_upload(trip, "GPS diagnostic events")
        self._master.require_known_diagnostic_event_types([e.event_type for e in batch.events])
        seen = self._repo.existing_diagnostic_ids(trip_id, [e.event_id for e in batch.events])
        accepted = duplicates = 0
        for event in batch.events:
            if event.event_id in seen:  # dedup across retries and within the batch
                duplicates += 1
                continue
            seen.add(event.event_id)
            self._repo.add(
                TrkTripGpsDiagnostic(
                    trip_id=trip_id,
                    **event.model_dump(exclude={"recorded_at"}),
                    recorded_at=_naive_utc(event.recorded_at),
                )
            )
            accepted += 1
        self._db.commit()
        return GpsDiagnosticUploadResult(accepted=accepted, duplicates_ignored=duplicates)

    def gps_diagnostics(self, user: CurrentUser, trip_id: int, query: PageQuery) -> Page[GpsDiagnosticItem]:
        """Diagnostic events of a trip: the engineer's own, or any trip in a reviewer's branches."""
        self._viewable_trip(user, trip_id)
        return self._repo.diagnostics_for_trip(trip_id, query)

    def sync_status(self, user: CurrentUser, trip_id: int, query: TripSyncQuery) -> TripSyncStatus:
        """Compare what the device says it recorded with what the server persisted, so the app knows
        whether it is safe to delete its local copy. Counts unique stored rows, not requests."""
        trip = self._viewable_trip(user, trip_id)
        gps = self._sync_section(self._repo.gps_point_stats(trip_id), query.expected_gps_records)
        diagnostics = self._sync_section(self._repo.diagnostic_stats(trip_id), query.expected_diagnostic_records)
        checked = [s.sync_complete for s in (gps, diagnostics) if s.sync_complete is not None]
        return TripSyncStatus(
            trip_id=trip.id,
            trip_status=trip.status,
            gps_sync=gps,
            diagnostics_sync=diagnostics,
            overall_sync_complete=trip.status != IN_PROGRESS and bool(checked) and all(checked),
        )

    @staticmethod
    def _sync_section(stats: tuple[int, datetime | None, datetime | None], expected: int | None) -> SyncSection:
        stored, first, last = stats
        return SyncSection(
            stored_records=stored,
            first_recorded_at=first,
            last_recorded_at=last,
            expected_records=expected,
            pending_records=max(expected - stored, 0) if expected is not None else None,
            sync_complete=stored >= expected if expected is not None else None,
        )

    def stop(self, user: CurrentUser, trip_id: int, data: StopTripInput) -> TripOut:
        trip = self._own_trip(user, trip_id)
        if trip.status == COMPLETED:  # idempotent: stopping a stopped trip is a no-op
            return self._to_out(trip)
        if trip.status != IN_PROGRESS:
            raise ApiError(f"This trip is {trip.status.lower()} and cannot be stopped.")

        now = _naive_utc(data.ended_at) if data.ended_at else _utcnow()
        if now < trip.start_at:
            raise ApiError("The trip end time is before its start time.")
        distance = self._gps_distance(trip_id)
        trip.end_at = now
        trip.end_latitude = Decimal(str(data.end_latitude))
        trip.end_longitude = Decimal(str(data.end_longitude))
        trip.duration_minutes = int((now - trip.start_at).total_seconds() // 60)
        trip.gps_distance_km = Decimal(str(distance)) if distance is not None else None
        trip.status = COMPLETED
        trip.updated_at = now
        trip.updated_by_user_id = user.id

        activity = self._repo.get_activity(trip.trackable_activity_id)
        if activity is not None:
            handler_for(activity.module_code).on_stop(
                self._db, activity, user.id, data.end_latitude, data.end_longitude, now
            )
        self._db.commit()
        return self._to_out(trip, activity)

    def get(self, user: CurrentUser, trip_id: int) -> TripOut:
        return self._to_out(self._own_trip(user, trip_id))

    def review(self, scope: RequestScope, query: TripListQuery) -> Page[TripListItem]:
        self._master.require_known_statuses(query.status)
        return self._repo.list(scope, query)

    def my_trips(self, user: CurrentUser, query: MyTripListQuery) -> Page[TripListItem]:
        """The caller's own trips, whichever branch they were made in; never anyone else's."""
        employee_id = self._require_engineer(user)
        self._master.require_known_statuses(query.status)
        own = TripListQuery(**query.model_dump(), employee_id=employee_id)
        return self._repo.list(RequestScope(branch_id=None, principal_id=None), own)

    def adjust_distance(
        self, user: CurrentUser, trip_id: int, expected_row_version: bytes, data: AdjustDistanceInput
    ) -> TripOut:
        """A Team Lead overrides the distance where GPS is unreliable. The GPS value is preserved;
        the manual value becomes effective and every change is appended to the audit trail."""
        trip = self._repo.get_trip(trip_id)
        if trip is None or not trip.is_active or not self._in_user_branch(user, trip.employee_id):
            raise NotFound("Trip not found.")
        if trip.status == IN_PROGRESS:
            raise ApiError("This trip is still in progress; adjust its distance once it is completed.")
        check_row_version(trip.row_version, expected_row_version)

        now = _utcnow()
        # The value being replaced, for the audit trail: a prior manual value, else Maps, else GPS.
        previous = trip.adjusted_distance_km if trip.is_distance_adjusted else trip.map_distance_km
        if previous is None:
            previous = trip.gps_distance_km
        self._repo.add(
            TrkTripDistanceAdjustment(
                trip_id=trip.id,
                previous_distance_km=previous,
                new_distance_km=data.new_distance_km,
                gps_distance_km_at_adjustment=trip.gps_distance_km,
                reason=data.reason,
                adjusted_by_user_id=user.id,
                adjusted_at=now,
            )
        )
        trip.adjusted_distance_km = data.new_distance_km
        trip.is_distance_adjusted = True
        trip.updated_at = now
        trip.updated_by_user_id = user.id
        self._db.commit()
        return self._to_out(trip)

    def adjustments(self, user: CurrentUser, trip_id: int) -> list[TripAdjustmentItem]:
        self._viewable_trip(user, trip_id)
        return self._repo.adjustments_for_trip(trip_id)

    def trips_for_service_call(self, user: CurrentUser, call_id: int) -> list[CallTripHistoryItem]:
        call = self._db.get(ServiceCall, call_id)
        if call is None or not call.is_active or not user.can_use_branch(call.branch_id):
            raise NotFound("Service call not found.")
        return self._repo.trips_for_service_call(call_id)

    # ------------------------------------------------------------------ helpers

    def _in_user_branch(self, user: CurrentUser, employee_id: int) -> bool:
        if user.branch_ids is None:  # no branch restriction (e.g. Admin)
            return True
        branch_id = self._repo.employee_branch_id(employee_id)
        return branch_id is not None and branch_id in user.branch_ids

    def _viewable_trip(self, user: CurrentUser, trip_id: int) -> TrkTrip:
        """Reviewers see trips of their branches; an engineer only their own trip."""
        if not user.can("trk.trip.view.team", "trk.trip.adjust"):
            return self._own_trip(user, trip_id)
        trip = self._repo.get_trip(trip_id)
        if trip is None or not trip.is_active or not self._in_user_branch(user, trip.employee_id):
            raise NotFound("Trip not found.")
        return trip

    def _own_trip(self, user: CurrentUser, trip_id: int) -> TrkTrip:
        employee_id = self._require_engineer(user)
        trip = self._repo.get_trip(trip_id)
        if trip is None or not trip.is_active or trip.employee_id != employee_id:
            raise NotFound("Trip not found.")
        return trip

    @staticmethod
    def _require_open_for_upload(trip: TrkTrip, what: str) -> None:
        """Data may be added while the trip runs and for a grace period after it ends, because a
        device that was offline uploads late."""
        if trip.status == IN_PROGRESS:
            return
        if trip.end_at is None or _utcnow() - trip.end_at > timedelta(days=LATE_UPLOAD_GRACE_DAYS):
            raise ApiError(f"This trip ended more than {LATE_UPLOAD_GRACE_DAYS} days ago; {what} cannot be added.")

    def _refresh_gps_distance(self, trip: TrkTrip, user_id: int) -> None:
        """Recompute the GPS distance of a stopped trip. Only the GPS value moves: a Team Lead's manual
        adjustment is a separate column and stays effective."""
        self._repo.flush()  # the recompute must see the points added in this request
        distance = self._gps_distance(trip.id)
        trip.gps_distance_km = Decimal(str(distance)) if distance is not None else None
        trip.updated_at = _utcnow()
        trip.updated_by_user_id = user_id

    def _gps_distance(self, trip_id: int) -> float | None:
        return route_distance_km(self._repo.gps_fixes(trip_id))

    def _to_out(self, trip: TrkTrip, activity: TrackableActivity | None = None) -> TripOut:
        activity = activity or self._repo.get_activity(trip.trackable_activity_id)
        assert activity is not None  # a trip always has its activity (FK)
        return TripOut(
            id=trip.id,
            trackable_activity_id=trip.trackable_activity_id,
            employee_id=trip.employee_id,
            module=activity.module_code,
            reference_id=activity.source_id,
            trip_type=trip.trip_type,
            status=trip.status,
            start_at=trip.start_at,
            start_latitude=float(trip.start_latitude),
            start_longitude=float(trip.start_longitude),
            end_at=trip.end_at,
            end_latitude=float(trip.end_latitude) if trip.end_latitude is not None else None,
            end_longitude=float(trip.end_longitude) if trip.end_longitude is not None else None,
            gps_distance_km=float(trip.gps_distance_km) if trip.gps_distance_km is not None else None,
            adjusted_distance_km=float(trip.adjusted_distance_km) if trip.adjusted_distance_km is not None else None,
            is_distance_adjusted=trip.is_distance_adjusted,
            effective_distance_km=self._effective_distance(trip),
            duration_minutes=trip.duration_minutes,
            row_version=trip.row_version,
        )

    @staticmethod
    def _effective_distance(trip: TrkTrip) -> float | None:
        """Distance used for reporting: manual adjustment wins, else Maps, else GPS (matches the SQL
        COALESCE). None-checks, not truthiness, so a valid 0 km adjustment still wins."""
        for value in (trip.adjusted_distance_km, trip.map_distance_km, trip.gps_distance_km):
            if value is not None:
                return float(value)
        return None
