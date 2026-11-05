"""Common trip engine: the /trk endpoints, and the service's idempotency / conflict / dedup rules."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from trishul_api.auth import RequestScope, get_current_user
from trishul_api.common.errors import ApiError, Conflict, NotFound
from trishul_api.common.schemas import Page
from trishul_api.modules.trk.constants import LATE_UPLOAD_GRACE_DAYS
from trishul_api.modules.trk.distance import GpsFix
from trishul_api.modules.trk.master_service import InvalidMasterValue, TripMasterService
from trishul_api.modules.trk.repository import TripRepository
from trishul_api.modules.trk.router import get_trip_master_service, get_trip_service
from trishul_api.modules.trk.schemas import (
    AdjustDistanceInput,
    GpsBatchInput,
    GpsDiagnosticBatchInput,
    GpsDiagnosticUploadResult,
    GpsUploadResult,
    MyTripListQuery,
    StartTripInput,
    StopTripInput,
    TripListItem,
    TripListQuery,
    TripOut,
    TripSyncQuery,
    TripSyncStatus,
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
        self.diagnostics: list[tuple[int, int, GpsDiagnosticBatchInput]] = []
        self.stopped: list[tuple[int, int]] = []

    def start(self, user: Any, data: StartTripInput) -> TripOut:
        self.started.append((user.id, data))
        return _trip_out()

    def upload_gps(self, user: Any, trip_id: int, batch: GpsBatchInput) -> GpsUploadResult:
        self.gps.append((user.id, trip_id, batch))
        return GpsUploadResult(accepted=len(batch.points), duplicates_ignored=0, trip_status="In progress")

    def upload_gps_diagnostics(
        self, user: Any, trip_id: int, batch: GpsDiagnosticBatchInput
    ) -> GpsDiagnosticUploadResult:
        self.diagnostics.append((user.id, trip_id, batch))
        return GpsDiagnosticUploadResult(accepted=len(batch.events), duplicates_ignored=0)

    def gps_diagnostics(self, user: Any, trip_id: int, query: Any) -> Page[Any]:
        return Page(items=[], total=0, page=query.page, page_size=query.page_size)

    def route(self, user: Any, trip_id: int) -> Any:
        return {
            "tripId": trip_id,
            "points": [],
            "quality": {
                "pointCount": 0,
                "avgAccuracyM": None,
                "maxAccuracyM": None,
                "poorAccuracyCount": 0,
                "mockLocationCount": 0,
                "firstRecordedAt": None,
                "lastRecordedAt": None,
            },
        }

    def sync_status(self, user: Any, trip_id: int, query: TripSyncQuery) -> TripSyncStatus:
        self.sync_query = query
        empty = {
            "storedRecords": 0,
            "firstRecordedAt": None,
            "lastRecordedAt": None,
            "expectedRecords": None,
            "pendingRecords": None,
            "syncComplete": None,
        }
        return TripSyncStatus.model_validate(
            {
                "tripId": trip_id,
                "tripStatus": "Completed",
                "gpsSync": empty,
                "diagnosticsSync": empty,
                "overallSyncComplete": False,
            }
        )

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


def _diagnostic_event(**overrides: Any) -> dict[str, Any]:
    return {
        "eventId": str(uuid4()),
        "eventType": "LOCATION_CALLBACK_SILENCE",
        "recordedAt": "2026-11-03T11:33:37.000Z",
        "durationSeconds": 59.4,
        "gpsEnabled": True,
        "permissionGranted": True,
        "batteryExempted": False,
        "powerSaveMode": True,
        "deviceIdleMode": False,
        "networkConnected": True,
        "callState": "IDLE",
        "manufacturer": "Samsung",
        "details": "Location callback silence watchdog detected a gap",
        **overrides,
    }


def test_upload_gps_diagnostics(api: FastAPI, client: TestClient) -> None:
    _field_user(api)
    service = use_trip_service(api)
    response = client.post("/api/v1/trk/trips/5501/gps-diagnostics", json={"events": [_diagnostic_event()]})
    assert response.status_code == 200
    assert response.json() == {"accepted": 1, "duplicatesIgnored": 0}
    assert service.diagnostics[0][1] == 5501


def test_upload_gps_diagnostics_needs_manage_permission(api: FastAPI, client: TestClient) -> None:
    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset(), employee_id=5)
    use_trip_service(api)
    response = client.post("/api/v1/trk/trips/5501/gps-diagnostics", json={"events": [_diagnostic_event()]})
    assert response.status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        {"events": []},  # empty batch
        {"events": [_diagnostic_event(eventId="not-a-uuid")]},
        {"events": [_diagnostic_event(durationSeconds=-1)]},
        {"events": [_diagnostic_event(latitude=20.3)]},  # latitude without longitude
        {"events": [_diagnostic_event(latitude=91, longitude=85.8)]},
        {"events": [_diagnostic_event(unknownField=1)]},  # mass assignment
    ],
)
def test_upload_gps_diagnostics_validates_the_body(api: FastAPI, client: TestClient, body: dict[str, Any]) -> None:
    _field_user(api)
    use_trip_service(api)
    assert client.post("/api/v1/trk/trips/5501/gps-diagnostics", json=body).status_code == 422


def test_gps_diagnostics_accept_unknown_device_state_and_no_position(api: FastAPI, client: TestClient) -> None:
    _field_user(api)
    use_trip_service(api)
    event = {"eventId": str(uuid4()), "eventType": "GPS_DISABLED", "recordedAt": "2026-11-03T09:30:00Z"}
    assert client.post("/api/v1/trk/trips/5501/gps-diagnostics", json={"events": [event]}).status_code == 200


def test_engineer_can_read_trip_route(api: FastAPI, client: TestClient) -> None:
    _field_user(api)
    use_trip_service(api)
    response = client.get("/api/v1/trk/trips/5501/route")
    assert response.status_code == 200
    assert response.json()["quality"]["pointCount"] == 0


def test_trip_route_needs_a_trip_permission(api: FastAPI, client: TestClient) -> None:
    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset(), employee_id=5)
    use_trip_service(api)
    assert client.get("/api/v1/trk/trips/5501/route").status_code == 403


def test_engineer_can_list_gps_diagnostics(api: FastAPI, client: TestClient) -> None:
    _field_user(api)
    use_trip_service(api)
    assert client.get("/api/v1/trk/trips/5501/gps-diagnostics").status_code == 200


def test_sync_status_passes_the_devices_expected_counts(api: FastAPI, client: TestClient) -> None:
    _field_user(api)
    service = use_trip_service(api)
    response = client.get(
        "/api/v1/trk/trips/5501/sync/status", params={"expectedGpsRecords": 36500, "expectedDiagnosticRecords": 12}
    )
    assert response.status_code == 200
    assert response.json()["tripId"] == 5501
    assert (service.sync_query.expected_gps_records, service.sync_query.expected_diagnostic_records) == (36500, 12)


def test_sync_status_expected_counts_are_optional_but_not_negative(api: FastAPI, client: TestClient) -> None:
    _field_user(api)
    use_trip_service(api)
    assert client.get("/api/v1/trk/trips/5501/sync/status").status_code == 200
    assert client.get("/api/v1/trk/trips/5501/sync/status", params={"expectedGpsRecords": -1}).status_code == 422


def test_sync_status_needs_a_tracking_permission(api: FastAPI, client: TestClient) -> None:
    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset(), employee_id=5)
    use_trip_service(api)
    assert client.get("/api/v1/trk/trips/5501/sync/status").status_code == 403


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
        existing_event_ids: set[UUID] | None = None,
        fixes: list[Any] | None = None,
        branch_id: int | None = 1,
    ):
        self._by_uuid = by_uuid
        self._active = active
        self._trip = trip
        self._existing_times: set[datetime] = existing_times or set()
        self._existing_event_ids: set[UUID] = existing_event_ids or set()
        self._fixes: list[Any] = fixes or []
        self.flushed = False
        self._gps_stats: Any = (0, None, None)
        self._diagnostic_stats: Any = (0, None, None)
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

    def existing_diagnostic_ids(self, _trip_id: int, _ids: list[UUID]) -> set[UUID]:
        return set(self._existing_event_ids)

    def gps_fixes(self, _trip_id: int) -> list[Any]:
        return self._fixes

    def flush(self) -> None:
        self.flushed = True

    def gps_point_stats(self, _trip_id: int) -> Any:
        return self._gps_stats

    def diagnostic_stats(self, _trip_id: int) -> Any:
        return self._diagnostic_stats

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def adjustments_for_trip(self, _trip_id: int) -> list[Any]:
        return []

    def list(self, scope: RequestScope, query: TripListQuery) -> Page[TripListItem]:
        self.listed = (scope, query)
        return Page(items=[], total=0, page=query.page, page_size=query.page_size)


class _FakeMasterRepo:
    """The seeded master data of migration 0012; pass `active=` to deactivate or add values."""

    SEED: dict[str, list[str]] = {
        "TrackableActivityModule": ["SVC", "PRE"],
        "TrkTripTypeMaster": ["To site", "Return", "Site to site"],
        "TrkTripVehicleTypeMaster": [
            "Own bike",
            "Own car",
            "Company vehicle",
            "Public transport",
            "Bus",
            "Train",
            "Other",
        ],
        "TrkTripStatusMaster": ["In progress", "Completed", "Auto closed"],
        "TrkGpsDiagnosticEventType": ["LOCATION_CALLBACK_SILENCE", "GPS_DISABLED", "GPS_ENABLED"],
    }

    def __init__(self, active: dict[str, list[str]] | None = None, default_type: str | None = "To site") -> None:
        self._active = {**self.SEED, **(active or {})}
        self._default = default_type

    def active_codes(self, model: Any) -> list[str]:
        return list(self._active[model.__name__])

    def all_codes(self, model: Any) -> set[str]:
        return set(self.SEED[model.__name__]) | set(self._active[model.__name__])

    def default_trip_type(self) -> str | None:
        return self._default

    def vehicle_row(self, code: str) -> Any:
        return SimpleNamespace(code=code, is_gps_tracked=code not in ("Public transport", "Bus", "Train", "Other"))


def _service_with(repo: _FakeRepo, master: _FakeMasterRepo | None = None) -> TripService:
    service = TripService.__new__(TripService)
    service._db = SimpleNamespace(commit=lambda: None)  # type: ignore[assignment]
    service._repo = repo  # type: ignore[assignment]
    service._master = TripMasterService.__new__(TripMasterService)
    service._master._repo = master or _FakeMasterRepo()  # type: ignore[assignment]
    return service


def _existing_trip() -> Any:
    return SimpleNamespace(
        id=5501,
        trackable_activity_id=3301,
        employee_id=5,
        trip_type="To site",
        status="In progress",
        is_active=True,
        start_at=datetime(2026, 10, 28, 6, 35),
        start_latitude=20.2961,
        start_longitude=85.8245,
        end_at=None,
        end_latitude=None,
        end_longitude=None,
        gps_distance_km=None,
        map_distance_km=None,
        adjusted_distance_km=None,
        is_distance_adjusted=False,
        duration_minutes=None,
        row_version=b"\x00\x00\x00\x00\x00\x00\x07\xd1",
    )


def _start_input() -> StartTripInput:
    return StartTripInput.model_validate(
        {
            "clientUuid": str(uuid4()),
            "module": "SVC",
            "referenceId": 9001,
            "startLatitude": 20.2961,
            "startLongitude": 85.8245,
        }
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


@pytest.fixture
def new_trip_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let start() run past validation: stub the module handler and the response mapping."""
    monkeypatch.setattr(
        "trishul_api.modules.trk.service.handler_for",
        lambda _module: SimpleNamespace(resolve=lambda *_args: SimpleNamespace(id=3301)),
    )
    monkeypatch.setattr(TripService, "_to_out", lambda _self, trip, _activity=None: trip)


