"""GPS upload dedup at the column's precision (trace a805718a50034124b28400fb7685479b, trip 301, 2026-11-23).

recorded_at was DATETIME2(0): SQL Server rounded the phone's millisecond capture time to the second, while
the upload's dedup compared milliseconds. A resent batch then inserted rows the unique index
(trip_id, recorded_at) already held -> IntegrityError -> HTTP 500 on every retry, and two points less than
a second apart failed the same way. Migration 0047 stores milliseconds; existing whole-second rows still
match a resent point once.

The fake below behaves like the table: it keeps what was committed and refuses a duplicate key, as the
unique index does, so these tests fail the way production failed if the dedup is wrong.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from trishul_api.db.models import TrkTripGpsPoint
from trishul_api.modules.trk.schemas import GpsBatchInput
from trishul_api.modules.trk.service import _to_stored_ms, _to_whole_second

from .conftest import make_user
from .test_trk_api import _existing_trip, _FakeRepo, _service_with

T0 = datetime(2026, 11, 21, 15, 1, 56, 902000)  # the first point of the failing batch


class _UniqueIndexViolation(Exception):
    pass


class _TableRepo(_FakeRepo):
    """existing_gps_times answers only for the times asked (like the SQL IN), and commit enforces the
    unique index on (trip_id, recorded_at)."""

    def __init__(self, stored: set[datetime] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.stored: set[datetime] = set(stored or set())

    def existing_gps_times(self, _trip_id: int, times: list[Any]) -> set[datetime]:
        return {t for t in times if t in self.stored}

    def commit(self) -> None:
        for obj in self.added:
            if isinstance(obj, TrkTripGpsPoint):
                if obj.recorded_at in self.stored:
                    raise _UniqueIndexViolation(f"duplicate key (trip, {obj.recorded_at})")
                self.stored.add(obj.recorded_at)
        self.added.clear()


def _service(repo: _TableRepo) -> Any:
    service = _service_with(repo)
    service._db.commit = repo.commit  # type: ignore[method-assign]
    return service


def _batch(*times: datetime) -> GpsBatchInput:
    return GpsBatchInput.model_validate(
        {
            "points": [
                {
                    "recordedAt": t.replace(tzinfo=UTC).isoformat(),
                    "latitude": 20.3625 + i / 100000,
                    "longitude": 85.8170,
                    "accuracyM": 12.0,
                }
                for i, t in enumerate(times)
            ]
        }
    )


def _upload(repo: _TableRepo, *times: datetime, trip: Any = None) -> Any:
    repo._trip = trip or repo._trip or _existing_trip()
    return _service(repo).upload_gps(make_user(employee_id=5), 5501, _batch(*times))


# --- rounding helpers ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "ms", "second"),
    [
        (T0, datetime(2026, 11, 21, 15, 1, 56, 902000), datetime(2026, 11, 21, 15, 1, 57)),
        (datetime(2026, 1, 1, 0, 0, 0, 499999), datetime(2026, 1, 1, 0, 0, 0, 500000), datetime(2026, 1, 1)),
        (datetime(2026, 1, 1, 0, 0, 0, 500000), datetime(2026, 1, 1, 0, 0, 0, 500000), datetime(2026, 1, 1, 0, 0, 1)),
        (datetime(2026, 1, 1, 0, 0, 59, 999600), datetime(2026, 1, 1, 0, 1), datetime(2026, 1, 1, 0, 1)),
    ],
)
def test_times_are_rounded_like_sql_server(value: datetime, ms: datetime, second: datetime) -> None:
    assert _to_stored_ms(value) == ms
    assert _to_whole_second(value) == second


# --- the reported failure: resending points already stored at whole seconds -----------------------


def test_resending_points_stored_as_whole_seconds_is_not_a_500_and_adds_nothing() -> None:
    sent = [T0 + timedelta(seconds=7 * i, milliseconds=293 * i) for i in range(10)]
    repo = _TableRepo(stored={_to_whole_second(t) for t in sent})  # what DATETIME2(0) kept on 21 Nov

    result = _upload(repo, *sent)
    assert (result.accepted, result.duplicates_ignored) == (0, 10)
    assert len(repo.stored) == 10  # nothing stored twice


def test_offline_sync_after_a_partial_upload_adds_only_the_missing_points() -> None:
    # 327 of the trip's points reached the server before the response was lost; the phone resends all.
    sent = [T0 + timedelta(seconds=3 * i, milliseconds=137 * (i % 7)) for i in range(40)]  # 3 s apart, as in the log
    repo = _TableRepo(stored={_to_whole_second(t) for t in sent[:15]})
    first = _upload(repo, *sent)
    assert (first.accepted, first.duplicates_ignored) == (25, 15)
    again = _upload(repo, *sent)  # the next retry after a timeout
    assert (again.accepted, again.duplicates_ignored) == (0, 40)
    assert len(repo.stored) == 40  # the phone's 40 points, each stored once: sync status can complete


def test_a_whole_second_row_matches_one_resent_point_only() -> None:
    # Two real points in the same second can't both be an old row (that insert used to fail): the first
    # matches it, the second is a new point.
    a, b = T0, T0 + timedelta(milliseconds=398)  # 56.902 and 57.300, both 15:01:57 when rounded
    repo = _TableRepo(stored={_to_whole_second(a)})
    result = _upload(repo, a, b)
    assert (result.accepted, result.duplicates_ignored) == (1, 1)
    assert _to_stored_ms(b) in repo.stored


# --- millisecond points from now on ---------------------------------------------------------------


def test_points_less_than_a_second_apart_are_all_kept() -> None:
    times = [datetime(2026, 11, 25, 10, 0, 0, 510000), datetime(2026, 11, 25, 10, 0, 1, 490000)]
    repo = _TableRepo()
    result = _upload(repo, *times)  # both used to round to 10:00:01 and fail the whole batch
    assert (result.accepted, result.duplicates_ignored) == (2, 0)
    assert repo.stored == {_to_stored_ms(t) for t in times}


def test_a_retried_millisecond_batch_and_a_repeated_point_are_ignored() -> None:
    times = [datetime(2026, 11, 25, 10, 0, 0, 120000) + timedelta(seconds=i) for i in range(5)]
    repo = _TableRepo()
    assert _upload(repo, *times, times[2]).duplicates_ignored == 1  # same point twice in one batch
    assert _upload(repo, *times).accepted == 0  # the whole batch again (lost response)
    assert len(repo.stored) == 5


def test_microseconds_from_the_phone_do_not_create_a_second_row() -> None:
    t = datetime(2026, 11, 25, 10, 0, 0, 123400)
    repo = _TableRepo()
    _upload(repo, t)
    assert _upload(repo, datetime(2026, 11, 25, 10, 0, 0, 123499)).accepted == 0  # same stored millisecond


# --- offline end, then sync -------------------------------------------------------------------------


def test_points_upload_while_the_server_still_has_the_trip_in_progress() -> None:
    # Ended offline: the phone sends the points before the stop reaches the server.
    trip = _existing_trip()
    assert trip.status == "In progress"
    repo = _TableRepo()
    result = _upload(repo, T0, T0 + timedelta(seconds=3), trip=trip)
    assert result.accepted == 2 and result.trip_status == "In progress"


def test_points_arriving_after_the_stop_are_accepted_and_the_distance_refreshed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trip = _existing_trip()
    trip.status, trip.end_at = "Completed", datetime(2026, 11, 21, 15, 30)
    trip.end_latitude, trip.end_longitude = Decimal("20.35"), Decimal("85.81")
    repo = _TableRepo()
    refreshed: list[int] = []
    monkeypatch.setattr(type(_service_with(repo)), "_refresh_gps_distance", lambda self, t, uid: refreshed.append(t.id))
    service = _service(repo)
    repo._trip = trip
    result = service.upload_gps(make_user(employee_id=5), 5501, _batch(T0, T0 + timedelta(seconds=3)))
    assert result.accepted == 2 and result.trip_status == "Completed" and refreshed == [5501]
