# Hand-written until the model generator is re-run. Keep these columns in step with
# migration 0043_biometric_foundation.

"""Biometric device registry, employee mapping, punch storage and sync audit."""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from trishul_api.db.models.base import Base


class BiometricDevice(Base):
    """One biometric terminal or controller registered for attendance sync."""

    __tablename__ = "biometric_device"
    __table_args__ = (
        sa.UniqueConstraint("code", name="UQ_hr_biometric_device_code"),
        {"schema": "hr"},
    )

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    code: Mapped[str] = mapped_column(sa.NVARCHAR(40))
    name: Mapped[str] = mapped_column(sa.NVARCHAR(120))
    vendor: Mapped[str] = mapped_column(sa.NVARCHAR(40), server_default=sa.FetchedValue())
    serial_number: Mapped[str | None] = mapped_column(sa.NVARCHAR(80))
    location_name: Mapped[str | None] = mapped_column(sa.NVARCHAR(120))
    branch_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.branch.id"))
    external_device_id: Mapped[str | None] = mapped_column(sa.NVARCHAR(80))
    credential_secret_name: Mapped[str | None] = mapped_column(
        sa.NVARCHAR(100), doc="AWS Secrets Manager key; credentials are never stored here"
    )
    base_url: Mapped[str | None] = mapped_column(sa.NVARCHAR(300), doc="Optional API base URL override")
    is_sync_enabled: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    last_synced_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


class BiometricEmployeeMapping(Base):
    """Maps a Trishul employee to a biometric user id on one device (or all devices)."""

    __tablename__ = "biometric_employee_mapping"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    biometric_user_id: Mapped[str] = mapped_column(sa.NVARCHAR(80))
    device_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.biometric_device.id"))
    effective_from: Mapped[dt.date] = mapped_column(sa.Date())
    effective_to: Mapped[dt.date | None] = mapped_column(sa.Date())
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


class BiometricPunchLog(Base):
    """Stored biometric punch. Duplicate protection uses external_punch_id or a composite key."""

    __tablename__ = "biometric_punch_log"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    device_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.biometric_device.id"))
    employee_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    biometric_user_id: Mapped[str] = mapped_column(sa.NVARCHAR(80))
    punched_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0))
    punch_type: Mapped[str | None] = mapped_column(sa.NVARCHAR(20))
    external_punch_id: Mapped[str | None] = mapped_column(sa.NVARCHAR(100))
    source: Mapped[str] = mapped_column(sa.NVARCHAR(20), server_default=sa.FetchedValue())
    sync_log_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.biometric_sync_log.id"))
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())


class BiometricSyncLog(Base):
    """One synchronization attempt (manual or scheduled)."""

    __tablename__ = "biometric_sync_log"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    device_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.biometric_device.id"))
    started_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    finished_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    status: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    trigger: Mapped[str] = mapped_column("trigger", sa.NVARCHAR(20))
    records_fetched: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.FetchedValue())
    records_inserted: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.FetchedValue())
    records_duplicate: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.FetchedValue())
    error_message: Mapped[str | None] = mapped_column(sa.NVARCHAR(500))
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