def test_start_uses_the_default_trip_type_when_none_is_sent(new_trip_path: None) -> None:
    repo = _FakeRepo()
    service = _service_with(repo)
    body = {
        "clientUuid": str(uuid4()),
        "module": "SVC",
        "referenceId": 9001,
        "startLatitude": 20.2961,
        "startLongitude": 85.8245,
    }
    service.start(make_user(employee_id=5), StartTripInput.model_validate(body))
    assert repo.added[0].trip_type == "To site"
    assert repo.added[0].status == "In progress"  # set by the application


@pytest.mark.parametrize(
    ("patch", "field"),
    [
        ({"module": "XYZ"}, "module"),
        ({"tripType": "Teleport"}, "tripType"),
        ({"vehicleType": "Jetpack"}, "vehicleType"),
    ],
)
def test_start_rejects_values_that_are_not_active_master_data(patch: dict[str, Any], field: str) -> None:
    repo = _FakeRepo()
    service = _service_with(repo)
    data = StartTripInput.model_validate({**_start_body(), **patch})
    with pytest.raises(InvalidMasterValue) as caught:
        service.start(make_user(employee_id=5), data)
    assert caught.value.status == 422
    assert field in (caught.value.errors or {})
    assert repo.added == []


def test_start_rejects_a_deactivated_vehicle_type() -> None:
    master = _FakeMasterRepo(active={"TrkTripVehicleTypeMaster": ["Own bike"]})
    service = _service_with(_FakeRepo(), master)
    data = StartTripInput.model_validate({**_start_body(), "vehicleType": "Own car"})
    with pytest.raises(InvalidMasterValue):
        service.start(make_user(employee_id=5), data)


