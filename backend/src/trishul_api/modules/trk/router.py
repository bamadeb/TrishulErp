from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, ScopeDep, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.modules.trk.schemas import (
    AdjustDistanceInput,
    GpsBatchInput,
    GpsUploadResult,
    MyTripListQuery,
    StartTripInput,
    StopTripInput,
    TripAdjustmentItem,
    TripListItem,
    TripListQuery,
    TripOut,
)
from trishul_api.modules.trk.service import TripService

router = APIRouter(prefix="/trk", tags=["tracking"])

TripId = Annotated[int, Path(alias="tripId", gt=0)]


def get_trip_service(db: DbSession) -> TripService:
    return TripService(db)


TripServiceDep = Annotated[TripService, Depends(get_trip_service)]


@router.post(
    "/trips",
    summary="Start a trip for a service call or pre-sales activity",
    status_code=201,
    dependencies=[Depends(require_permission("trk.trip.manage"))],
)
def create_trip(data: StartTripInput, user: CurrentUserDep, service: TripServiceDep, response: Response) -> TripOut:
    trip = service.start(user, data)
    # A retried start (same clientUuid) returns the existing trip, so it is not a fresh 201.
    response.status_code = 200 if trip.status != "In progress" or trip.end_at else 201
    return trip


@router.post(
    "/trips/{tripId}/gps-points",
    summary="Upload a batch of GPS points for a trip (offline-tolerant, deduplicated)",
    responses=NOT_FOUND_RESPONSE,
    dependencies=[Depends(require_permission("trk.trip.manage"))],
)
def upload_trip_gps_points(
    trip_id: TripId, data: GpsBatchInput, user: CurrentUserDep, service: TripServiceDep
) -> GpsUploadResult:
    return service.upload_gps(user, trip_id, data)


@router.post(
    "/trips/{tripId}/stop",
    summary="Stop a trip on arrival and record the end point",
    responses=NOT_FOUND_RESPONSE,
    dependencies=[Depends(require_permission("trk.trip.manage"))],
)
def stop_trip(trip_id: TripId, data: StopTripInput, user: CurrentUserDep, service: TripServiceDep) -> TripOut:
    return service.stop(user, trip_id, data)


# Declared before /trips/{tripId}, which would otherwise capture "mine".
@router.get(
    "/trips/mine",
    summary="My own trips (the engineer's trip history)",
    dependencies=[Depends(require_permission("trk.trip.manage"))],
)
def list_my_trips(
    query: Annotated[MyTripListQuery, Query()], user: CurrentUserDep, service: TripServiceDep
) -> Page[TripListItem]:
    return service.my_trips(user, query)


@router.get(
    "/trips/{tripId}",
    summary="One trip (to resume an interrupted trip)",
    responses=NOT_FOUND_RESPONSE,
    dependencies=[Depends(require_permission("trk.trip.manage"))],
)
def get_trip(trip_id: TripId, user: CurrentUserDep, service: TripServiceDep) -> TripOut:
    return service.get(user, trip_id)


@router.get(
    "/trips",
    summary="Review trips of the team / branch",
    dependencies=[Depends(require_permission("trk.trip.view.team"))],
)
def list_trips(
    query: Annotated[TripListQuery, Query()], scope: ScopeDep, service: TripServiceDep
) -> Page[TripListItem]:
    return service.review(scope, query)


@router.post(
    "/trips/{tripId}/adjust-distance",
    summary="Manually adjust a trip's distance (Team Lead), keeping the GPS value for audit",
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
    dependencies=[Depends(require_permission("trk.trip.adjust"))],
)
def adjust_trip_distance(
    trip_id: TripId,
    data: AdjustDistanceInput,
    user: CurrentUserDep,
    service: TripServiceDep,
    if_match: Annotated[bytes, Depends(if_match_row_version)],
) -> TripOut:
    return service.adjust_distance(user, trip_id, if_match, data)


@router.get(
    "/trips/{tripId}/adjustments",
    summary="Audit trail of a trip's manual distance adjustments (engineers: own trips only)",
    responses=NOT_FOUND_RESPONSE,
    dependencies=[Depends(require_permission("trk.trip.view.team", "trk.trip.adjust", "trk.trip.manage"))],
)
def list_trip_adjustments(trip_id: TripId, user: CurrentUserDep, service: TripServiceDep) -> list[TripAdjustmentItem]:
    return service.adjustments(user, trip_id)
