# Hand-written (not produced by scripts/generate_models.py): the trk schema was added by migration
# 0006 and these mirror its DDL. Re-run the generator against the migrated DB to fold this into
# generated/ and then delete this file. Keep the columns in sync with migration 0006 until then.

"""ORM models for the trk schema (common, cross-module trip tracking): 3 tables."""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from trishul_api.db.models.base import Audited, Base

TrackableActivityModuleCode = Literal["SVC", "PRE"]
TrkTripType = Literal["To site", "Return", "Site to site"]
TrkTripVehicleType = Literal["Own bike", "Own car", "Company vehicle", "Public transport"]
TrkTripStatus = Literal["In progress", "Completed", "Auto closed"]


class TrackableActivity(Base, Audited):
    """Polymorphic anchor: one row per business activity that can own trips. Each module registers
    its own activity (a service visit, a sales activity, ...) and trips point here, not at the module."""

    __tablename__ = "trackable_activity"
    __table_args__ = {"schema": "trk"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    module_code: Mapped[TrackableActivityModuleCode] = mapped_column(sa.NVARCHAR(10), doc="Owning module")
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
    trip_type: Mapped[TrkTripType] = mapped_column(sa.NVARCHAR(30), doc="Trip type")
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
    vehicle_type: Mapped[TrkTripVehicleType | None] = mapped_column(sa.NVARCHAR(30), doc="Vehicle")
    status: Mapped[TrkTripStatus] = mapped_column(sa.NVARCHAR(30), doc="Status")
    route_polyline: Mapped[str | None] = mapped_column(sa.UnicodeText(), doc="Encoded route")
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