def test_start_accepts_a_newly_added_vehicle_type_without_code_changes(new_trip_path: None) -> None:
    master = _FakeMasterRepo(active={"TrkTripVehicleTypeMaster": ["Own bike", "Auto rickshaw"]})
    repo = _FakeRepo()
    data = StartTripInput.model_validate({**_start_body(), "vehicleType": "Auto rickshaw"})
    _service_with(repo, master).start(make_user(employee_id=5), data)
    assert repo.added[0].vehicle_type == "Auto rickshaw"


def test_retry_after_a_value_is_deactivated_still_returns_the_trip() -> None:
    master = _FakeMasterRepo(active={"TrkTripVehicleTypeMaster": []})
    repo = _FakeRepo(by_uuid=_existing_trip())
    data = StartTripInput.model_validate({**_start_body(), "vehicleType": "Own bike"})
    out = _service_with(repo, master).start(make_user(employee_id=5), data)
    assert out.id == 5501 and repo.added == []


def test_start_without_a_configured_default_requires_a_trip_type() -> None:
    service = _service_with(_FakeRepo(), _FakeMasterRepo(default_type=None))
    body = {
        "clientUuid": str(uuid4()),
        "module": "SVC",
        "referenceId": 9001,
        "startLatitude": 20.2961,
        "startLongitude": 85.8245,
    }
    with pytest.raises(InvalidMasterValue) as caught:
        service.start(make_user(employee_id=5), StartTripInput.model_validate(body))
    assert "tripType" in (caught.value.errors or {})


