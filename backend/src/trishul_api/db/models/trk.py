# Hand-written (not produced by scripts/generate_models.py): the trk schema was added by migration
# 0006 and these mirror its DDL. Re-run the generator against the migrated DB to fold this into
# generated/ and then delete this file. Keep the columns in sync with migration 0006 until then.

"""ORM models for the trk schema (common, cross-module trip tracking): 9 tables."""

import datetime as dt
import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from trishul_api.db.models.base import Audited, Base


class _TrkMaster:
    """Columns shared by the trk master tables. `code` is the value stored on trips and sent over the
    API, so it never changes; `name` is the editable display label. is_system rows are used by
    application logic and must stay active."""

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    code: Mapped[str] = mapped_column(sa.NVARCHAR(30), doc="Stable value stored on trips")
    name: Mapped[str] = mapped_column(sa.NVARCHAR(60), doc="Display name")
    description: Mapped[str | None] = mapped_column(sa.NVARCHAR(200), doc="Description")
    sort_order: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.FetchedValue(), doc="Display order")
    is_system: Mapped[bool] = mapped_column(
        sa.Boolean(), server_default=sa.FetchedValue(), doc="Used by application logic; cannot be deactivated"
    )
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )


class TrackableActivityModule(_TrkMaster, Base, Audited):
    """Modules whose activities can own trips (SVC, PRE). Table trk.trackable_activity_module."""

    __tablename__ = "trackable_activity_module"
    __table_args__ = {"schema": "trk"}

    source_schema: Mapped[str] = mapped_column(sa.NVARCHAR(10), doc="Owning table's schema")
    source_table: Mapped[str] = mapped_column(sa.NVARCHAR(60), doc="Owning table name")


class TrkTripTypeMaster(_TrkMaster, Base, Audited):
    """Trip types (To site, Return, ...). Table trk.trip_type."""

    __tablename__ = "trip_type"
    __table_args__ = {"schema": "trk"}

    is_default: Mapped[bool] = mapped_column(
        sa.Boolean(), server_default=sa.FetchedValue(), doc="Used when the client sends no trip type"
    )


class TrkTripVehicleTypeMaster(_TrkMaster, Base, Audited):
    """Vehicles a trip can be made with. Table trk.trip_vehicle_type."""

    __tablename__ = "trip_vehicle_type"
    __table_args__ = {"schema": "trk"}

    is_gps_tracked: Mapped[bool] = mapped_column(
        sa.Boolean(),
        server_default=sa.FetchedValue(),
        doc="True: GPS Start/Stop trip. False: distance is entered by hand (trk.manual_travel)",
    )


class TrkTripStatusMaster(_TrkMaster, Base, Audited):
    """Trip statuses. Set by the application, never by clients. Table trk.trip_status."""

    __tablename__ = "trip_status"
    __table_args__ = {"schema": "trk"}

    is_initial: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue(), doc="Status on start")
    is_final: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue(), doc="Trip has ended")


class TrkGpsDiagnosticEventType(_TrkMaster, Base, Audited):
    """GPS diagnostic event types (LOCATION_CALLBACK_SILENCE, GPS_DISABLED, ...). Table
    trk.gps_diagnostic_event_type."""

    __tablename__ = "gps_diagnostic_event_type"
    __table_args__ = {"schema": "trk"}

    code: Mapped[str] = mapped_column(sa.NVARCHAR(40), doc="Stable value sent by the app")


class TrackableActivity(Base, Audited):
    """Polymorphic anchor: one row per business activity that can own trips. Each module registers
    its own activity (a service visit, a sales activity, ...) and trips point here, not at the module."""

    __tablename__ = "trackable_activity"
    __table_args__ = {"schema": "trk"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    module_code: Mapped[str] = mapped_column(
        sa.NVARCHAR(10), sa.ForeignKey("trk.trackable_activity_module.code"), doc="Owning module"
    )
    activity_kind: Mapped[str | None] = mapped_column(sa.NVARCHAR(40), doc="Human label, e.g. 'Service visit'")
    source_schema: Mapped[str] = mapped_column(sa.NVARCHAR(10), doc="Owning table's schema")
    source_table: Mapped[str] = mapped_column(sa.NVARCHAR(60), doc="Owning table name")
    source_id: Mapped[int] = mapped_column(sa.BigInteger(), doc="Owning row id")
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"), doc="Who travels")
    customer_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.customer.id"), doc="Customer")
    title: Mapped[str | None] = mapped_column(sa.NVARCHAR(200), doc="Display title")
    target_latitude: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 6), doc="Destination")
    target_longitude: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 6), doc="Destination")
    geofence_radius_m: Mapped[int | None] = mapped_column(sa.Integer(), doc="Arrival radius")
    client_uuid: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid(), doc="Device-generated id for idempotency")
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )


