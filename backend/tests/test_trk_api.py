"""Common trip engine: the /trk endpoints, and the service's idempotency / conflict / dedup rules."""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from trishul_api.auth import RequestScope, get_current_user
from trishul_api.common.errors import ApiError, Conflict, NotFound
from trishul_api.common.schemas import Page
from trishul_api.modules.trk.repository import TripRepository
from trishul_api.modules.trk.router import get_trip_service
from trishul_api.modules.trk.schemas import (
    AdjustDistanceInput,
    GpsBatchInput,
    GpsUploadResult,
    MyTripListQuery,
    StartTripInput,
    StopTripInput,
    TripListItem,
    TripListQuery,
    TripOut,
)
from trishul_api.modules.trk.service import TripService

from .conftest import make_user
from .helpers import mssql_sql


def _trip_out(status: str = "In progress", end_at: datetime | None = None) -> TripOut:
    return TripOut(
        id=5501,
        trackable_activity_id=3301,
        employee_id=5,
        module="SVC",
        reference_id=9001,
        trip_type="To site",
        status=status,
        start_at=datetime(2026, 10, 28, 6, 35),
        start_latitude=20.2961,
        start_longitude=85.8245,
        end_at=end_at,
        end_latitude=None,
        end_longitude=None,
        gps_distance_km=None,
        adjusted_distance_km=None,
        is_distance_adjusted=False,
        effective_distance_km=None,
        duration_minutes=None,
        row_version=b"\x00\x00\x00\x00\x00\x00\x07\xd1",
    )


class FakeTripService:
    def __init__(self) -> None:
        self.started: list[tuple[int, StartTripInput]] = []
        self.gps: list[tuple[int, int, GpsBatchInput]] = []
        self.stopped: list[tuple[int, int]] = []

    def start(self, user: Any, data: StartTripInput) -> TripOut:
        self.started.append((user.id, data))
        return _trip_out()

    def upload_gps(self, user: Any, trip_id: int, batch: GpsBatchInput) -> GpsUploadResult:
        self.gps.append((user.id, trip_id, batch))
        return GpsUploadResult(accepted=len(batch.points), duplicates_ignored=0, trip_status="In progress")

    def stop(self, user: Any, trip_id: int, data: StopTripInput) -> TripOut:
        self.stopped.append((user.id, trip_id))
        return _trip_out(status="Completed", end_at=datetime(2026, 10, 28, 8, 10))

    def get(self, user: Any, trip_id: int) -> TripOut:
        return _trip_out()

    def review(self, scope: RequestScope, query: TripListQuery) -> Page[TripListItem]:
        return Page(items=[], total=0, page=query.page, page_size=query.page_size)

    def my_trips(self, user: Any, query: MyTripListQuery) -> Page[TripListItem]:
        self.my_trips_for = user.id
        return Page(items=[], total=0, page=query.page, page_size=query.page_size)

    def adjustments(self, user: Any, trip_id: int) -> list[Any]:
        return []


def use_trip_service(api: FastAPI) -> FakeTripService:
    service = FakeTripService()
    api.dependency_overrides[get_trip_service] = lambda: service
    return service


def _field_user(api: FastAPI, **overrides: object) -> Any:
    user = make_user(permissions=frozenset({"trk.trip.manage"}), employee_id=5, **overrides)
    api.dependency_overrides[get_current_user] = lambda: user
    return user


def _start_body() -> dict[str, Any]:
    return {
        "clientUuid": str(uuid4()),
        "module": "SVC",
        "referenceId": 9001,
        "tripType": "To site",
        "startLatitude": 20.2961,
        "startLongitude": 85.8245,
    }


# ---------------------------------------------------------------- endpoints


def test_start_trip_returns_201(api: FastAPI, client: TestClient) -> None:
    user = _field_user(api)
    service = use_trip_service(api)
    response = client.post("/api/v1/trk/trips", json=_start_body())
    assert response.status_code == 201
    assert service.started[0][0] == user.id
    assert response.json()["status"] == "In progress"


def test_start_trip_needs_manage_permission(api: FastAPI, client: TestClient) -> None:
    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset({"trk.trip.view.team"}))
    use_trip_service(api)
    assert client.post("/api/v1/trk/trips", json=_start_body()).status_code == 403


