"""Leave balance board contracts."""

from datetime import date
from decimal import Decimal

from pydantic import Field, model_validator

from trishul_api.common.schemas import ApiModel, InputModel

_ZERO = Decimal("0.0")


class BalanceBucket(ApiModel):
    opening: Decimal = _ZERO
    credited: Decimal = _ZERO
    used: Decimal = _ZERO
    balance: Decimal = _ZERO


class BalanceEmployee(ApiModel):
    employee_id: int
    employee_code: str
    employee_name: str
    department: str | None
    designation: str | None
    el: BalanceBucket
    sl: BalanceBucket
    cl: BalanceBucket
    comp_off_balance: Decimal = _ZERO


class BalanceSummary(ApiModel):
    total_employees: int
    with_assigned_policy: int
    entitlement_generated: int
    requires_review: int


class BalanceBoard(ApiModel):
    year: int
    policy_id: int | None
    policy_name: str | None
    warning: str | None
    summary: BalanceSummary
    items: list[BalanceEmployee]
    total: int
    page: int
    page_size: int


class BalanceTransactionItem(ApiModel):
    id: int
    code: str
    on: date
    kind: str
    days: Decimal
    reference: str | None
    remarks: str | None


class BalanceTypeDetail(ApiModel):
    code: str
    name: str
    leave_type_id: int | None
    opening: Decimal
    annual_entitlement: Decimal | None
    credited: Decimal
    consumed: Decimal
    adjustments: Decimal
    expired: Decimal
    closing: Decimal


class BalanceLeaveHistory(ApiModel):
    id: int
    code: str
    from_date: date
    to_date: date
    days: Decimal
    status: str


class BalanceDetail(ApiModel):
    employee_id: int
    employee_code: str
    employee_name: str
    year: int
    types: list[BalanceTypeDetail]
    transactions: list[BalanceTransactionItem]
    leave_history: list[BalanceLeaveHistory] = Field(default_factory=list)


class BalanceAdjustment(InputModel):
    leave_type_id: int = Field(gt=0)
    year: int = Field(ge=2000, le=2100)
    days: Decimal = Field(max_digits=6, decimal_places=1)
    reason: str = Field(min_length=3, max_length=300)

    @model_validator(mode="after")
    def not_zero(self) -> "BalanceAdjustment":
        if self.days == 0:
            raise ValueError("Enter an adjustment other than zero.")
        return self


class EntitlementPreviewRequest(InputModel):
    policy_id: int = Field(gt=0)
    year: int = Field(ge=2000, le=2100)
    generation_type: str = "Annual"


class EntitlementPreviewLine(ApiModel):
    code: str
    credited: Decimal = _ZERO
    eligibility_days: Decimal | None = None
    days_worked: Decimal | None = None
    deemed_days: Decimal | None = None
    threshold: int | None = None
    blocked: bool = False
    review: bool = False
    message: str | None = None


class EntitlementPreviewEmployee(ApiModel):
    employee_id: int
    employee_code: str
    employee_name: str
    lines: list[EntitlementPreviewLine]
    requires_review: bool


class EntitlementPreviewBoard(ApiModel):
    policy_id: int
    policy_name: str
    year: int
    warning: str | None
    employees: list[EntitlementPreviewEmployee]


class EntitlementGenerateResult(ApiModel):
    credited_employees: int
    skipped_duplicates: int
    blocked: int
