from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field, StrictFloat, StrictInt, StrictStr, model_validator

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


class GpsDiagnosticEventInput(InputModel):
    """One diagnostic event recorded by the app while tracking. `eventId` is generated on the device,
    so a retried batch is deduplicated. Device-state flags are nullable: null means the device could not
    tell, which is not the same as false. The position is optional (there may be no fix)."""

    event_id: UUID
    event_type: str = Field(
        min_length=1, max_length=40, description="An event type code, e.g. LOCATION_CALLBACK_SILENCE."
    )
    recorded_at: UtcDateTime
    duration_seconds: float | None = Field(None, ge=0, lt=10_000_000)
    gps_enabled: bool | None = None
    permission_granted: bool | None = None
    battery_exempted: bool | None = None
    power_save_mode: bool | None = None
    device_idle_mode: bool | None = None
    network_connected: bool | None = None
    call_state: str | None = Field(None, max_length=20)
    manufacturer: str | None = Field(None, max_length=60)
    model: str | None = Field(None, max_length=100)
    os_name: str | None = Field(None, max_length=20, description="Android or iOS.")
    os_version: str | None = Field(None, max_length=30)
    details: str | None = Field(None, max_length=500)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    accuracy_m: float | None = Field(None, ge=0, le=99_999.9)

    @model_validator(mode="after")
    def _position_is_complete(self) -> "GpsDiagnosticEventInput":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be sent together or not at all.")
        return self


class GpsDiagnosticBatchInput(InputModel):
    events: list[GpsDiagnosticEventInput] = Field(min_length=1, max_length=500)


class GpsDiagnosticUploadResult(ApiModel):
    accepted: int
    duplicates_ignored: int


class GpsDiagnosticItem(ApiModel):
    id: int
    event_id: UUID
    event_type: str
    recorded_at: UtcDateTime
    duration_seconds: float | None
    gps_enabled: bool | None
    permission_granted: bool | None
    battery_exempted: bool | None
    power_save_mode: bool | None
    device_idle_mode: bool | None
    network_connected: bool | None
    call_state: str | None
    manufacturer: str | None
    model: str | None
    os_name: str | None
    os_version: str | None
    details: str | None
    latitude: float | None
    longitude: float | None
    accuracy_m: float | None
    received_at: UtcDateTime


class TripSyncQuery(ApiModel):
    """What the device believes it has recorded. The server cannot know how many points the phone
    captured, so the app sends its own counts and the server compares them with what it stored."""

    expected_gps_records: int | None = Field(None, ge=0, description="GPS points the device recorded.")
    expected_diagnostic_records: int | None = Field(None, ge=0, description="Diagnostic events the device recorded.")


class SyncSection(ApiModel):
    """Stored (unique, persisted) records of one kind. `expectedRecords`, `pendingRecords` and
    `syncComplete` are null when the device sent no expected count for this kind."""

    stored_records: int
    first_recorded_at: UtcDateTime | None
    last_recorded_at: UtcDateTime | None
    expected_records: int | None
    pending_records: int | None
    sync_complete: bool | None


class TripSyncStatus(ApiModel):
    trip_id: int
    trip_status: TripStatus
    gps_sync: SyncSection
    diagnostics_sync: SyncSection
    overall_sync_complete: bool = Field(
        description="True only when the trip has ended, at least one expected count was sent, and every "
        "count that was sent is met by the stored records."
    )


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
    last_latitude: float | None = Field(None, description="Latest recorded GPS fix of the trip, if any.")
    last_longitude: float | None = None
    last_gps_at: UtcDateTime | None = None
    start_battery_pct: int | None = Field(None, description="Phone battery on the first GPS fix of the trip.")
    end_battery_pct: int | None = Field(
        None, description="Phone battery on the latest GPS fix (final one once stopped)."
    )
    device_manufacturer: str | None = None
    device_model: str | None = None
    device_platform: str | None = None
    device_os_version: str | None = None
    device_app_version: str | None = None
    row_version: RowVersion


class RoutePoint(ApiModel):
    recorded_at: UtcDateTime
    latitude: float
    longitude: float
    accuracy_m: float | None
    is_mock_location: bool