@pytest.mark.parametrize(
    "patch",
    [
        {"startLatitude": 120},  # out of range
        {"startLongitude": -200},
        {"module": "XYZ"},  # not a known module
        {"referenceId": 0},  # must be > 0
        {"clientUuid": "not-a-uuid"},
        {"deviceId": "x" * 101},  # too long
    ],
)
def test_start_trip_validates_the_body(api: FastAPI, client: TestClient, patch: dict[str, Any]) -> None:
    _field_user(api)
    use_trip_service(api)
    assert client.post("/api/v1/trk/trips", json={**_start_body(), **patch}).status_code == 422


def test_upload_gps_points(api: FastAPI, client: TestClient) -> None:
    _field_user(api)
    service = use_trip_service(api)
    response = client.post(
        "/api/v1/trk/trips/5501/gps-points",
        json={"points": [{"recordedAt": "2026-10-28T06:36:00Z", "latitude": 20.297, "longitude": 85.826}]},
    )
    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    assert service.gps[0][1] == 5501


def test_upload_gps_rejects_empty_batch(api: FastAPI, client: TestClient) -> None:
    _field_user(api)
    use_trip_service(api)
    assert client.post("/api/v1/trk/trips/5501/gps-points", json={"points": []}).status_code == 422


def test_stop_and_get_trip(api: FastAPI, client: TestClient) -> None:
    user = _field_user(api)
    service = use_trip_service(api)
    stop = client.post("/api/v1/trk/trips/5501/stop", json={"endLatitude": 22.1, "endLongitude": 85.38})
    assert stop.status_code == 200
    assert stop.json()["status"] == "Completed"
    assert service.stopped == [(user.id, 5501)]
    assert client.get("/api/v1/trk/trips/5501").status_code == 200


def test_review_needs_team_permission(api: FastAPI, client: TestClient) -> None:
    _field_user(api)  # has trk.trip.manage but not trk.trip.view.team
    use_trip_service(api)
    assert client.get("/api/v1/trk/trips").status_code == 403


def test_review_allowed_for_team_viewer(api: FastAPI, client: TestClient) -> None:
    api.dependency_overrides[get_current_user] = lambda: make_user(
        permissions=frozenset({"trk.trip.view.team"}), employee_id=1
    )
    use_trip_service(api)
    assert client.get("/api/v1/trk/trips").status_code == 200


def test_engineer_lists_own_trips(api: FastAPI, client: TestClient) -> None:
    user = _field_user(api)
    service = use_trip_service(api)
    response = client.get("/api/v1/trk/trips/mine", params={"status": "Completed"})
    assert response.status_code == 200  # not swallowed by /trips/{tripId}
    assert service.my_trips_for == user.id


def test_my_trips_needs_manage_permission(api: FastAPI, client: TestClient) -> None:
    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset({"svc.call.view"}))
    use_trip_service(api)
    assert client.get("/api/v1/trk/trips/mine").status_code == 403


def test_engineer_can_open_adjustment_trail(api: FastAPI, client: TestClient) -> None:
    _field_user(api)
    use_trip_service(api)
    assert client.get("/api/v1/trk/trips/5501/adjustments").status_code == 200


# ---------------------------------------------------------------- service rules


class _FakeRepo:
    def __init__(
        self,
        by_uuid: Any = None,
        active: Any = None,
        trip: Any = None,
        existing_times: set[datetime] | None = None,
        branch_id: int | None = 1,
    ):
        self._by_uuid = by_uuid
        self._active = active
        self._trip = trip
        self._existing_times: set[datetime] = existing_times or set()
        self._branch_id = branch_id
        self.added: list[Any] = []
        self.activity = SimpleNamespace(id=3301, module_code="SVC", source_id=9001)

    def employee_branch_id(self, _employee_id: int) -> int | None:
        return self._branch_id

    def trip_by_client_uuid(self, _uuid: Any) -> Any:
        return self._by_uuid

    def active_trip_for_employee(self, _employee_id: int) -> Any:
        return self._active

    def get_trip(self, _trip_id: int) -> Any:
        return self._trip

    def get_activity(self, _activity_id: int) -> Any:
        return self.activity

    def existing_gps_times(self, _trip_id: int, _times: list[Any]) -> set[datetime]:
        return set(self._existing_times)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def adjustments_for_trip(self, _trip_id: int) -> list[Any]:
        return []

    def list(self, scope: RequestScope, query: TripListQuery) -> Page[TripListItem]:
        self.listed = (scope, query)
        return Page(items=[], total=0, page=query.page, page_size=query.page_size)


def _service_with(repo: _FakeRepo) -> TripService:
    service = TripService.__new__(TripService)
    service._db = SimpleNamespace(commit=lambda: None)  # type: ignore[assignment]
    service._repo = repo  # type: ignore[assignment]
    return service