class TrkTrip(Base, Audited):
    """A trip against a trackable activity: start, end, route, distance, time. Table trk.trip."""

    __tablename__ = "trip"
    __table_args__ = {"schema": "trk"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    trackable_activity_id: Mapped[int] = mapped_column(
        sa.BigInteger(), sa.ForeignKey("trk.trackable_activity.id"), doc="Activity"
    )
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"), doc="Who travels")
    user_device_id: Mapped[int | None] = mapped_column(
        sa.BigInteger(), sa.ForeignKey("core.user_device.id"), doc="Recording device"
    )
    client_uuid: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid(), doc="Device-generated id for idempotency")
    trip_type: Mapped[str] = mapped_column(sa.NVARCHAR(30), sa.ForeignKey("trk.trip_type.code"), doc="Trip type")
    start_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), doc="Start")
    start_latitude: Mapped[Decimal] = mapped_column(sa.Numeric(9, 6), doc="Start point")
    start_longitude: Mapped[Decimal] = mapped_column(sa.Numeric(9, 6), doc="Start point")
    end_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0), doc="End")
    end_latitude: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 6), doc="End point")
    end_longitude: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 6), doc="End point")
    gps_distance_km: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), doc="Distance from GPS points")
    map_distance_km: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), doc="Distance from Maps API")
    adjusted_distance_km: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(8, 2), doc="Team Lead's manual distance; overrides GPS for reporting (GPS kept in gps_distance_km)"
    )
    is_distance_adjusted: Mapped[bool] = mapped_column(
        sa.Boolean(), server_default=sa.FetchedValue(), doc="True once a manual distance adjustment has been applied"
    )
    duration_minutes: Mapped[int | None] = mapped_column(sa.Integer(), doc="Travel time")
    vehicle_type: Mapped[str | None] = mapped_column(
        sa.NVARCHAR(30), sa.ForeignKey("trk.trip_vehicle_type.code"), doc="Vehicle"
    )
    status: Mapped[str] = mapped_column(sa.NVARCHAR(30), sa.ForeignKey("trk.trip_status.code"), doc="Status")
    route_polyline: Mapped[str | None] = mapped_column(sa.UnicodeText(), doc="Encoded route")
    remarks: Mapped[str | None] = mapped_column(sa.NVARCHAR(500), doc="Engineer's remarks when the trip was stopped")
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )


class TrkTripGpsPoint(Base):
    """GPS points during a trip. High volume: partition by month, dedup on (trip_id, recorded_at)."""

    __tablename__ = "trip_gps_point"
    __table_args__ = {"schema": "trk"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    trip_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("trk.trip.id"), doc="Trip")
    recorded_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), doc="Capture time on the device")
    latitude: Mapped[Decimal] = mapped_column(sa.Numeric(9, 6), doc="Latitude")
    longitude: Mapped[Decimal] = mapped_column(sa.Numeric(9, 6), doc="Longitude")
    accuracy_m: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 1), doc="Accuracy")
    speed_kmph: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 1), doc="Speed")
    battery_pct: Mapped[int | None] = mapped_column(mssql.TINYINT(), doc="Phone battery")
    is_mock_location: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue(), doc="Fake-GPS flag")
    received_at: Mapped[dt.datetime] = mapped_column(
        mssql.DATETIME2(0), server_default=sa.FetchedValue(), doc="Server receipt time"
    )


class TrkTripDistanceAdjustment(Base):
    """Append-only audit log of manual distance adjustments. One row per adjustment: the GPS original
    is never overwritten, so the full before/after history (who, when, why) lives here. Table
    trk.trip_distance_adjustment."""

    __tablename__ = "trip_distance_adjustment"
    __table_args__ = {"schema": "trk"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    trip_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("trk.trip.id"), doc="Adjusted trip")
    previous_distance_km: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(8, 2), doc="Effective distance before this adjustment"
    )
    new_distance_km: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2), doc="Distance set by this adjustment")
    gps_distance_km_at_adjustment: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(8, 2), doc="Snapshot of the GPS-calculated distance at the time, for audit"
    )
    reason: Mapped[str] = mapped_column(sa.NVARCHAR(500), doc="Why the distance was adjusted")
    adjusted_by_user_id: Mapped[int] = mapped_column(sa.BigInteger(), doc="Team Lead who adjusted")
    adjusted_at: Mapped[dt.datetime] = mapped_column(
        mssql.DATETIME2(0), server_default=sa.FetchedValue(), doc="When the adjustment was made"
    )


