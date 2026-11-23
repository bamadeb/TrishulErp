# Hand-written until the model generator is re-run. Keep these columns in step with
# migration 0046_face_attendance.

"""Mobile face attendance: face models, registered faces, geofences, policies, punches and audit."""

import datetime as dt
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from trishul_api.db.models.base import Base

_SCHEMA = {"schema": "hr"}


class _Standard:
    """created/updated/is_active/row_version, as on every Trishul table."""

    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, object]:
        return {"version_id_col": cls.__table__.c.row_version, "version_id_generator": False}  # type: ignore[attr-defined]


class FaceModel(_Standard, Base):
    """A face or anti-spoof model version; every score names the model that made it."""

    __tablename__ = "face_model"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    code: Mapped[str] = mapped_column(sa.NVARCHAR(40))
    kind: Mapped[str] = mapped_column(sa.NVARCHAR(20), doc="Face | Anti-spoof")
    version: Mapped[str] = mapped_column(sa.NVARCHAR(40))
    file_sha256: Mapped[str | None] = mapped_column(sa.NVARCHAR(64))
    vector_size: Mapped[int | None] = mapped_column(sa.SmallInteger())
    default_match_threshold: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4))
    default_review_threshold: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4))
    is_current: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    activated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))


class EmployeeFace(_Standard, Base):
    """An employee's registered face; one Active row per employee."""

    __tablename__ = "employee_face"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    photo_s3_key: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    photo_sha256: Mapped[str | None] = mapped_column(sa.NVARCHAR(64))
    face_vector: Mapped[bytes | None] = mapped_column(sa.LargeBinary(), doc="Encrypted")
    face_model_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.face_model.id"))
    face_confidence: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4))
    sharpness: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 2))
    brightness: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2))
    face_count: Mapped[int | None] = mapped_column(sa.SmallInteger())
    status: Mapped[str] = mapped_column(sa.NVARCHAR(20), server_default=sa.FetchedValue())
    registered_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    approved_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    approved_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    rejection_reason: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    consent_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    delete_after: Mapped[dt.date | None] = mapped_column(sa.Date())


class WorkLocation(_Standard, Base):
    """An office geofence."""

    __tablename__ = "work_location"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    branch_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.branch.id"))
    name: Mapped[str] = mapped_column(sa.NVARCHAR(120))
    latitude: Mapped[Decimal] = mapped_column(sa.Numeric(9, 6))
    longitude: Mapped[Decimal] = mapped_column(sa.Numeric(9, 6))
    radius_m: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("150"))
    address: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))


class AttendancePolicy(_Standard, Base):
    """How strict face attendance is for a group of employees."""

    __tablename__ = "attendance_policy"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    code: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    name: Mapped[str] = mapped_column(sa.NVARCHAR(80))
    mode: Mapped[str] = mapped_column(sa.NVARCHAR(10), doc="Office | Field | Hybrid")
    challenge: Mapped[str] = mapped_column(sa.NVARCHAR(20), server_default=sa.text("'Blink'"))
    challenge_on_check_out: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.text("0"))
    antispoof_required: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.text("1"))
    match_threshold: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4))
    review_threshold: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4))
    max_score_gap: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4), server_default=sa.text("0.1"))
    max_gps_accuracy_m: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("100"))
    allow_offline: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.text("1"))
    offline_auto_accept: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.text("1"))
    max_offline_hours: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("72"))


class EmployeeAttendancePolicy(_Standard, Base):
    """Which attendance policy applies to an employee, from a date."""

    __tablename__ = "employee_attendance_policy"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    policy_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.attendance_policy.id"))
    from_date: Mapped[dt.date] = mapped_column(sa.Date())
    to_date: Mapped[dt.date | None] = mapped_column(sa.Date())


class EmployeeAttendanceLocation(Base):
    """A work location allowed for an employee's attendance policy assignment."""

    __tablename__ = "employee_attendance_location"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    employee_attendance_policy_id: Mapped[int] = mapped_column(
        sa.BigInteger(), sa.ForeignKey("hr.employee_attendance_policy.id", ondelete="CASCADE")
    )
    work_location_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.work_location.id"))


