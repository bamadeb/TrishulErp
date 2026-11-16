"""Employee leave register contracts. Balances are the stored hr.leave_balance rows."""

from datetime import date
from decimal import Decimal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, PageQuery

_ZERO = Decimal("0.0")


class EmployeeLeaveQuery(PageQuery):
    financial_year: int = Field(ge=2000, le=2100)
    department_id: int | None = Field(default=None, gt=0)
    designation_id: int | None = Field(default=None, gt=0)
    branch_id: int | None = Field(default=None, gt=0)


class EmployeeLeaveOption(ApiModel):
    id: int
    name: str


class EmployeeLeaveStats(ApiModel):
    employees: int
    on_leave: int
    upcoming: int
    taken: Decimal
    departments: list[EmployeeLeaveOption]
    designations: list[EmployeeLeaveOption]
    locations: list[EmployeeLeaveOption]


class EmployeeLeaveSpan(ApiModel):
    request_id: int
    display_id: str
    leave_code: str
    from_date: date
    to_date: date
    days: Decimal


class EmployeeUpcomingLeave(EmployeeLeaveSpan):
    employee_id: int
    code: str
    name: str


class EmployeeLeaveBalanceView(ApiModel):
    opening: Decimal = _ZERO
    credited: Decimal = _ZERO
    consumed: Decimal = _ZERO
    adjustments: Decimal = _ZERO
    expired: Decimal = _ZERO
    closing: Decimal = _ZERO


class EmployeeLeaveRow(ApiModel):
    employee_id: int
    code: str
    name: str
    department: str | None
    designation: str | None
    location: str | None
    status: str
    date_of_joining: date | None
    cl: Decimal = _ZERO
    el: Decimal = _ZERO
    sl: Decimal = _ZERO
    co: Decimal = _ZERO
    taken: Decimal = _ZERO
    upcoming: EmployeeLeaveSpan | None = None
    on_leave_today: bool = False


class EmployeeLeaveHistoryItem(ApiModel):
    request_id: int
    display_id: str
    leave_code: str
    leave_type: str
    from_date: date
    to_date: date
    days: Decimal
    status: str
    approved_by: str | None


class EmployeeLeaveDetail(EmployeeLeaveRow):
    last_leave: EmployeeLeaveSpan | None = None
    balances: dict[str, EmployeeLeaveBalanceView]
    history: list[EmployeeLeaveHistoryItem]


class EmployeeLeavePage(ApiModel):
    items: list[EmployeeLeaveRow]
    total: int
    page: int
    page_size: int
