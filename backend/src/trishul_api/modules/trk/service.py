from datetime import UTC, datetime
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.errors import ApiError, Conflict, NotFound
from trishul_api.common.schemas import Page
from trishul_api.db.models import TrackableActivity, TrkTrip, TrkTripGpsPoint
from trishul_api.modules.trk.handlers import handler_for
from trishul_api.modules.trk.repository import TripRepository
from trishul_api.modules.trk.schemas import (
    GpsBatchInput,
    GpsUploadResult,
    StartTripInput,
    StopTripInput,
    TripListItem,
    TripListQuery,
    TripOut,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _naive_utc(value: datetime) -> datetime:
    """DATETIME2 columns hold naive UTC; incoming UtcDateTime values are tz-aware. Match the DB so
    equality checks (GPS dedup) and arithmetic (duration) work."""
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo is not None else value


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(h))


class TripService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = TripRepository(db)

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

        now = _naive_utc(data.started_at) if data.started_at else _utcnow()
        activity = handler_for(data.module).resolve(
            self._db, employee_id, data.reference_id, user.id, data.start_latitude, data.start_longitude, now
        )
        device_pk = self._repo.device_id_for(user.id, data.device_id) if data.device_id else None
        trip = TrkTrip(
            trackable_activity_id=activity.id,
            employee_id=employee_id,
            user_device_id=device_pk,
            client_uuid=data.client_uuid,
            trip_type=data.trip_type,
            start_at=now,
            start_latitude=data.start_latitude,
            start_longitude=data.start_longitude,
            vehicle_type=data.vehicle_type,
            status="In progress",
            created_by_user_id=user.id,
        )
        self._repo.add(trip)
        self._db.commit()
        return self._to_out(trip, activity)

    def upload_gps(self, user: CurrentUser, trip_id: int, batch: GpsBatchInput) -> GpsUploadResult:
        trip = self._own_trip(user, trip_id)
        if trip.status != "In progress":
            raise ApiError("This trip is not in progress; GPS points cannot be added.")
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
        self._db.commit()
        return GpsUploadResult(accepted=accepted, duplicates_ignored=duplicates, trip_status=trip.status)

    def stop(self, user: CurrentUser, trip_id: int, data: StopTripInput) -> TripOut:
        trip = self._own_trip(user, trip_id)
        if trip.status == "Completed":  # idempotent: stopping a stopped trip is a no-op
            return self._to_out(trip)
        if trip.status != "In progress":
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
        trip.status = "Completed"
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
        return self._repo.list(scope, query)

    # ------------------------------------------------------------------ helpers

    def _own_trip(self, user: CurrentUser, trip_id: int) -> TrkTrip:
        employee_id = self._require_engineer(user)
        trip = self._repo.get_trip(trip_id)
        if trip is None or not trip.is_active or trip.employee_id != employee_id:
            raise NotFound("Trip not found.")
        return trip

    def _gps_distance(self, trip_id: int) -> float | None:
        points = self._repo.gps_points(trip_id)
        if len(points) < 2:
            return None
        total = sum(_haversine_km(points[i - 1], points[i]) for i in range(1, len(points)))
        return round(total, 2)

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
            duration_minutes=trip.duration_minutes,
            row_version=trip.row_version,
        )
