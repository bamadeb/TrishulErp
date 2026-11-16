"""Leave request queue models. Employee fields come from core.employee and its existing joins."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery

LeaveQueueStatus = Literal["Pending", "Approved", "Rejected"]


class LeaveRequestFilter(ApiModel):
    department_id: int | None = Field(default=None, gt=0)
    leave_type_id: int | None = Field(default=None, gt=0)
    from_date: date | None = None
    to_date: date | None = None
    search: str | None = Field(default=None, max_length=100)


class LeaveRequestQuery(LeaveRequestFilter, PageQuery):
    status: LeaveQueueStatus | None = None


class LeaveOption(ApiModel):
    id: int
    name: str


class LeaveRequestSummary(ApiModel):
    pending: int
    approved: int
    rejected: int
    total: int
    departments: list[LeaveOption]
    leave_types: list[LeaveOption]


class LeaveRequestEmployee(ApiModel):
    code: str
    name: str
    department: str | None
    designation: str | None
    location: str | None
    manager: str | None


class LeaveRequestRow(ApiModel):
    request_id: int
    display_id: str
    employee: LeaveRequestEmployee
    leave_type_id: int
    leave_type: str
    leave_code: str
    from_date: date
    to_date: date
    is_half_day: bool
    days: Decimal
    reason: str | None
    applied_on: date
    status: str
    balance: Decimal | None
    can_approve: bool


class LeaveHistoryEvent(ApiModel):
    id: int
    action: str
    actor: str
    at: date
    remarks: str


class LeaveRequestDetail(LeaveRequestRow):
    approver_user_id: int | None
    acted_at: datetime | None
    history: list[LeaveHistoryEvent]
    comments: list[str]


class LeaveRequestPage(ApiModel):
    items: list[LeaveRequestRow]
    total: int
    page: int
    page_size: int


class LeaveReject(InputModel):
    remarks: str = Field(min_length=3, max_length=500)


class LeaveComment(InputModel):
    remarks: str = Field(min_length=1, max_length=500)
