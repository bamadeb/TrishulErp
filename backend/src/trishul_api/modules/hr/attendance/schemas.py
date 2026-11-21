"""Request and response models for Daily Attendance."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, PageQuery, UtcDateTime

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
