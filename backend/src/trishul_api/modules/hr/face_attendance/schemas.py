"""Request and response models for mobile face attendance (set-up and the employee's day)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from trishul_api.common.schemas import ApiModel, InputModel, RowVersion, UtcDateTime

PolicyMode = Literal["Office", "Field", "Hybrid"]
ChallengeKind = Literal["None", "Blink", "Blink and turn"]
PunchType = Literal["In", "Out"]
PunchStatus = Literal["Present", "Pending", "Rejected"]
FaceStatus = Literal["Not registered", "Pending approval", "Active", "Rejected"]

_LAT = Field(ge=-90, le=90, max_digits=9, decimal_places=6)
_LON = Field(ge=-180, le=180, max_digits=9, decimal_places=6)
_THRESHOLD = Field(None, ge=0, le=1, max_digits=5, decimal_places=4)


# --- work locations -------------------------------------------------------------


class WorkLocationCreate(InputModel):
    name: str = Field(min_length=1, max_length=120)
    branch_id: int | None = Field(None, gt=0)
    latitude: Decimal = _LAT
    longitude: Decimal = _LON
    radius_m: int = Field(150, ge=10, le=5000)
    address: str | None = Field(None, max_length=300)


class WorkLocationUpdate(InputModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    branch_id: int | None = Field(None, gt=0)
    latitude: Decimal | None = Field(None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(None, ge=-180, le=180, max_digits=9, decimal_places=6)
    radius_m: int | None = Field(None, ge=10, le=5000)
    address: str | None = Field(None, max_length=300)
    is_active: bool | None = None


class WorkLocationOut(ApiModel):
    id: int
    name: str
    branch_id: int | None
    branch_name: str | None = None
    latitude: Decimal
    longitude: Decimal
    radius_m: int
    address: str | None
    is_active: bool
    row_version: RowVersion


# --- policies --------------------------------------------------------------------


class AttendancePolicyCreate(InputModel):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=1, max_length=80)
    mode: PolicyMode
    challenge: ChallengeKind = "Blink"
    challenge_on_check_out: bool = False
    antispoof_required: bool = True
    match_threshold: Decimal | None = _THRESHOLD
    review_threshold: Decimal | None = _THRESHOLD
    max_score_gap: Decimal = Field(Decimal("0.1"), ge=0, le=1, max_digits=5, decimal_places=4)
    max_gps_accuracy_m: int = Field(100, ge=5, le=2000)
    allow_offline: bool = True
    offline_auto_accept: bool = True
    max_offline_hours: int = Field(72, ge=1, le=720)

    @model_validator(mode="after")
    def _review_below_match(self) -> "AttendancePolicyCreate":
        _check_thresholds(self.match_threshold, self.review_threshold)
        return self


class AttendancePolicyUpdate(InputModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    mode: PolicyMode | None = None
    challenge: ChallengeKind | None = None
    challenge_on_check_out: bool | None = None
    antispoof_required: bool | None = None
    match_threshold: Decimal | None = _THRESHOLD
    review_threshold: Decimal | None = _THRESHOLD
    max_score_gap: Decimal | None = Field(None, ge=0, le=1, max_digits=5, decimal_places=4)
    max_gps_accuracy_m: int | None = Field(None, ge=5, le=2000)
    allow_offline: bool | None = None
    offline_auto_accept: bool | None = None
    max_offline_hours: int | None = Field(None, ge=1, le=720)
    is_active: bool | None = None


def _check_thresholds(match: Decimal | None, review: Decimal | None) -> None:
    if match is not None and review is not None and review > match:
        raise ValueError("The review threshold must not be above the match threshold.")


class AttendancePolicyOut(ApiModel):
    id: int
    code: str
    name: str
    mode: PolicyMode
    challenge: ChallengeKind
    challenge_on_check_out: bool
    antispoof_required: bool
    match_threshold: Decimal | None
    review_threshold: Decimal | None
    max_score_gap: Decimal
    max_gps_accuracy_m: int
    allow_offline: bool
    offline_auto_accept: bool
    max_offline_hours: int
    is_active: bool
    employee_count: int = 0
    row_version: RowVersion


# --- employee assignment ---------------------------------------------------------


class EmployeePolicyAssign(InputModel):
    policy_id: int = Field(gt=0)
    from_date: date
    work_location_ids: list[int] = Field(default_factory=list, max_length=20)


class AttendanceEmployeeOut(ApiModel):
    """One employee on the HR set-up screen: policy in force today and face registration status."""

    employee_id: int
    employee_code: str
    employee_name: str
    branch_id: int | None
    branch_name: str | None
    department_name: str | None
    policy_id: int | None
    policy_code: str | None
    policy_name: str | None
    policy_mode: PolicyMode | None
    policy_from_date: date | None
    work_location_ids: list[int]
    work_location_names: list[str]
    face_id: int | None
    face_status: FaceStatus


class EmployeePolicyOut(ApiModel):
    id: int
    employee_id: int
    policy: AttendancePolicyOut
    from_date: date
    to_date: date | None
    work_locations: list[WorkLocationOut]


# --- face registration (HR) -------------------------------------------------------

FaceRecordStatus = Literal["Pending approval", "Active", "Rejected", "Superseded", "Deleted"]


class FaceModelOut(ApiModel):
    id: int
    code: str
    kind: Literal["Face", "Anti-spoof"]
    version: str
    vector_size: int | None
    default_match_threshold: Decimal | None
    default_review_threshold: Decimal | None
    is_current: bool
    activated_at: UtcDateTime | None


class FaceRegistrationOut(ApiModel):
    id: int
    employee_id: int
    employee_code: str | None = None
    employee_name: str | None = None
    status: FaceRecordStatus
    face_confidence: Decimal | None
    sharpness: Decimal | None
    brightness: Decimal | None
    face_model: str | None = None
    registered_by_user_id: int | None
    registered_at: UtcDateTime
    approved_by_user_id: int | None
    approved_at: UtcDateTime | None
    rejection_reason: str | None
    consent_at: UtcDateTime | None
    row_version: RowVersion


class FaceRejectIn(InputModel):
    reason: str = Field(min_length=3, max_length=300)


# --- punching (mobile) --------------------------------------------------------------

ChallengeResult = Literal["Passed", "Failed", "Not done"]


class ChallengeRequest(InputModel):
    punch_type: PunchType


class ChallengeOut(ApiModel):
    nonce: str
    punch_type: PunchType
    challenge: str
    """What the phone must ask for: "None", "Blink", "Blink, then turn left" or "Blink, then turn right"."""
    instruction: str
    expires_at: UtcDateTime
    server_time: UtcDateTime


class PunchEvidence(InputModel):
    """Everything the phone sends with a punch except the photos (sent as multipart files)."""

    client_uuid: str = Field(min_length=8, max_length=36, pattern=r"^[A-Za-z0-9-]+$")
    punch_type: PunchType
    nonce: str | None = Field(None, max_length=64)
    challenge_result: ChallengeResult = "Not done"
    device_score: Decimal | None = Field(None, ge=-1, le=1, max_digits=5, decimal_places=4)
    latitude: Decimal | None = Field(None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(None, ge=-180, le=180, max_digits=9, decimal_places=6)
    gps_accuracy_m: Decimal | None = Field(None, ge=0, le=100000, max_digits=9, decimal_places=2)
    location_captured_at: datetime | None = None
    is_mock_location: bool = False
    device_captured_at: datetime | None = None
    device_elapsed_ms: int | None = Field(None, ge=0)
    device_boot_id: str | None = Field(None, max_length=64)
    device_id: str | None = Field(None, max_length=100)
    platform: str | None = Field(None, max_length=20)
    os_version: str | None = Field(None, max_length=40)
    app_version: str | None = Field(None, max_length=40)
    integrity_token: str | None = Field(None, max_length=8000)
    keystore_signature: str | None = Field(None, max_length=600)

    @model_validator(mode="after")
    def _location_pair(self) -> "PunchEvidence":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Send both latitude and longitude, or neither.")
        return self


class PunchResultOut(ApiModel):
    id: int
    client_uuid: str
    punch_type: PunchType
    status: PunchStatus
    status_reason: str | None
    message: str
    effective_at: UtcDateTime
    attendance_date: date
    capture_mode: Literal["Online", "Offline"]
    inside_geofence: bool | None
    work_location_name: str | None = None
    already_received: bool = False


class PunchListItemOut(ApiModel):
    id: int
    employee_id: int
    employee_code: str | None
    employee_name: str | None
    attendance_date: date
    punch_type: PunchType
    effective_at: UtcDateTime
    capture_mode: Literal["Online", "Offline"]
    status: PunchStatus
    status_reason: str | None
    face_status: str
    server_score: Decimal | None
    device_score: Decimal | None
    challenge: str | None
    challenge_result: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    gps_accuracy_m: Decimal | None
    is_mock_location: bool
    inside_geofence: bool | None
    distance_m: Decimal | None
    work_location_name: str | None
    time_trust: str
    has_photo: bool
    reviewed_by_user_id: int | None
    reviewed_at: UtcDateTime | None
    review_remarks: str | None


class PunchReviewIn(InputModel):
    decision: Literal["Present", "Rejected"]
    remarks: str = Field(min_length=3, max_length=300)


class FaceTemplateOut(ApiModel):
    """The signed-in employee's own registered face, for matching on the phone when offline."""

    face_id: int
    model_code: str
    model_version: str
    vector_size: int
    vector: str
    """Little-endian float32 values, base64."""
    match_threshold: Decimal
    review_threshold: Decimal


