"""Leave type and policy requests. JSON is camelCase."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion
from trishul_api.db.models.generated.core import EmployeeEmployeeType

AccrualFrequency = Literal["None", "Monthly", "Yearly"]
StatusFilter = Literal["active", "inactive", "all"]
YearBasis = Literal["FINANCIAL", "CALENDAR"]
AssignmentMode = Literal["AUTOMATIC", "EXPLICIT"]
CalculationMethod = Literal["FIXED", "FORMULA", "ELIGIBILITY"]
JoiningYearRule = Literal["NONE", "TWO_THIRDS_REMAINDER"]
BenefitClass = Literal["STANDARD", "STATUTORY", "COMPANY"]
CompensatoryBasis = Literal["NONE", "STATUTORY_WEEKLY_REST", "COMPANY_COMP_OFF"]
AttendanceStatusName = Literal["Present", "Absent", "Half day", "Leave", "Holiday", "Week off", "On duty"]


class LeaveTypeQuery(PageQuery):
    status: StatusFilter = "all"


class LeaveTypeWrite(InputModel):
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=60)
    description: str | None = Field(None, max_length=400)
    annual_quota: Decimal | None = Field(None, ge=0, max_digits=5, decimal_places=1)
    carry_forward_max: Decimal | None = Field(None, ge=0, max_digits=5, decimal_places=1)
    is_paid: bool = True
    is_encashable: bool = False
    accrual_applicable: bool = False
    half_day_allowed: bool = True
    attachment_required: bool = False
    max_consecutive_days: int | None = Field(None, ge=1, le=366)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def upper_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name", "description")
    @classmethod
    def trimmed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class LeaveTypeItem(ApiModel):
    id: int
    code: str
    name: str
    description: str | None
    annual_quota: Decimal | None
    carry_forward_max: Decimal | None
    is_paid: bool
    is_encashable: bool
    accrual_applicable: bool
    half_day_allowed: bool
    attachment_required: bool
    max_consecutive_days: int | None
    is_active: bool
    row_version: RowVersion


class LeavePolicyLineWrite(InputModel):
    leave_type_id: int = Field(gt=0)
    annual_entitlement: Decimal = Field(ge=0, max_digits=6, decimal_places=1)
    accrual_frequency: AccrualFrequency = "None"
    carry_forward: bool = False
    max_accumulation: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=1)
    encashment_eligible: bool = False
    calculation_method: CalculationMethod = "FIXED"
    credit_days: Decimal | None = Field(None, gt=0, max_digits=6, decimal_places=1)
    qualifying_days_per_credit: int | None = Field(None, gt=0, le=366)
    minimum_qualifying_days: int | None = Field(None, ge=0, le=366)
    joining_year_rule: JoiningYearRule = "NONE"
    minimum_service_months: int | None = Field(None, ge=0, le=600)
    adolescent_max_accumulation: Decimal | None = Field(None, ge=0, max_digits=6, decimal_places=1)
    exclude_boundary_holidays: bool = False
    document_required: bool = False
    benefit_class: BenefitClass = "STANDARD"
    compensatory_basis: CompensatoryBasis = "NONE"
    compensatory_expiry_months: int | None = Field(None, ge=1, le=36)
    max_backdate_days: int | None = Field(None, ge=0, le=366)
    backdate_requires_authorization: bool = False


class LeavePolicyWrite(InputModel):
    name: str = Field(min_length=1, max_length=80)
    employee_type: EmployeeEmployeeType | None = None
    department_id: int | None = Field(None, gt=0)
    branch_id: int | None = Field(None, gt=0)
    state_id: int | None = Field(None, gt=0)
    year_basis: YearBasis = "FINANCIAL"
    assignment_mode: AssignmentMode = "AUTOMATIC"
    applies_during_probation: bool = False
    negative_balance_allowed: bool = False
    effective_from: date
    effective_to: date | None = None
    is_active: bool = True
    lines: list[LeavePolicyLineWrite] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def trimmed_name(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Policy name is required.")
        return text

    @model_validator(mode="after")
    def dates_in_order(self) -> "LeavePolicyWrite":
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("Effective to must be later than effective from.")
        ids = [line.leave_type_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Each leave type can appear once in a policy.")
        for line in self.lines:
            _validate_line(line)
        return self


class LeavePolicyLineItem(ApiModel):
    id: int
    leave_type_id: int
    leave_type_code: str
    leave_type_name: str
    annual_entitlement: Decimal
    accrual_frequency: AccrualFrequency
    carry_forward: bool
    max_accumulation: Decimal | None
    encashment_eligible: bool
    calculation_method: CalculationMethod
    credit_days: Decimal | None
    qualifying_days_per_credit: int | None
    minimum_qualifying_days: int | None
    joining_year_rule: JoiningYearRule
    minimum_service_months: int | None
    adolescent_max_accumulation: Decimal | None
    exclude_boundary_holidays: bool
    document_required: bool
    benefit_class: BenefitClass
    compensatory_basis: CompensatoryBasis
    compensatory_expiry_months: int | None
    max_backdate_days: int | None
    backdate_requires_authorization: bool
    rule_summary: list[str]


class LeavePolicyItem(ApiModel):
    id: int
    name: str
    employee_type: str | None
    department_id: int | None
    department_name: str | None
    branch_id: int | None
    branch_name: str | None
    state_id: int | None
    state_name: str | None
    year_basis: YearBasis
    assignment_mode: AssignmentMode
    applies_during_probation: bool
    negative_balance_allowed: bool
    effective_from: date
    effective_to: date | None
    is_active: bool
    lines: list[LeavePolicyLineItem]
    row_version: RowVersion


class LeavePolicyQuery(PageQuery):
    status: StatusFilter = "all"
    department_id: int | None = Field(None, gt=0)
    branch_id: int | None = Field(None, gt=0)


class LeaveAssignmentWrite(InputModel):
    employee_id: int = Field(gt=0)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def dates_in_order(self) -> "LeaveAssignmentWrite":
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("Effective to must be later than effective from.")
        return self


class LeaveAssignmentItem(ApiModel):
    id: int
    leave_policy_id: int
    employee_id: int
    employee_code: str
    employee_name: str
    effective_from: date
    effective_to: date | None
    is_active: bool


class AttendanceClassWrite(InputModel):
    attendance_status: AttendanceStatusName
    counts_for_eligibility: bool = False
    counts_as_days_worked: bool = False
    is_deemed_work: bool = False
    day_weight: Decimal | None = Field(None, gt=0, max_digits=3, decimal_places=1)

    @model_validator(mode="after")
    def split_worked_and_deemed(self) -> "AttendanceClassWrite":
        if self.counts_as_days_worked and self.is_deemed_work:
            raise ValueError("A status cannot both earn Earned Leave and be deemed work.")
        counted = self.counts_for_eligibility or self.counts_as_days_worked or self.is_deemed_work
        if counted and self.day_weight is None:
            raise ValueError("Enter the day weight for a status that counts. It is not assumed.")
        return self


class AttendanceClassItem(ApiModel):
    attendance_status: AttendanceStatusName
    counts_for_eligibility: bool
    counts_as_days_worked: bool
    is_deemed_work: bool
    day_weight: Decimal | None
    configured: bool


class EntitlementPreviewQuery(InputModel):
    employee_id: int = Field(gt=0)
    attendance_year: int = Field(ge=2000, le=2100)


class EntitlementPreview(ApiModel):
    attendance_year: int
    available_in_year: int
    eligibility_days: Decimal
    days_worked: Decimal
    deemed_days: Decimal
    credited_days: Decimal
    threshold: int


class WeeklyRestGrantWrite(InputModel):
    employee_id: int = Field(gt=0)
    leave_policy_line_id: int = Field(gt=0)
    original_holiday_date: date
    granted_on: date
    days: Decimal = Field(gt=0, max_digits=4, decimal_places=1)


class WeeklyRestGrantItem(ApiModel):
    id: int
    employee_id: int
    leave_policy_line_id: int
    original_holiday_date: date
    granted_on: date
    expires_on: date
    days: Decimal


def _validate_line(line: LeavePolicyLineWrite) -> None:
    if line.calculation_method == "FORMULA":
        if line.annual_entitlement != 0:
            raise ValueError("A formula entitlement does not take a fixed day count.")
        if line.credit_days is None or line.qualifying_days_per_credit is None or line.minimum_qualifying_days is None:
            raise ValueError("A formula needs the credit, the days worked per credit, and the eligibility minimum.")
    elif line.calculation_method == "ELIGIBILITY" and line.annual_entitlement <= 0:
        raise ValueError("An eligibility entitlement needs a cap greater than zero.")
    if line.compensatory_basis == "STATUTORY_WEEKLY_REST" and line.compensatory_expiry_months is None:
        raise ValueError("Statutory weekly rest needs an expiry counted in calendar months.")
    if line.carry_forward and line.max_accumulation is None and line.adolescent_max_accumulation is None:
        raise ValueError("Carry forward needs a maximum.")