def _existing_trip() -> Any:
    return SimpleNamespace(
        id=5501, trackable_activity_id=3301, employee_id=5, trip_type="To site", status="In progress",
        is_active=True, start_at=datetime(2026, 10, 28, 6, 35), start_latitude=20.2961, start_longitude=85.8245,
        end_at=None, end_latitude=None, end_longitude=None, gps_distance_km=None, map_distance_km=None,
        adjusted_distance_km=None, is_distance_adjusted=False, duration_minutes=None,
        row_version=b"\x00\x00\x00\x00\x00\x00\x07\xd1",
    )


def _start_input() -> StartTripInput:
    return StartTripInput.model_validate(
        {"clientUuid": str(uuid4()), "module": "SVC", "referenceId": 9001,
         "startLatitude": 20.2961, "startLongitude": 85.8245}
    )


def test_start_is_idempotent_on_client_uuid() -> None:
    repo = _FakeRepo(by_uuid=_existing_trip())
    service = _service_with(repo)
    out = service.start(make_user(employee_id=5), _start_input())
    assert out.id == 5501
    assert repo.added == []  # no new trip created on a retry


def test_start_rejects_a_second_active_trip() -> None:
    repo = _FakeRepo(active=_existing_trip())
    service = _service_with(repo)
    with pytest.raises(Conflict):
        service.start(make_user(employee_id=5), _start_input())


def test_upload_gps_deduplicates_within_and_across_batches() -> None:
    t0 = datetime(2026, 10, 28, 6, 36)
    t1 = datetime(2026, 10, 28, 6, 37)
    repo = _FakeRepo(trip=_existing_trip(), existing_times={t0})  # t0 already stored
    service = _service_with(repo)
    batch = GpsBatchInput.model_validate(
        {
            "points": [
                {"recordedAt": t0, "latitude": 20.1, "longitude": 85.1},  # duplicate of stored
                {"recordedAt": t1, "latitude": 20.2, "longitude": 85.2},  # new
                {"recordedAt": t1, "latitude": 20.2, "longitude": 85.2},  # duplicate within batch
            ]
        }
    )
    result = service.upload_gps(make_user(employee_id=5), 5501, batch)
    assert (result.accepted, result.duplicates_ignored) == (1, 2)
    assert len(repo.added) == 1


def test_upload_gps_rejects_a_stopped_trip() -> None:
    trip = _existing_trip()
    trip.status = "Completed"
    service = _service_with(_FakeRepo(trip=trip))
    batch = GpsBatchInput.model_validate(
        {"points": [{"recordedAt": datetime(2026, 10, 28, 6, 36), "latitude": 20.1, "longitude": 85.1}]}
    )
    with pytest.raises(ApiError):
        service.upload_gps(make_user(employee_id=5), 5501, batch)


# ---------------------------------------------------------------- manual distance adjustment


def _completed_trip(gps: Decimal | None = Decimal("12.00")) -> Any:
    trip = _existing_trip()
    trip.status = "Completed"
    trip.gps_distance_km = gps
    trip.end_at = datetime(2026, 10, 28, 8, 10)
    return trip


def _adjust_input(new_km: str = "18.50", reason: str = "GPS under-counted on the hill road") -> AdjustDistanceInput:
    return AdjustDistanceInput.model_validate({"newDistanceKm": new_km, "reason": reason})


_ROW_VERSION = b"\x00\x00\x00\x00\x00\x00\x07\xd1"


def test_adjust_distance_logs_audit_and_sets_effective_without_touching_gps() -> None:
    trip = _completed_trip()
    repo = _FakeRepo(trip=trip)
    service = _service_with(repo)
    out = service.adjust_distance(make_user(id=7, branch_ids=None), 5501, _ROW_VERSION, _adjust_input())

    assert len(repo.added) == 1
    audit = repo.added[0]
    assert (audit.trip_id, audit.new_distance_km, audit.reason) == (5501, Decimal("18.50"), _adjust_input().reason)
    assert audit.previous_distance_km == Decimal("12.00")  # the GPS value it replaced
    assert audit.gps_distance_km_at_adjustment == Decimal("12.00")
    assert audit.adjusted_by_user_id == 7
    # GPS preserved; the manual value becomes effective.
    assert trip.gps_distance_km == Decimal("12.00")
    assert trip.adjusted_distance_km == Decimal("18.50")
    assert trip.is_distance_adjusted is True
    assert out.effective_distance_km == 18.5
    assert out.is_distance_adjusted is True


