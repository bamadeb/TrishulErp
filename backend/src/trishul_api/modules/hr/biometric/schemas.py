"""Request and response models for the biometric integration foundation."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime

PunchSource = Literal["Sync", "Manual", "Demo"]
SyncStatus = Literal["Pending", "Running", "Success", "Failed", "Skipped"]
SyncTrigger = Literal["Manual", "Scheduled"]
DeviceStatusLabel = Literal["Online", "Offline", "Maintenance"]


class BiometricDeviceCreate(InputModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    vendor: str = Field("ESSL", min_length=1, max_length=40)
    serial_number: str | None = Field(None, max_length=80)
    location_name: str | None = Field(None, max_length=120)
    branch_id: int | None = Field(None, gt=0)
    external_device_id: str | None = Field(None, max_length=80)
    credential_secret_name: str | None = Field(None, max_length=100)
    base_url: str | None = Field(None, max_length=300)
    is_sync_enabled: bool = False


class BiometricDeviceUpdate(InputModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    vendor: str | None = Field(None, min_length=1, max_length=40)
    serial_number: str | None = Field(None, max_length=80)
    location_name: str | None = Field(None, max_length=120)
    branch_id: int | None = Field(None, gt=0)
    external_device_id: str | None = Field(None, max_length=80)
    credential_secret_name: str | None = Field(None, max_length=100)
    base_url: str | None = Field(None, max_length=300)
    is_sync_enabled: bool | None = None
    is_active: bool | None = None


class BiometricDeviceOut(ApiModel):
    id: int
    code: str
    name: str
    vendor: str
    serial_number: str | None
    location_name: str | None
    branch_id: int | None
    external_device_id: str | None
    credential_secret_name: str | None
    base_url: str | None
    is_sync_enabled: bool
    last_synced_at: UtcDateTime | None
    is_active: bool
    status: DeviceStatusLabel
    created_at: UtcDateTime
    row_version: RowVersion


class BiometricMappingCreate(InputModel):
    employee_id: int = Field(gt=0)
    biometric_user_id: str = Field(min_length=1, max_length=80)
    device_id: int | None = Field(None, gt=0)
    effective_from: date
    effective_to: date | None = None


class BiometricMappingUpdate(InputModel):
    biometric_user_id: str | None = Field(None, min_length=1, max_length=80)
    device_id: int | None = Field(None, gt=0)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None


class BiometricMappingOut(ApiModel):
    id: int
    employee_id: int
    employee_code: str | None = None
    employee_name: str | None = None
    department_name: str | None = None
    branch_name: str | None = None
    biometric_user_id: str
    device_id: int | None
    device_name: str | None = None
    effective_from: date
    effective_to: date | None
    is_active: bool
    created_at: UtcDateTime


class BiometricPunchQuery(PageQuery):
    device_id: int | None = Field(None, gt=0)
    employee_id: int | None = Field(None, gt=0)
    biometric_user_id: str | None = Field(None, max_length=80)
    punch_type: str | None = Field(None, max_length=20)
    from_at: datetime | None = None
    to_at: datetime | None = None


class BiometricPunchOut(ApiModel):
    id: int
    device_id: int
    device_name: str | None = None
    device_location: str | None = None
    employee_id: int | None
    employee_code: str | None = None
    employee_name: str | None = None
    department_name: str | None = None
    biometric_user_id: str
    punched_at: UtcDateTime
    punch_type: str | None
    external_punch_id: str | None
    source: str
    sync_log_id: int | None
    created_at: UtcDateTime


class BiometricSyncRequest(InputModel):
    device_id: int | None = Field(None, gt=0, description="Limit sync to one device; omit for all enabled devices.")
    since: datetime | None = None
    until: datetime | None = None


class BiometricSyncLogOut(ApiModel):
    id: int
    device_id: int | None
    device_name: str | None = None
    device_code: str | None = None
    started_at: UtcDateTime
    finished_at: UtcDateTime | None
    status: SyncStatus
    trigger: SyncTrigger
    records_fetched: int
    records_inserted: int
    records_duplicate: int
    error_message: str | None
    created_by_user_id: int | None


class BiometricSyncLogQuery(PageQuery):
    device_id: int | None = Field(None, gt=0)
    status: SyncStatus | None = None
    trigger: SyncTrigger | None = None


class PunchTrendPoint(ApiModel):
    hour: str
    check_in: int
    check_out: int


class DeviceStatusCounts(ApiModel):
    online: int
    offline: int
    maintenance: int


IntegrationStatus = Literal["Ready", "Disabled", "Blocked"]


class BiometricDashboardOut(ApiModel):
    registered_devices: int
    mapped_employees: int
    todays_punches: int
    last_sync_at: UtcDateTime | None
    last_sync_status: SyncStatus | None
    sync_failures: int
    device_status: DeviceStatusCounts
    punch_trend: list[PunchTrendPoint]
    recent_punches: list[BiometricPunchOut]
    """Vendor sync readiness — never implies punches were invented."""
    integration_status: IntegrationStatus = "Disabled"
    integration_message: str = ""
