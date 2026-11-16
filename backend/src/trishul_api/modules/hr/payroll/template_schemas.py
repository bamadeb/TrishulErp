"""Salary template requests and responses. JSON is camelCase."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion
from trishul_api.db.models.generated.core import EmployeeEmployeeType
from trishul_api.modules.hr.payroll.schemas import ComponentType

TemplateType = Literal["Monthly"]
TemplateStatus = Literal["all", "active", "inactive"]


class NamedOption(ApiModel):
    id: int
    name: str


class SalaryTemplateQuery(PageQuery):
    status: TemplateStatus = "all"
    department_id: int | None = Field(None, gt=0)
    designation_id: int | None = Field(None, gt=0)
    grade: str | None = Field(None, max_length=10)
    employee_category: EmployeeEmployeeType | None = None


class SalaryTemplateSummary(ApiModel):
    total: int
    active: int
    inactive: int
    assigned_employees: int
    departments: list[NamedOption]
    designations: list[NamedOption]


class SalaryTemplateLineWrite(InputModel):
    salary_component_id: int = Field(gt=0)
    monthly_amount: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    percentage: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    formula: str | None = Field(None, max_length=300)
    display_order: int = Field(0, ge=0)

    @field_validator("formula")
    @classmethod
    def blank_formula(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class SalaryTemplateWrite(InputModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(None, max_length=400)
    template_type: TemplateType = "Monthly"
    employee_category: EmployeeEmployeeType | None = None
    department_id: int | None = Field(None, gt=0)
    designation_id: int | None = Field(None, gt=0)
    designation_ids: list[int] = Field(default_factory=list)
    grades: list[str] = Field(default_factory=list)
    effective_from: date
    effective_to: date | None = None
    is_active: bool = True
    lines: list[SalaryTemplateLineWrite]

    @model_validator(mode="after")
    def dates_in_order(self) -> "SalaryTemplateWrite":
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("Effective to must be later than effective from.")
        return self


class SalaryTemplateStatusWrite(InputModel):
    is_active: bool


class SalaryTemplateLineItem(ApiModel):
    salary_component_id: int
    code: str
    name: str
    component_type: ComponentType
    calculation_method: str
    calculation_basis: str | None
    monthly_amount: Decimal | None
    percentage: Decimal | None
    formula: str | None
    display_order: int
    estimated_amount: Decimal | None


class SalaryTemplateEmployee(ApiModel):
    employee_id: int
    employee_code: str
    full_name: str
    department: str | None
    effective_from: date
    effective_to: date | None
    monthly_gross: Decimal


class SalaryTemplateHistoryItem(ApiModel):
    action: str
    changed_at: date
    changed_by: str | None
    summary: str


class SalaryTemplateListItem(ApiModel):
    id: int
    code: str
    name: str
    description: str | None
    employee_category: str | None
    department: str | None
    designation: str | None
    designation_ids: list[int] = Field(default_factory=list)
    grades: list[str] = Field(default_factory=list)
    assigned_employees: int
    is_active: bool
    row_version: RowVersion


class SalaryTemplateDetail(SalaryTemplateListItem):
    template_type: TemplateType
    department_id: int | None
    designation_id: int | None
    effective_from: date
    effective_to: date | None
    monthly_gross: Decimal
    employee_deductions: Decimal
    net_salary: Decimal
    employer_contribution: Decimal
    annual_ctc: Decimal
    lines: list[SalaryTemplateLineItem]
    employees: list[SalaryTemplateEmployee]
    history: list[SalaryTemplateHistoryItem]