def test_adjust_distance_rejects_a_trip_in_progress() -> None:
    service = _service_with(_FakeRepo(trip=_existing_trip()))  # status "In progress"
    with pytest.raises(ApiError):
        service.adjust_distance(make_user(branch_ids=None), 5501, _ROW_VERSION, _adjust_input())


def test_adjust_distance_conflicts_on_stale_row_version() -> None:
    service = _service_with(_FakeRepo(trip=_completed_trip()))
    with pytest.raises(Conflict):
        service.adjust_distance(make_user(branch_ids=None), 5501, b"stale-version", _adjust_input())


def test_adjust_distance_hides_a_trip_outside_the_users_branches() -> None:
    # The trip's engineer is in branch 9; the Team Lead only covers 1 and 2.
    repo = _FakeRepo(trip=_completed_trip(), branch_id=9)
    service = _service_with(repo)
    with pytest.raises(NotFound):
        service.adjust_distance(make_user(branch_ids=frozenset({1, 2})), 5501, _ROW_VERSION, _adjust_input())
    assert repo.added == []


# ---------------------------------------------------------------- review SQL


def _review_sql(scope: RequestScope, **query: Any) -> str:
    statement = TripRepository.list_statement(scope, TripListQuery(**query))
    return mssql_sql(statement.offset(0).limit(20))


def test_review_sql_filters_by_branch_employee_and_status() -> None:
    text = _review_sql(RequestScope(branch_id=3, principal_id=None), employee_id=5, status=["Completed"])
    assert "core.employee.branch_id = 3" in text
    assert "trk.trip.employee_id = 5" in text
    assert "trk.trip.status IN (N'Completed')" in text


# ---------------------------------------------------------------- own trips


def test_my_trips_is_pinned_to_the_callers_employee() -> None:
    repo = _FakeRepo()
    service = _service_with(repo)
    service.my_trips(make_user(employee_id=5), MyTripListQuery(status=["Completed"]))
    scope, query = repo.listed
    assert query.employee_id == 5
    assert query.status == ["Completed"]
    assert scope.branch_id is None  # own trips from every branch, but only one's own


def test_my_trips_ignores_an_employee_id_in_the_request() -> None:
    # Extra query params are not part of MyTripListQuery, so another engineer cannot be asked for.
    query = MyTripListQuery.model_validate({"employeeId": 99})
    assert "employee_id" not in query.model_dump()


def test_my_trips_requires_a_linked_employee() -> None:
    service = _service_with(_FakeRepo())
    with pytest.raises(NotFound):
        service.my_trips(make_user(employee_id=None), MyTripListQuery())


def test_engineer_cannot_read_another_engineers_adjustment_trail() -> None:
    other = _completed_trip()
    other.employee_id = 77
    service = _service_with(_FakeRepo(trip=other))
    engineer = make_user(permissions=frozenset({"trk.trip.manage"}), employee_id=5)
    with pytest.raises(NotFound):
        service.adjustments(engineer, 5501)


def test_engineer_reads_own_adjustment_trail() -> None:
    service = _service_with(_FakeRepo(trip=_completed_trip()))  # employee 5
    engineer = make_user(permissions=frozenset({"trk.trip.manage"}), employee_id=5)
    assert service.adjustments(engineer, 5501) == []


def test_review_my_trips_sql_filters_only_by_employee() -> None:
    text = _review_sql(RequestScope(branch_id=None, principal_id=None), employee_id=5)
    assert "trk.trip.employee_id = 5" in text
    assert "core.employee.branch_id" not in text


def test_reviewer_cannot_read_adjustment_trail_outside_their_branches() -> None:
    # The trip's engineer is in branch 9; the Team Lead only covers 1 and 2.
    service = _service_with(_FakeRepo(trip=_completed_trip(), branch_id=9))
    lead = make_user(permissions=frozenset({"trk.trip.view.team"}), branch_ids=frozenset({1, 2}))
    with pytest.raises(NotFound):
        service.adjustments(lead, 5501)


def test_reviewer_reads_adjustment_trail_in_their_branch() -> None:
    service = _service_with(_FakeRepo(trip=_completed_trip(), branch_id=1))
    lead = make_user(permissions=frozenset({"trk.trip.view.team"}), branch_ids=frozenset({1, 2}))
    assert service.adjustments(lead, 5501) == []


def test_admin_reads_any_adjustment_trail() -> None:
    service = _service_with(_FakeRepo(trip=_completed_trip(), branch_id=9))
    admin = make_user(permissions=frozenset({"trk.trip.adjust"}), branch_ids=None)
    assert service.adjustments(admin, 5501) == []
