"""Request and response models for Daily Attendance."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime

IST = timezone(timedelta(hours=5, minutes=30), "IST")


def _as_india(value: datetime) -> datetime:
    return value.replace(tzinfo=IST) if value.tzinfo is None else value


IndiaDateTime = Annotated[datetime, AfterValidator(_as_india)]
"""A punch time. Daily attendance works in Indian clock time (punched_at, hr.attendance.check_in_at,
shift start/end), so these are sent with +05:30. Sent as UTC, the browser showed them 5.5 h late."""

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


class AttendancePunchLocationOut(ApiModel):
    """Where a mobile face punch was made; null for biometric punches."""

    latitude: float
    longitude: float
    accuracy_m: float | None
    place: str | None
    """Nearest work location of the employee's policy."""
    inside_office: bool | None
    distance_m: float | None
    fake_gps: bool


class AttendancePunchOut(ApiModel):
    kind: PunchKind
    at: IndiaDateTime
    device: str
    location: AttendancePunchLocationOut | None = None


class AttendanceHistoryOut(ApiModel):
    date: date
    status: AttendanceDisplayStatus
    first_in: IndiaDateTime | None = None
    last_out: IndiaDateTime | None = None
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
    first_in: IndiaDateTime | None = None
    last_out: IndiaDateTime | None = None
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
    first_in: IndiaDateTime | None = None
    last_out: IndiaDateTime | None = None
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


ResolvedAttendanceStatus = Literal["Present", "Absent", "Half day", "On duty"]


class ResolveExceptionIn(InputModel):
    remark: str | None = Field(None, max_length=300)
    """Required for Missing Punch / Absent — no silent LOP policy is configured."""
    resolved_status: ResolvedAttendanceStatus | None = Field(None, alias="resolvedStatus")


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
    original_in: IndiaDateTime | None = None
    original_out: IndiaDateTime | None = None
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


# ---------------------------------------------------------------------------
# Shift master, attendance rules, shift assignment, leave-year context
# ---------------------------------------------------------------------------

WeekdayCode = Literal["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
LeaveYearBasis = Literal["FINANCIAL", "CALENDAR"]


class ShiftWrite(InputModel):
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=60)
    start_time: time = Field(alias="startTime")
    end_time: time = Field(alias="endTime")
    grace_minutes: int = Field(10, alias="graceMinutes", ge=0, le=240)
    half_day_hours: float | None = Field(None, alias="halfDayHours", ge=0, le=24)
    is_active: bool = True


class ShiftItem(ApiModel):
    id: int
    code: str
    name: str
    start_time: time
    end_time: time
    work_hours: str
    grace_minutes: int
    half_day_hours: float | None = None
    is_active: bool
    is_overnight: bool
    row_version: RowVersion


class ShiftSummary(ApiModel):
    total: int
    active: int
    inactive: int


class ShiftListQuery(PageQuery):
    active_only: bool | None = None


class ShiftPage(ApiModel):
    items: list[ShiftItem]
    summary: ShiftSummary
    total: int
    page: int
    page_size: int


class AttendanceRulesOut(ApiModel):
    standard_work_hours: float
    working_days_per_week: int
    late_arrival_grace_minutes: int
    early_exit_grace_minutes: int
    grace_days_per_month: int
    ot_after_hours: float
    ot_approval_required: bool
    weekly_off_days: list[WeekdayCode]
    weekly_off_applies_to: str
    auto_attendance_enabled: bool
    manual_attendance_enabled: bool
    leave_year_label: str
    holiday_count: int
    row_version: RowVersion | None = None


class AttendanceRulesWrite(InputModel):
    standard_work_hours: float = Field(alias="standardWorkHours", gt=0, le=24)
    working_days_per_week: int = Field(alias="workingDaysPerWeek", ge=1, le=7)
    late_arrival_grace_minutes: int = Field(alias="lateArrivalGraceMinutes", ge=0, le=240)
    early_exit_grace_minutes: int = Field(alias="earlyExitGraceMinutes", ge=0, le=240)
    ot_after_hours: float = Field(alias="otAfterHours", gt=0, le=24)
    ot_approval_required: bool = Field(alias="otApprovalRequired")
    weekly_off_days: list[WeekdayCode] = Field(alias="weeklyOffDays")
    weekly_off_applies_to: str = Field("All Employees", alias="weeklyOffAppliesTo", max_length=80)
    auto_attendance_enabled: bool = Field(alias="autoAttendanceEnabled")
    manual_attendance_enabled: bool = Field(alias="manualAttendanceEnabled")


class LeaveYearOut(ApiModel):
    year_basis: LeaveYearBasis
    year: int
    label: str
    start_date: date
    end_date: date


class ShiftAssignmentWrite(InputModel):
    employee_id: int = Field(alias="employeeId", gt=0)
    shift_id: int = Field(alias="shiftId", gt=0)
    from_date: date = Field(alias="fromDate")
    to_date: date | None = Field(None, alias="toDate")
    weekly_off_days: list[WeekdayCode] | None = Field(None, alias="weeklyOffDays")
    is_active: bool = True


class ShiftAssignmentItem(ApiModel):
    id: int
    employee_id: int
    employee_code: str
    employee_name: str
    department: str
    shift_id: int
    shift_code: str
    shift_name: str
    weekly_off_days: list[WeekdayCode]
    from_date: date
    to_date: date | None
    is_current: bool
    is_active: bool
    row_version: RowVersion


class ShiftAssignmentListQuery(PageQuery):
    current_only: bool = True
    employee_id: int | None = Field(None, gt=0)
    shift_id: int | None = Field(None, gt=0)