class AttendanceChallenge(Base):
    """A one-time nonce the server issues for an online punch."""

    __tablename__ = "attendance_challenge"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    nonce: Mapped[str] = mapped_column(sa.NVARCHAR(64), unique=True)
    punch_type: Mapped[str] = mapped_column(sa.NVARCHAR(3), doc="In | Out")
    challenge: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    issued_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    expires_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0))
    used_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))


class AttendancePunch(_Standard, Base):
    """One mobile face check-in or check-out with its evidence."""

    __tablename__ = "attendance_punch"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    client_uuid: Mapped[str] = mapped_column(sa.NVARCHAR(36), unique=True)
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    attendance_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.attendance.id"))
    attendance_date: Mapped[dt.date] = mapped_column(sa.Date())
    punch_type: Mapped[str] = mapped_column(sa.NVARCHAR(3), doc="In | Out")
    # time
    device_captured_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    device_elapsed_ms: Mapped[int | None] = mapped_column(sa.BigInteger())
    device_boot_id: Mapped[str | None] = mapped_column(sa.NVARCHAR(64))
    server_received_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    effective_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0))
    time_trust: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    # face
    photo_s3_key: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    photo_sha256: Mapped[str | None] = mapped_column(sa.NVARCHAR(64))
    frame_hashes: Mapped[str | None] = mapped_column(sa.NVARCHAR(1000))
    employee_face_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.employee_face.id"))
    face_model_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.face_model.id"))
    device_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4))
    server_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4))
    face_status: Mapped[str] = mapped_column(sa.NVARCHAR(20), server_default=sa.text("'Not checked'"))
    challenge: Mapped[str | None] = mapped_column(sa.NVARCHAR(20))
    challenge_nonce: Mapped[str | None] = mapped_column(sa.NVARCHAR(64))
    challenge_result: Mapped[str | None] = mapped_column(sa.NVARCHAR(10))
    antispoof_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4))
    # location
    latitude: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 6))
    gps_accuracy_m: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 2))
    location_captured_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    is_mock_location: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.text("0"))
    work_location_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.work_location.id"))
    distance_m: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 1))
    inside_geofence: Mapped[bool | None] = mapped_column(sa.Boolean())
    address: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    # device
    device_id: Mapped[str | None] = mapped_column(sa.NVARCHAR(100))
    platform: Mapped[str | None] = mapped_column(sa.NVARCHAR(20))
    os_version: Mapped[str | None] = mapped_column(sa.NVARCHAR(40))
    app_version: Mapped[str | None] = mapped_column(sa.NVARCHAR(40))
    integrity_verdict: Mapped[str | None] = mapped_column(sa.NVARCHAR(60))
    keystore_signature: Mapped[str | None] = mapped_column(sa.NVARCHAR(600))
    ip_address: Mapped[str | None] = mapped_column(sa.NVARCHAR(45))
    capture_mode: Mapped[str] = mapped_column(sa.NVARCHAR(10), doc="Online | Offline")
    # outcome
    status: Mapped[str] = mapped_column(sa.NVARCHAR(10), doc="Present | Pending | Rejected")
    status_reason: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    reviewed_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    review_remarks: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))


class AttendanceAudit(Base):
    """Append-only log of attendance changes and photo / face-vector access."""

    __tablename__ = "attendance_audit"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    entity: Mapped[str] = mapped_column(sa.NVARCHAR(20), doc="punch | face | policy | location | model")
    entity_id: Mapped[int] = mapped_column(sa.BigInteger())
    action: Mapped[str] = mapped_column(sa.NVARCHAR(40))
    old_json: Mapped[str | None] = mapped_column(sa.UnicodeText())
    new_json: Mapped[str | None] = mapped_column(sa.UnicodeText())
    by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    ip_address: Mapped[str | None] = mapped_column(sa.NVARCHAR(45))
