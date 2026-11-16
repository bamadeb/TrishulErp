"""Leave dashboard query and response. Figures come from existing leave and employee rows."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel

LeaveStatus = Literal["Pending", "Approved", "Rejected", "Cancelled"]


class LeaveDashboardQuery(ApiModel):
    year: int | None = Field(None, ge=2000, le=2100)
    month: int | None = Field(None, ge=1, le=12)
    department_id: int | None = Field(None, gt=0)
    leave_type_id: int | None = Field(None, gt=0)
    status: LeaveStatus | None = None
    upcoming: bool = False
    search: str | None = Field(None, max_length=100)
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=200)
    sort: str | None = Field(None, max_length=40)


class NamedCount(ApiModel):
    name: str
    count: int


class MonthPoint(ApiModel):
    month: str
    days: Decimal


class BalanceRow(ApiModel):
    code: str
    name: str
    entitlement: Decimal
    used: Decimal
    closing: Decimal


class Overview(ApiModel):
    working: int
    on_leave: int
    pending: int


class RequestRow(ApiModel):
    request_id: int
    employee_code: str
    employee_name: str
    department: str | None
    leave_type: str
    from_date: date
    to_date: date
    days: Decimal
    reason: str | None
    status: str


class RequestPage(ApiModel):
    items: list[RequestRow]
    total: int
    page: int
    page_size: int


class MineBalance(ApiModel):
    code: str
    name: str
    closing: Decimal


class MinePanel(ApiModel):
    balances: list[MineBalance]
    requests: list[RequestRow]
    history: list[RequestRow]


class FilterOption(ApiModel):
    id: int
    name: str


class LeaveDashboard(ApiModel):
    year: int
    month: int
    as_of: date
    organisation_wide: bool
    active_employees: int
    on_leave_today: int
    pending_requests: int
    approved_requests: int
    rejected_requests: int
    upcoming_leaves: int
    overview: Overview
    trend: list[MonthPoint]
    balances: list[BalanceRow]
    requests: RequestPage
    mine: MinePanel
    department_options: list[FilterOption]
    leave_type_options: list[FilterOption]
