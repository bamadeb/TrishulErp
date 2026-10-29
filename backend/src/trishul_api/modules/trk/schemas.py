from uuid import UUID

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models import TrackableActivityModuleCode, TrkTripStatus, TrkTripType, TrkTripVehicleType

ModuleCode = TrackableActivityModuleCode
TripType = TrkTripType
TripStatus = TrkTripStatus
VehicleType = TrkTripVehicleType

_LAT = Field(ge=-90, le=90)
_LON = Field(ge=-180, le=180)


class StartTripInput(InputModel):
    """Start a trip for a business activity. `module` + `referenceId` name the activity in its own
    module (SVC -> service_call id, PRE -> sales_activity id); the trk engine registers it and links
    the trip. `clientUuid` makes a retried start return the same trip instead of a second one."""

    client_uuid: UUID
    module: ModuleCode
    reference_id: int = Field(gt=0)
    trip_type: TripType = "To site"
    start_latitude: float = _LAT
    start_longitude: float = _LON
    started_at: UtcDateTime | None = None
    vehicle_type: VehicleType | None = None
    device_id: str | None = Field(None, max_length=100)


class GpsPointInput(InputModel):
    recorded_at: UtcDateTime
    latitude: float = _LAT
    longitude: float = _LON
    accuracy_m: float | None = Field(None, ge=0)
    speed_kmph: float | None = Field(None, ge=0)
    battery_pct: int | None = Field(None, ge=0, le=100)
    is_mock_location: bool = False


class GpsBatchInput(InputModel):
    points: list[GpsPointInput] = Field(min_length=1, max_length=500)


class StopTripInput(InputModel):
    end_latitude: float = _LAT
    end_longitude: float = _LON
    ended_at: UtcDateTime | None = None


class TripOut(ApiModel):
    id: int
    trackable_activity_id: int
    employee_id: int
    module: ModuleCode
    reference_id: int
    trip_type: TripType
    status: TripStatus
    start_at: UtcDateTime
    start_latitude: float
    start_longitude: float
    end_at: UtcDateTime | None
    end_latitude: float | None
    end_longitude: float | None
    gps_distance_km: float | None
    duration_minutes: int | None
    row_version: RowVersion


class GpsUploadResult(ApiModel):
    accepted: int
    duplicates_ignored: int
    trip_status: TripStatus


class TripListQuery(PageQuery):
    employee_id: int | None = Field(None, gt=0)
    status: list[TripStatus] = Field(default_factory=list)


class TripListItem(ApiModel):
    id: int
    employee_id: int
    employee_name: str | None
    module: ModuleCode
    activity_title: str | None
    trip_type: TripType
    status: TripStatus
    start_at: UtcDateTime
    end_at: UtcDateTime | None
    gps_distance_km: float | None
    duration_minutes: int | None