# --- the employee's month (mobile calendar) ------------------------------------------


class MyMonthDayOut(ApiModel):
    """One day of the employee's own calendar, as HR's Daily Attendance and Muster see it."""

    date: date
    status: str
    """Present, Late, Missing Punch, Absent, On Leave, Off Day or Holiday."""
    first_in: datetime | None
    last_out: datetime | None
    working_hours: str | None


class MyMonthOut(ApiModel):
    year: int
    month: int
    days: list[MyMonthDayOut]
    """1st of the month up to today (or the month end), oldest first; future days are left out."""
    totals: dict[str, int]
    """Days per status in this month so far."""


# --- the employee's day (mobile) --------------------------------------------------


class MyPunchOut(ApiModel):
    id: int
    punch_type: PunchType
    effective_at: UtcDateTime
    status: PunchStatus
    status_reason: str | None
    capture_mode: Literal["Online", "Offline"]
    inside_geofence: bool | None
    work_location_name: str | None = None


class MyFaceOut(ApiModel):
    status: FaceStatus
    registered_at: UtcDateTime | None = None
    rejection_reason: str | None = None


class MyAttendanceTodayOut(ApiModel):
    server_time: UtcDateTime
    attendance_date: date
    employee_id: int
    can_punch: bool
    blocked_reason: str | None
    next_punch_type: PunchType
    policy: AttendancePolicyOut | None
    work_locations: list[WorkLocationOut]
    face: MyFaceOut
    face_model_version: str | None
    punches: list[MyPunchOut]