def test_start_body_cannot_set_the_status() -> None:
    with pytest.raises(ValueError):
        StartTripInput.model_validate({**_start_body(), "status": "Completed"})


def test_status_filter_must_name_a_known_status() -> None:
    service = _service_with(_FakeRepo())
    with pytest.raises(InvalidMasterValue):
        service.my_trips(make_user(employee_id=5), MyTripListQuery(status=["Teleported"]))
    service.my_trips(make_user(employee_id=5), MyTripListQuery(status=["Completed"]))


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


def _gps_batch() -> GpsBatchInput:
    return GpsBatchInput.model_validate(
        {"points": [{"recordedAt": datetime(2026, 10, 28, 6, 36), "latitude": 20.1, "longitude": 85.1}]}
    )


def _ended_trip(ended_ago: timedelta) -> Any:
    trip = _existing_trip()
    trip.status = "Completed"
    trip.end_at = datetime.now(UTC).replace(tzinfo=None) - ended_ago
    trip.gps_distance_km = Decimal("1.00")
    return trip


def test_late_gps_points_are_accepted_after_the_stop_and_the_distance_is_recomputed() -> None:
    trip = _ended_trip(timedelta(hours=2))
    repo = _FakeRepo(
        trip=trip,
        fixes=[
            GpsFix(datetime(2026, 10, 28, 6, 36), 20.2961, 85.8245, accuracy_m=5.0),
            GpsFix(datetime(2026, 10, 28, 6, 46), 20.3961, 85.8245, accuracy_m=5.0),  # ~11 km north
        ],
    )
    result = _service_with(repo).upload_gps(make_user(employee_id=5), 5501, _gps_batch())
    assert result.accepted == 1
    assert repo.flushed  # the recompute reads the points added by this request
    assert Decimal("10") < trip.gps_distance_km < Decimal("12")
    assert trip.status == "Completed"


def test_late_gps_duplicates_do_not_touch_the_distance() -> None:
    trip = _ended_trip(timedelta(hours=2))
    repo = _FakeRepo(trip=trip, existing_times={datetime(2026, 10, 28, 6, 36)})
    result = _service_with(repo).upload_gps(make_user(employee_id=5), 5501, _gps_batch())
    assert (result.accepted, result.duplicates_ignored) == (0, 1)
    assert trip.gps_distance_km == Decimal("1.00")


