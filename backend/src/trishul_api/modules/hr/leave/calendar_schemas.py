"""Leave calendar contracts. Counts and entries come from the existing leave tables."""

from datetime import date
from decimal import Decimal

from pydantic import Field

from trishul_api.common.schemas import ApiModel
from trishul_api.modules.hr.leave.employee_schemas import EmployeeLeaveOption

_ZERO = Decimal("0.00")


class LeaveCalendarQuery(ApiModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    department_id: int | None = Field(default=None, gt=0)
    designation_id: int | None = Field(default=None, gt=0)
    branch_id: int | None = Field(default=None, gt=0)
    leave_type_id: int | None = Field(default=None, gt=0)
    search: str | None = Field(default=None, max_length=100)


class LeaveCalendarSummary(ApiModel):
    total_employees: int
    on_leave_today: int
    on_leave_percent: Decimal = _ZERO
    pending_approval: int
    approved_mtd: int
    rejected_mtd: int
    upcoming_leaves: int


class LeaveCalendarEmployee(ApiModel):
    employee_id: int
    code: str
    name: str
    department: str | None
    designation: str | None
    location: str | None
    status: str


class LeaveCalendarTypeOption(ApiModel):
    id: int
    code: str
    name: str


class LeaveCalendarEntry(ApiModel):
    request_id: int
    display_id: str
    employee: LeaveCalendarEmployee
    leave_code: str
    leave_type: str
    from_date: date
    to_date: date
    days: Decimal
    status: str
    reason: str | None
    approved_by: str | None


class LeaveCalendarHoliday(ApiModel):
    holiday_date: date
    name: str


class LeaveCalendarBoard(ApiModel):
    summary: LeaveCalendarSummary
    entries: list[LeaveCalendarEntry]
    holidays: list[LeaveCalendarHoliday]
    departments: list[EmployeeLeaveOption]
    designations: list[EmployeeLeaveOption]
    locations: list[EmployeeLeaveOption]
    leave_types: list[LeaveCalendarTypeOption]
