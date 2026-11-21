"""Request and response models for Daily Attendance."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, UtcDateTime

AttendanceDisplayStatus = Literal[
    "Present",
    "Late",
    "Missing Punch",
    "Absent",
    "On Leave",
    "Off Day",
    "Holiday",
]
StatusTab = Literal["all", "present", "absent", "leave", "offDay"]
PunchKind = Literal["IN", "OUT"]


class DailyAttendanceQuery(PageQuery):
    attendance_date: date = Field(alias="date")
    status_tab: StatusTab = "all"
    department: str | None = Field(None, max_length=120)
    location: str | None = Field(None, max_length=120)
    shift: str | None = Field(None, max_length=60)
    status: AttendanceDisplayStatus | None = None
    employee_type: str | None = Field(None, max_length=40)
    reporting_manager: str | None = Field(None, max_length=120)
    include_history: bool = False
    include_punches: bool = True


class AttendancePunchOut(ApiModel):
    kind: PunchKind
    at: UtcDateTime
    device: str


class AttendanceHistoryOut(ApiModel):
    date: date
    status: AttendanceDisplayStatus
    first_in: UtcDateTime | None = None
    last_out: UtcDateTime | None = None
    working_hours: str | None = None


class DailyAttendanceRowOut(ApiModel):
    id: int
    employee_id: int
    employee_code: str
    employee_name: str
    department: str
    location: str
    shift: str
    employee_type: str
    reporting_manager: str
    first_in: UtcDateTime | None = None
    last_out: UtcDateTime | None = None
    first_in_late: bool = False
    working_hours: str | None = None
    status: AttendanceDisplayStatus
    remarks: str = ""
    punches: list[AttendancePunchOut] = Field(default_factory=list)
    history: list[AttendanceHistoryOut] = Field(default_factory=list)


class AttendanceSummaryOut(ApiModel):
    total: int
    present: int
    late: int
    missing_punch: int
    absent: int
    on_leave: int
    off_day: int
    holiday: int


class AttendanceFilterOptionsOut(ApiModel):
    departments: list[str]
    locations: list[str]
    shifts: list[str]
    employee_types: list[str]
    managers: list[str]
    statuses: list[AttendanceDisplayStatus]


class DailyAttendancePageOut(ApiModel):
    date: date
    summary: AttendanceSummaryOut
    filter_options: AttendanceFilterOptionsOut
    items: list[DailyAttendanceRowOut]
    total: int
    page: int
    page_size: int


MusterDayCode = Literal["P", "L", "A", "PL", "WFH", "OFF", "H"]
EmploymentStatusFilter = Literal["Active", "Inactive"]


class MonthlyMusterQuery(PageQuery):
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    department: str | None = Field(None, max_length=120)
    location: str | None = Field(None, max_length=120)
    employment_status: EmploymentStatusFilter | None = None


class MusterDayColumnOut(ApiModel):
    day: int
    weekday: str
    is_weekend: bool


class MusterEmployeeRowOut(ApiModel):
    id: int
    employee_id: int
    employee_code: str
    employee_name: str
    department: str
    location: str
    employment_status: EmploymentStatusFilter
    days: list[MusterDayCode]
    present: int
    late: int
    absent: int
    leave: int
    wfh: int
    hours: int


class MusterKpiOut(ApiModel):
    """Month totals: employee count + sum of day-codes across the filtered roster."""

    total: int
    present: int
    late: int
    absent: int
    on_leave: int
    wfh: int


class MusterFilterOptionsOut(ApiModel):
    departments: list[str]
    locations: list[str]


class MonthlyMusterPageOut(ApiModel):
    year: int
    month: int
    days_in_month: int
    day_columns: list[MusterDayColumnOut]
    summary: MusterKpiOut
    filter_options: MusterFilterOptionsOut
    items: list[MusterEmployeeRowOut]
    total: int
    page: int
    page_size: int


ExceptionType = Literal[
    "Missing Punch",
    "Late Arrival",
    "Early Exit",
    "Short Hours",
    "Absent",
]
ExceptionReviewStatus = Literal["Pending", "Resolved"]
ExceptionTab = Literal["all", "pending", "resolved"]


class AttendanceExceptionsQuery(PageQuery):
    date_from: date = Field(alias="from")
    date_to: date = Field(alias="to")
    status_tab: ExceptionTab = "all"
    department: str | None = Field(None, max_length=120)
    location: str | None = Field(None, max_length=120)
    exception_type: ExceptionType | None = None
    status: ExceptionReviewStatus | None = None


class AttendanceExceptionRowOut(ApiModel):
    id: int
    employee_id: int
    employee_code: str
    employee_name: str
    department: str
    location: str
    date: date
    shift: str
    first_in: UtcDateTime | None = None
    last_out: UtcDateTime | None = None
    exception_type: ExceptionType
    expected_hours: str
    actual_hours: str | None = None
    status: ExceptionReviewStatus
    remark: str = ""


class ExceptionKpiOut(ApiModel):
    total: int
    missing_punch: int
    late_arrival: int
    early_exit: int
    short_hours: int
    absent: int


class ExceptionFilterOptionsOut(ApiModel):
    departments: list[str]
    locations: list[str]
    exception_types: list[ExceptionType]


class AttendanceExceptionsPageOut(ApiModel):
    date_from: date
    date_to: date
    summary: ExceptionKpiOut
    filter_options: ExceptionFilterOptionsOut
    items: list[AttendanceExceptionRowOut]
    total: int
    page: int
    page_size: int
    pending_count: int
    resolved_count: int


class ResolveExceptionIn(InputModel):
    remark: str | None = Field(None, max_length=300)


RegularizationRequestType = Literal[
    "Missed Punch",
    "Wrong Attendance",
    "Early Exit",
    "WFH Correction",
    "Late Arrival",
]
RegularizationStatus = Literal["Pending", "Approved", "Rejected"]
RegularizationTab = Literal["pending", "approved", "rejected", "all"]


class RegularizationQuery(PageQuery):
    date_from: date = Field(alias="from")
    date_to: date = Field(alias="to")
    status_tab: RegularizationTab = "all"
    department: str | None = Field(None, max_length=120)
    location: str | None = Field(None, max_length=120)
    request_type: RegularizationRequestType | None = None


class RegularizationRowOut(ApiModel):
    id: int
    employee_id: int
    employee_code: str
    employee_name: str
    department: str
    location: str
    attendance_date: date
    request_type: RegularizationRequestType
    original_in: UtcDateTime | None = None
    original_out: UtcDateTime | None = None
    requested_in: str | None = None
    requested_out: str | None = None
    reason: str
    submitted_on: UtcDateTime
    status: RegularizationStatus
    rejection_reason: str | None = None
    attachment_name: str | None = None


class RegularizationKpiOut(ApiModel):
    total: int
    pending: int
    approved: int
    rejected: int


class RegularizationFilterOptionsOut(ApiModel):
    departments: list[str]
    locations: list[str]
    request_types: list[RegularizationRequestType]


class RegularizationPageOut(ApiModel):
    date_from: date
    date_to: date
    summary: RegularizationKpiOut
    filter_options: RegularizationFilterOptionsOut
    items: list[RegularizationRowOut]
    total: int
    page: int
    page_size: int
    pending_count: int
    approved_count: int
    rejected_count: int


class RegularizationCreateIn(InputModel):
    employee_id: int = Field(alias="employeeId", gt=0)
    attendance_date: date = Field(alias="attendanceDate")
    request_type: RegularizationRequestType = Field(alias="requestType")
    requested_in: str | None = Field(None, alias="requestedIn", max_length=20)
    requested_out: str | None = Field(None, alias="requestedOut", max_length=20)
    reason: str = Field(..., min_length=1, max_length=250)
    attachment_name: str | None = Field(None, alias="attachmentName", max_length=120)


class RegularizationDecisionIn(InputModel):
    remark: str | None = Field(None, max_length=250)