def test_late_gps_points_keep_a_manual_adjustment() -> None:
    trip = _ended_trip(timedelta(hours=2))
    trip.adjusted_distance_km = Decimal("7.50")
    trip.is_distance_adjusted = True
    _service_with(_FakeRepo(trip=trip)).upload_gps(make_user(employee_id=5), 5501, _gps_batch())
    assert trip.adjusted_distance_km == Decimal("7.50")


def test_gps_points_are_rejected_after_the_grace_period() -> None:
    service = _service_with(_FakeRepo(trip=_ended_trip(timedelta(days=LATE_UPLOAD_GRACE_DAYS, hours=1))))
    with pytest.raises(ApiError):
        service.upload_gps(make_user(employee_id=5), 5501, _gps_batch())


# ---------------------------------------------------------------- sync status


def _sync(trip: Any, gps: Any = (0, None, None), diagnostics: Any = (0, None, None), **expected: int) -> Any:
    repo = _FakeRepo(trip=trip)
    repo._gps_stats, repo._diagnostic_stats = gps, diagnostics
    query = TripSyncQuery.model_validate(expected)
    return _service_with(repo).sync_status(make_user(employee_id=5), 5501, query)


_T0, _T1 = datetime(2026, 10, 28, 6, 36), datetime(2026, 10, 28, 8, 5)


def test_sync_complete_when_the_server_stored_everything_the_device_recorded() -> None:
    status = _sync(
        _ended_trip(timedelta(hours=1)),
        gps=(36500, _T0, _T1),
        diagnostics=(12, _T0, _T1),
        expectedGpsRecords=36500,
        expectedDiagnosticRecords=12,
    )
    assert status.gps_sync.sync_complete and status.gps_sync.pending_records == 0
    assert status.gps_sync.first_recorded_at == _T0.replace(tzinfo=UTC)  # served as UTC
    assert status.gps_sync.last_recorded_at == _T1.replace(tzinfo=UTC)
    assert status.diagnostics_sync.sync_complete
    assert status.overall_sync_complete


def test_sync_reports_pending_gps_points_and_is_not_complete() -> None:
    status = _sync(_ended_trip(timedelta(hours=1)), gps=(36000, _T0, _T1), expectedGpsRecords=36500)
    assert (status.gps_sync.stored_records, status.gps_sync.pending_records) == (36000, 500)
    assert status.gps_sync.sync_complete is False
    assert status.overall_sync_complete is False


def test_sync_is_not_overall_complete_while_the_trip_is_in_progress() -> None:
    status = _sync(_existing_trip(), gps=(10, _T0, _T1), expectedGpsRecords=10)
    assert status.gps_sync.sync_complete is True
    assert status.overall_sync_complete is False


def test_sync_without_expected_counts_proves_nothing() -> None:
    status = _sync(_ended_trip(timedelta(hours=1)), gps=(5, _T0, _T1))
    assert status.gps_sync.stored_records == 5
    assert status.gps_sync.expected_records is None and status.gps_sync.sync_complete is None
    assert status.overall_sync_complete is False


def test_sync_checks_only_the_kinds_the_device_sent_a_count_for() -> None:
    status = _sync(_ended_trip(timedelta(hours=1)), gps=(10, _T0, _T1), expectedGpsRecords=10)
    assert status.diagnostics_sync.sync_complete is None
    assert status.overall_sync_complete is True


def test_sync_cannot_read_another_engineers_trip() -> None:
    repo = _FakeRepo(trip=_existing_trip())
    with pytest.raises(NotFound):
        _service_with(repo).sync_status(make_user(employee_id=99), 5501, TripSyncQuery())


# ---------------------------------------------------------------- GPS diagnostics


def _diagnostic_batch(*events: dict[str, Any]) -> GpsDiagnosticBatchInput:
    return GpsDiagnosticBatchInput.model_validate({"events": list(events)})


def test_diagnostics_are_deduplicated_by_event_id_within_and_across_batches() -> None:
    stored, fresh = uuid4(), uuid4()
    repo = _FakeRepo(trip=_existing_trip(), existing_event_ids={stored})
    batch = _diagnostic_batch(
        _diagnostic_event(eventId=str(stored)),  # duplicate of stored
        _diagnostic_event(eventId=str(fresh)),  # new
        _diagnostic_event(eventId=str(fresh)),  # duplicate within batch
    )
    result = _service_with(repo).upload_gps_diagnostics(make_user(employee_id=5), 5501, batch)
    assert (result.accepted, result.duplicates_ignored) == (1, 2)
    assert len(repo.added) == 1
    row = repo.added[0]
    assert (row.trip_id, row.event_id, row.event_type) == (5501, fresh, "LOCATION_CALLBACK_SILENCE")
    assert row.recorded_at.tzinfo is None  # stored as naive UTC like every DATETIME2
    assert row.power_save_mode is True and row.manufacturer == "Samsung"


