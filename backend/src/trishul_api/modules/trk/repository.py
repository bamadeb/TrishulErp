from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import RequestScope
from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import Employee, TrackableActivity, TrkTrip, TrkTripGpsPoint, UserDevice
from trishul_api.modules.trk.schemas import TripListItem, TripListQuery

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
                TrkTrip.employee_id == employee_id, TrkTrip.status == "In progress", TrkTrip.is_active
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

    def gps_points(self, trip_id: int) -> list[tuple[float, float]]:
        rows = self._session.execute(
            select(TrkTripGpsPoint.latitude, TrkTripGpsPoint.longitude)
            .where(TrkTripGpsPoint.trip_id == trip_id)
            .order_by(TrkTripGpsPoint.recorded_at)
        )
        return [(float(lat), float(lon)) for lat, lon in rows]

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
