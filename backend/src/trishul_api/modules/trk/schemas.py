from decimal import Decimal
from uuid import UUID

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime

# trk.trip.(gps|map|adjusted)_distance_km is DECIMAL(8,2): up to 999999.99 km.
_DISTANCE_KM = Field(ge=0, le=Decimal("999999.99"), max_digits=8, decimal_places=2)

# These four are master data (trk.trackable_activity_module, trip_type, trip_vehicle_type, trip_status),
# not enums: the allowed values are read from the database, so the types are plain strings. Requests
# are validated against the active master rows in the service; GET /trk/master-data lists them.
ModuleCode = str
TripType = str
TripStatus = str
VehicleType = str

_LAT = Field(ge=-90, le=90)
_LON = Field(ge=-180, le=180)


class StartTripInput(InputModel):
    """Start a trip for a business activity. `module` + `referenceId` name the activity in its own
    module (SVC -> service_call id, PRE -> sales_activity id); the trk engine registers it and links
    the trip. `clientUuid` makes a retried start return the same trip instead of a second one."""

    client_uuid: UUID
    module: ModuleCode = Field(description="A module code from GET /trk/module-codes, e.g. SVC or PRE.")
    reference_id: int = Field(gt=0)
    trip_type: TripType | None = Field(
        None, description="A trip type code from GET /trk/trip-types; omitted means the default ('To site')."
    )
    start_latitude: float = _LAT
    start_longitude: float = _LON
    started_at: UtcDateTime | None = None
    vehicle_type: VehicleType | None = Field(None, description="A vehicle code from GET /trk/vehicle-types.")
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
    adjusted_distance_km: float | None
    is_distance_adjusted: bool
    effective_distance_km: float | None
    duration_minutes: int | None
    row_version: RowVersion


class GpsUploadResult(ApiModel):
    accepted: int
    duplicates_ignored: int
    trip_status: TripStatus


class MyTripListQuery(PageQuery):
    """Filters for an engineer's own trip list; the employee is always the caller."""

    status: list[TripStatus] = Field(default_factory=list)


class TripListQuery(MyTripListQuery):
    employee_id: int | None = Field(None, gt=0)


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
    adjusted_distance_km: float | None
    is_distance_adjusted: bool
    effective_distance_km: float | None
    duration_minutes: int | None


class AdjustDistanceInput(InputModel):
    """A Team Lead overrides a trip's distance where GPS is unreliable. The original GPS value is
    kept; this value becomes the effective distance and the change is logged for audit."""

    new_distance_km: Decimal = _DISTANCE_KM
    reason: str = Field(min_length=3, max_length=500)


class TripAdjustmentItem(ApiModel):
    """One entry in a trip's manual-adjustment audit trail."""

    id: int
    trip_id: int
    previous_distance_km: float | None
    new_distance_km: float
    gps_distance_km_at_adjustment: float | None
    reason: str
    adjusted_by_user_id: int
    adjusted_by_name: str | None
    adjusted_at: UtcDateTime


class CallTripHistoryItem(ApiModel):
    """A trip in a service call's history, with both the GPS and the effective (possibly adjusted)
    distance so the dashboard can show what was changed."""

    id: int
    visit_no: int
    trip_type: TripType
    status: TripStatus
    engineer_employee_id: int
    engineer_name: str | None
    start_at: UtcDateTime
    end_at: UtcDateTime | None
    duration_minutes: int | None
    start_latitude: float
    start_longitude: float
    end_latitude: float | None
    end_longitude: float | None
    gps_distance_km: float | None
    map_distance_km: float | None
    adjusted_distance_km: float | None
    is_distance_adjusted: bool
    effective_distance_km: float | None
    adjustment_count: int
    row_version: RowVersion


class MasterItem(ApiModel):
    """A master-data value. `code` is what trips store and the API accepts; it never changes. `name`
    is the display label."""

    code: str
    name: str
    description: str | None
    sort_order: int
    is_active: bool


class ModuleCodeItem(MasterItem):
    source_schema: str
    source_table: str


class TripTypeItem(MasterItem):
    is_default: bool


class VehicleTypeItem(MasterItem):
    pass


class TripStatusItem(MasterItem):
    """Statuses are set by the application, never by clients."""

    is_initial: bool
    is_final: bool


class TripMasterData(ApiModel):
    """All trip-tracking master lists in one call (for the mobile app and the review screens)."""

    module_codes: list[ModuleCodeItem]
    trip_types: list[TripTypeItem]
    vehicle_types: list[VehicleTypeItem]
    trip_statuses: list[TripStatusItem]