def test_diagnostics_keep_unknown_device_state_as_null() -> None:
    repo = _FakeRepo(trip=_existing_trip())
    event = {"eventId": str(uuid4()), "eventType": "GPS_DISABLED", "recordedAt": "2026-11-03T09:30:00Z"}
    _service_with(repo).upload_gps_diagnostics(make_user(employee_id=5), 5501, _diagnostic_batch(event))
    row = repo.added[0]
    assert row.gps_enabled is None and row.latitude is None and row.call_state is None


def test_diagnostics_reject_an_unknown_event_type() -> None:
    repo = _FakeRepo(trip=_existing_trip())
    service = _service_with(repo)
    with pytest.raises(InvalidMasterValue):
        service.upload_gps_diagnostics(
            make_user(employee_id=5), 5501, _diagnostic_batch(_diagnostic_event(eventType="TELEPORTED"))
        )
    assert repo.added == []


def test_diagnostics_accept_a_deactivated_event_type() -> None:
    master = _FakeMasterRepo(active={"TrkGpsDiagnosticEventType": ["GPS_ENABLED"]})  # silence deactivated
    repo = _FakeRepo(trip=_existing_trip())
    _service_with(repo, master).upload_gps_diagnostics(
        make_user(employee_id=5), 5501, _diagnostic_batch(_diagnostic_event())
    )
    assert len(repo.added) == 1


def test_diagnostics_are_accepted_after_the_trip_ended() -> None:
    repo = _FakeRepo(trip=_ended_trip(timedelta(hours=3)))
    result = _service_with(repo).upload_gps_diagnostics(
        make_user(employee_id=5), 5501, _diagnostic_batch(_diagnostic_event())
    )
    assert result.accepted == 1


def test_diagnostics_are_rejected_after_the_grace_period() -> None:
    service = _service_with(_FakeRepo(trip=_ended_trip(timedelta(days=LATE_UPLOAD_GRACE_DAYS + 1))))
    with pytest.raises(ApiError):
        service.upload_gps_diagnostics(make_user(employee_id=5), 5501, _diagnostic_batch(_diagnostic_event()))


def test_diagnostics_cannot_be_added_to_another_engineers_trip() -> None:
    service = _service_with(_FakeRepo(trip=_existing_trip()))
    with pytest.raises(NotFound):
        service.upload_gps_diagnostics(make_user(employee_id=99), 5501, _diagnostic_batch(_diagnostic_event()))


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


# ---------------------------------------------------------------- master data


class _MasterRows:
    """Rows as the master repository returns them (ORM objects with these attributes)."""

    @staticmethod
    def base(code: str, **extra: Any) -> SimpleNamespace:
        return SimpleNamespace(
            code=code,
            name=code,
            description=None,
            sort_order=1,
            is_active=True,
            **({"is_gps_tracked": True} if code in ("Own bike",) else {}),
            **extra,
        )


def _master_service(repo_rows: dict[str, list[SimpleNamespace]]) -> TripMasterService:
    class Repo:
        calls: list[bool] = []

        def rows(self, model: Any, include_inactive: bool = False) -> list[SimpleNamespace]:
            self.calls.append(include_inactive)
            return repo_rows[model.__name__]

    service = TripMasterService.__new__(TripMasterService)
    service._repo = Repo()  # type: ignore[assignment]
    return service


def _rows() -> dict[str, list[SimpleNamespace]]:
    b = _MasterRows.base
    return {
        "TrackableActivityModule": [b("SVC", source_schema="svc", source_table="service_visit")],
        "TrkTripTypeMaster": [b("To site", is_default=True)],
        "TrkTripVehicleTypeMaster": [b("Own bike")],
        "TrkTripStatusMaster": [b("In progress", is_initial=True, is_final=False)],
    }