class ShiftAssignmentPage(ApiModel):
    items: list[ShiftAssignmentItem]
    total: int
    page: int
    page_size: int


class ShiftAssignmentEmployeeOption(ApiModel):
    id: int
    employee_code: str
    employee_name: str
    department: str


class ShiftAssignmentOptions(ApiModel):
    employees: list[ShiftAssignmentEmployeeOption]
    shifts: list[ShiftItem]


class AttendanceHolidayItem(ApiModel):
    id: int
    holiday_date: date
    name: str
    holiday_type: Literal["National", "Festival", "Optional"]
    category: Literal["National", "Regional", "Optional"]
    applies_to: str
    is_active: bool


class AttendanceHolidayPage(ApiModel):
    leave_year: LeaveYearOut
    items: list[AttendanceHolidayItem]
    total: int


# ---------------------------------------------------------------------------
# Monthly attendance finalization
# ---------------------------------------------------------------------------

FinalizationGroupBy = Literal["department", "location"]
FinalizationRowStatus = Literal["Ready", "Review", "Pending"]


class FinalizationQuery(ApiModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    group_by: FinalizationGroupBy = "department"


class FinalizationKpiOut(ApiModel):
    total_employees: int
    attendance_ready: int
    with_exceptions: int
    pending_regularization: int
    finalized: int


class FinalizationSummaryOut(ApiModel):
    year: int
    month: int
    month_label: str
    total_employees: int
    attendance_ready: int
    attendance_ready_pct: float
    with_exceptions: int
    with_exceptions_pct: float
    pending_regularization: int
    pending_regularization_pct: float
    is_finalized: bool
    finalized_at: UtcDateTime | None = None
    finalized_by_user_id: int | None = None


class FinalizationChecklistItemOut(ApiModel):
    id: str
    label: str
    done: bool
    detail: str = ""


class FinalizationGroupRowOut(ApiModel):
    id: int
    name: str
    employees: int
    present: int
    absent: int
    leave: int
    exceptions: int
    pending_regularization: int
    readiness: int
    status: FinalizationRowStatus


class FinalizationPageOut(ApiModel):
    year: int
    month: int
    group_by: FinalizationGroupBy
    kpi: FinalizationKpiOut
    summary: FinalizationSummaryOut
    checklist: list[FinalizationChecklistItemOut]
    groups: list[FinalizationGroupRowOut]
    can_finalize: bool
    is_finalized: bool


class FinalizationLockOut(ApiModel):
    year: int
    month: int
    month_label: str
    is_finalized: bool
    finalized_at: UtcDateTime | None = None
    finalized_by_user_id: int | None = None
    employee_count: int
    message: str
    persisted_days: int = 0


# ---------------------------------------------------------------------------
# Attendance dashboard + ESS mine + reports summary
# ---------------------------------------------------------------------------


class DashboardKpiOut(ApiModel):
    total: int
    present: int
    present_pct: float
    absent: int
    absent_pct: float
    on_leave: int = 0
    late: int
    late_pct: float
    early_exit: int
    early_exit_pct: float
    short_hours: int
    short_hours_pct: float


class DashboardOverviewSliceOut(ApiModel):
    label: str
    count: int
    percent: float
    color: str


class DashboardTrendPointOut(ApiModel):
    label: str
    percent: float
    date: date
    present: int = 0
    absent: int = 0
    on_leave: int = 0


class DashboardDepartmentRowOut(ApiModel):
    id: int
    department: str
    employees: int
    present: int
    absent: int
    attendance_pct: float


class DashboardLocationRowOut(ApiModel):
    location: str
    employees: int
    present: int
    absent: int
    attendance_pct: float


class DashboardExceptionItemOut(ApiModel):
    id: str
    label: str
    count: int
    tone: str
    icon: str
    route: str


class DashboardQuickActionOut(ApiModel):
    id: str
    label: str
    icon: str
    route: str


class AttendanceDashboardOut(ApiModel):
    date: date
    date_label: str
    attendance_rate: float
    kpi: DashboardKpiOut
    overview: list[DashboardOverviewSliceOut]
    trend: list[DashboardTrendPointOut]
    departments: list[DashboardDepartmentRowOut]
    locations: list[DashboardLocationRowOut] = []
    department_options: list[str] = []
    location_options: list[str] = []
    exceptions: list[DashboardExceptionItemOut]
    exceptions_total: int
    actions: list[DashboardQuickActionOut]
    is_month_finalized: bool


class MineAttendanceDayOut(ApiModel):
    date: date
    status: AttendanceDisplayStatus
    first_in: str | None = None
    last_out: str | None = None
    working_hours: str | None = None
    shift: str
    remarks: str = ""


class MineAttendanceSummaryOut(ApiModel):
    present: int
    late: int
    absent: int
    on_leave: int
    off_day: int
    holiday: int
    missing_punch: int


class MineAttendancePageOut(ApiModel):
    employee_id: int
    employee_code: str
    employee_name: str
    year: int
    month: int
    month_label: str
    summary: MineAttendanceSummaryOut
    items: list[MineAttendanceDayOut]
    regularizations: list[RegularizationRowOut] = []
    is_month_finalized: bool
    can_regularize: bool = True


class AttendanceReportsSummaryOut(ApiModel):
    year: int
    month: int
    month_label: str
    total_employees: int
    present: int
    late: int
    absent: int
    on_leave: int
    wfh: int
    pending_exceptions: int
    pending_regularizations: int
    is_month_finalized: bool
    finalized_at: UtcDateTime | None = None