class GpsQuality(ApiModel):
    """Quality of the whole GPS trail (never of the thinned-out points returned for drawing)."""

    point_count: int
    avg_accuracy_m: float | None
    max_accuracy_m: float | None
    poor_accuracy_count: int = Field(description="Points less accurate than 50 m.")
    mock_location_count: int = Field(description="Points flagged as fake GPS.")
    first_recorded_at: UtcDateTime | None
    last_recorded_at: UtcDateTime | None


class TripRoute(ApiModel):
    """The GPS trail of a trip for drawing a map, plus quality figures of the full trail."""

    trip_id: int
    points: list[RoutePoint] = Field(description="Oldest first; thinned to at most 1000 points.")
    quality: GpsQuality


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
    is_gps_tracked: bool = Field(
        description="True: Start/Stop GPS trip. False (Bus, Train, Other): enter the kilometres by hand "
        "(POST /trk/manual-travel); there is no Start/Stop trip."
    )


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


_MANUAL_KM = Field(
    gt=0, le=Decimal("5000"), max_digits=8, decimal_places=2, description="Total distance travelled, km."
)


class ManualTravelUpdate(InputModel):
    """Correct a manual travel entry. The service call and the engineer never change."""

    vehicle_type: VehicleType = Field(description="A vehicle code with isGpsTracked = false (Bus, Train, Other).")
    travel_date: date
    distance_km: Decimal = _MANUAL_KM
    notes: str | None = Field(None, max_length=500, description="Travel notes / description.")


class ManualTravelInput(ManualTravelUpdate):
    """Record travel by a vehicle that has no GPS trip. Attach tickets with POST /documents
    (entityType 'trk.manual_travel') using the returned id. `clientUuid` makes a retried save return the
    same entry instead of a second one."""

    client_uuid: UUID | None = None
    service_call_id: int = Field(gt=0)


class ManualTravelOut(ApiModel):
    id: int
    service_call_id: int
    employee_id: int
    employee_name: str | None
    vehicle_type: VehicleType
    travel_date: date
    distance_km: Decimal
    notes: str | None
    document_count: int
    can_edit: bool = Field(description="The signed-in user recorded this entry and may correct or remove it.")
    created_at: UtcDateTime
    row_version: RowVersion


class TrackingConfigOut(ApiModel):
    """What the mobile app applies. A null value is "to be calibrated": keep the app's own behaviour for it.
    `version` changes whenever any value changes; send it back as If-None-Match to get 304 when nothing did."""

    moving_interval_ms: int = Field(description="Location interval while moving, ms.")
    moving_priority: str = Field(description="Android fused-location priority while moving.")
    stationary_candidate_duration_ms: int = Field(description="Time inside the dwell radius before stationary, ms.")
    stationary_dwell_radius_meters: float = Field(description="Dwell radius, m.")
    movement_recovery_displacement_meters: float = Field(description="Displacement that ends a stationary period, m.")
    variance_threshold_moving: float | None = Field(description="Null until calibrated.")
    variance_threshold_stationary: float | None = Field(description="Null until calibrated.")
    sampling_period_us: int | None = Field(
        description="Motion-sensor sampling period, microseconds. Null until calibrated."
    )
    calibration_pending: list[str] = Field(
        description="Keys that are still null because they are not calibrated yet."
    )
    version: str


class TrackingConfigParameter(ApiModel):
    """One parameter with the rules its value must follow (for the administration screen)."""

    code: str
    name: str
    description: str | None
    value_type: str = Field(description="int, decimal or string.")
    value: str | None = Field(description="Current value as text; null = to be calibrated.")
    default_value: str | None
    unit: str | None
    min_value: float | None
    max_value: float | None
    allowed_values: list[str] | None
    is_calibrated: bool
    updated_at: UtcDateTime | None
    row_version: RowVersion


class TrackingConfigUpdate(InputModel):
    """Set one parameter. A number for int / decimal parameters, text for string ones. null clears a parameter
    that is "to be calibrated" (one with no default); parameters with a default cannot be cleared."""

    value: StrictInt | StrictFloat | StrictStr | None