def test_master_data_is_open_to_any_signed_in_user(api: FastAPI, client: TestClient) -> None:
    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset())
    api.dependency_overrides[get_trip_master_service] = lambda: _master_service(_rows())
    response = client.get("/api/v1/trk/master-data")
    assert response.status_code == 200
    body = response.json()
    assert body["moduleCodes"][0] == {
        "code": "SVC",
        "name": "SVC",
        "description": None,
        "sortOrder": 1,
        "isActive": True,
        "sourceSchema": "svc",
        "sourceTable": "service_visit",
    }
    assert body["tripTypes"][0]["isDefault"] is True
    assert body["tripStatuses"][0]["isInitial"] is True
    assert body["vehicleTypes"][0]["code"] == "Own bike"


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ("module-codes", "SVC"),
        ("trip-types", "To site"),
        ("vehicle-types", "Own bike"),
        ("trip-statuses", "In progress"),
    ],
)
def test_each_master_list_endpoint(api: FastAPI, client: TestClient, path: str, code: str) -> None:
    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset())
    api.dependency_overrides[get_trip_master_service] = lambda: _master_service(_rows())
    response = client.get(f"/api/v1/trk/{path}")
    assert response.status_code == 200
    assert response.json()[0]["code"] == code


def test_inactive_master_data_is_for_reviewers_only(api: FastAPI, client: TestClient) -> None:
    api.dependency_overrides[get_trip_master_service] = lambda: _master_service(_rows())
    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset({"trk.trip.manage"}))
    assert client.get("/api/v1/trk/trip-types?includeInactive=true").status_code == 403
    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset({"trk.trip.view.team"}))
    assert client.get("/api/v1/trk/trip-types?includeInactive=true").status_code == 200


# ---------------------------------------------------------------- trip start side effects


def test_site_coordinates_fall_back_in_order() -> None:
    from trishul_api.modules.trk.handlers import _site_coordinates

    sites = {
        1: SimpleNamespace(latitude=None, longitude=None),  # call's site, no coordinates yet
        2: SimpleNamespace(latitude=Decimal("20.1"), longitude=Decimal("85.1")),  # machine's site
    }
    default = SimpleNamespace(latitude=Decimal("19.9"), longitude=Decimal("84.9"))

    class Session:
        def get(self, _model: Any, site_id: int) -> Any:
            return sites.get(site_id)

        def scalars(self, _statement: Any) -> Any:
            return SimpleNamespace(first=lambda: default)

    assert _site_coordinates(Session(), [1, 2], 5) == (20.1, 85.1)  # skips the site without coordinates
    assert _site_coordinates(Session(), [None, None], 5) == (19.9, 84.9)  # customer's default site
    assert _site_coordinates(Session(), [1], None) == (None, None)  # nothing known


@pytest.mark.parametrize(
    ("header", "agent", "expected"),
    [
        ("android", None, "Android"),  # an explicit header wins
        ("web", "okhttp/4.12.0", "Web"),
        (None, "okhttp/4.12.0", "Android"),
        (None, "Dart/3.4 (dart:io)", "Android"),
        (None, "MyApp/1.0 CFNetwork/1494 Darwin/23.4", "iOS"),
        (None, "Mozilla/5.0 (Linux; Android 14) Chrome/124", "Web"),  # a phone browser is still web
        (None, None, "Web"),
    ],
)
def test_audit_source_is_inferred_for_mobile_clients(header: str | None, agent: str | None, expected: str) -> None:
    from trishul_api.auth.deps import _audit_source

    assert _audit_source(header, agent) == expected


@pytest.mark.parametrize("vehicle", ["Public transport", "Bus", "Train", "Other"])
def test_start_rejects_vehicles_without_gps_tracking(vehicle: str) -> None:
    service = _service_with(_FakeRepo())
    data = StartTripInput.model_validate({**_start_body(), "vehicleType": vehicle})
    with pytest.raises(InvalidMasterValue) as error:
        service.start(make_user(permissions=frozenset({"trk.trip.manage"}), employee_id=5), data)
    assert "manual travel" in error.value.errors["vehicleType"][0]


def test_manual_travel_accepts_only_non_gps_vehicles() -> None:
    master = TripMasterService.__new__(TripMasterService)
    master._repo = _FakeMasterRepo()  # type: ignore[assignment]
    assert master.manual_vehicle_problem("Bus") is None
    assert master.manual_vehicle_problem("Train") is None
    assert master.manual_vehicle_problem("Other") is None
    assert "GPS" in (master.manual_vehicle_problem("Own bike") or "")
    assert "not an active" in (master.manual_vehicle_problem("Jetpack") or "")