class TrkTripGpsDiagnostic(Base):
    """A diagnostic event the app recorded while tracking: why the GPS trail has a gap and whether
    tracking recovered. Deduplicated on (trip_id, event_id). Device-state flags are nullable: NULL means
    the device could not tell. Table trk.trip_gps_diagnostic."""

    __tablename__ = "trip_gps_diagnostic"
    __table_args__ = {"schema": "trk"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    trip_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("trk.trip.id"), doc="Trip")
    event_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), doc="Client-generated id, for idempotency")
    event_type: Mapped[str] = mapped_column(
        sa.NVARCHAR(40), sa.ForeignKey("trk.gps_diagnostic_event_type.code"), doc="Event type"
    )
    recorded_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(3), doc="When the event happened on the device")
    duration_seconds: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 1), doc="Length, e.g. of a silence")
    gps_enabled: Mapped[bool | None] = mapped_column(sa.Boolean(), doc="Location services on")
    permission_granted: Mapped[bool | None] = mapped_column(sa.Boolean(), doc="Location permission granted")
    battery_exempted: Mapped[bool | None] = mapped_column(sa.Boolean(), doc="Exempt from battery optimisation")
    power_save_mode: Mapped[bool | None] = mapped_column(sa.Boolean(), doc="Battery saver on")
    device_idle_mode: Mapped[bool | None] = mapped_column(sa.Boolean(), doc="Doze / idle mode")
    network_connected: Mapped[bool | None] = mapped_column(sa.Boolean(), doc="Network reachable")
    call_state: Mapped[str | None] = mapped_column(sa.NVARCHAR(20), doc="Phone call state")
    manufacturer: Mapped[str | None] = mapped_column(sa.NVARCHAR(60), doc="Device manufacturer")
    model: Mapped[str | None] = mapped_column(sa.NVARCHAR(100), doc="Device model")
    os_name: Mapped[str | None] = mapped_column(sa.NVARCHAR(20), doc="Android / iOS")
    os_version: Mapped[str | None] = mapped_column(sa.NVARCHAR(30), doc="OS version")
    details: Mapped[str | None] = mapped_column(sa.NVARCHAR(500), doc="Free-text detail")
    latitude: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 6), doc="Last known position, if any")
    longitude: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 6), doc="Last known position, if any")
    accuracy_m: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 1), doc="Accuracy of that position")
    received_at: Mapped[dt.datetime] = mapped_column(
        mssql.DATETIME2(0), server_default=sa.FetchedValue(), doc="Server receipt time"
    )


class TrkManualTravel(Base, Audited):
    """Travel recorded by hand for a vehicle that has no GPS trip (Bus, Train, Other). Linked to the
    service call and the engineer; tickets are core.attachment rows. Table trk.manual_travel."""

    __tablename__ = "manual_travel"
    __table_args__ = {"schema": "trk"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    service_call_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("svc.service_call.id"))
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    vehicle_type: Mapped[str] = mapped_column(sa.NVARCHAR(30), sa.ForeignKey("trk.trip_vehicle_type.code"))
    travel_date: Mapped[dt.date] = mapped_column(sa.Date())
    distance_km: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2))
    notes: Mapped[str | None] = mapped_column(sa.NVARCHAR(500))
    client_uuid: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid(), doc="Device-generated id for idempotency")
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


class TrkTrackingConfig(Base, Audited):
    """One tracking parameter the mobile app fetches (interval, radius, thresholds ...). value is text,
    typed by value_type; NULL means "to be calibrated". Table trk.tracking_config."""

    __tablename__ = "tracking_config"
    __table_args__ = {"schema": "trk"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    code: Mapped[str] = mapped_column(sa.NVARCHAR(60), doc="Key in the API response")
    name: Mapped[str] = mapped_column(sa.NVARCHAR(100))
    description: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    value_type: Mapped[str] = mapped_column(sa.NVARCHAR(10), doc="int, decimal or string")
    value: Mapped[str | None] = mapped_column(sa.NVARCHAR(100), doc="Current value; NULL = to be calibrated")
    default_value: Mapped[str | None] = mapped_column(sa.NVARCHAR(100))
    unit: Mapped[str | None] = mapped_column(sa.NVARCHAR(10))
    min_value: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    max_value: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    allowed_values: Mapped[str | None] = mapped_column(sa.NVARCHAR(200), doc="Comma-separated choices")
    sort_order: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.FetchedValue())
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}
