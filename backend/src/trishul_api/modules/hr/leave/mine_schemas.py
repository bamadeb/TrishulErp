"""My Leave request and response models. Fields follow the existing leave tables."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, Page, UtcDateTime

LeaveStatus = Literal["Pending", "Approved", "Rejected", "Cancelled"]
HalfDayPart = Literal["First half", "Second half"]


class MineProfile(ApiModel):
    employee_id: int
    employee_code: str
    employee_name: str
    department: str | None
    designation: str | None
    location: str | None
    date_of_joining: date | None
    confirmation_date: date | None
    employment_status: str


class MineBalance(ApiModel):
    leave_type_id: int
    code: str
    name: str
    opening: Decimal
    credited: Decimal
    availed: Decimal
    pending: Decimal
    available: Decimal
    expired: Decimal | None
    max_backdate_days: int | None = None
    backdate_requires_authorization: bool = False


class MineBalances(ApiModel):
    financial_year: int
    items: list[MineBalance]


class MineCompOff(ApiModel):
    earned: Decimal
    available: Decimal
    used: Decimal
    expiring: Decimal | None
    expiry_tracked: bool
    lines: list[str]


class MineHolidayQuery(ApiModel):
    financial_year: int = Field(ge=2000, le=2100)
    month: int | None = Field(None, ge=1, le=12)
    year: int | None = Field(None, ge=2000, le=2100)


class MineHoliday(ApiModel):
    holiday_date: date
    name: str
    holiday_type: str


class MineRequestQuery(ApiModel):
    financial_year: int = Field(ge=2000, le=2100)
    leave_type_id: int | None = Field(None, gt=0)
    status: LeaveStatus | None = None
    from_date: date | None = None
    to_date: date | None = None
    search: str | None = Field(None, max_length=100)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)


class MineStatusEvent(ApiModel):
    from_status: str | None
    to_status: str
    changed_at: datetime
    remarks: str | None


ApprovalStepStatus = Literal["Submitted", "Pending", "Approved", "Rejected", "Upcoming", "Cancelled"]


class MineApprovalStep(ApiModel):
    """One step on the approval timeline for a submitted request."""

    title: str
    approver_name: str | None
    approver_role: str | None
    level: str | None
    status: ApprovalStepStatus
    acted_at: datetime | None
    comments: str | None


class MineRequestItem(ApiModel):
    request_id: int
    display_id: str
    leave_type_id: int
    leave_type: str
    from_date: date
    to_date: date
    days: Decimal
    reason: str | None
    applied_at: UtcDateTime
    status: LeaveStatus
    is_half_day: bool
    approver_user_id: int | None
    acted_at: datetime | None
    current_approval_level: str | None
    pending_with_name: str | None = None
    pending_with_role: str | None = None
    needs_hr_attention: bool = False


class MineRequestDetail(MineRequestItem):
    history: list[MineStatusEvent]
    approval_steps: list[MineApprovalStep] = Field(default_factory=list)


class MineRequestPage(Page[MineRequestItem]):
    pass


class MineApply(InputModel):
    leave_type_id: int = Field(gt=0)
    from_date: date
    to_date: date
    is_half_day: bool = False
    half_day_part: HalfDayPart | None = None
    reason: str = Field(min_length=1, max_length=300)
    contact: str | None = Field(default=None, max_length=120)


class MineDayCount(InputModel):
    leave_type_id: int = Field(gt=0)
    from_date: date
    to_date: date
    is_half_day: bool = False
    half_day_part: HalfDayPart | None = None


class MineDayCountResult(ApiModel):
    days: Decimal
