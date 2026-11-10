"""Employee salary structure requests and responses. JSON is camelCase."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion
from trishul_api.db.models.generated.hr import (
    SalaryComponentCalculationBasis,
    SalaryComponentCalculationType,
)
from trishul_api.modules.hr.payroll.schemas import ComponentType

StructureFilter = Literal["all", "assigned", "unassigned"]


class SalaryStructureQuery(PageQuery):
    """Employees, with the current salary structure when one is saved."""

    assignment: StructureFilter = "all"


class SalaryStructureSummary(ApiModel):
    employees: int
    assigned: int
    unassigned: int
    active: int


class SalaryStructureListItem(ApiModel):
    employee_id: int
    employee_code: str
    full_name: str
    department: str | None
    designation: str | None
    status: str
    structure_id: int | None
    effective_from: date | None
    effective_to: date | None
    annual_ctc: Decimal | None
    monthly_gross: Decimal | None
    row_version: RowVersion | None


class SalaryStructureLineItem(ApiModel):
    salary_component_id: int
    code: str
    name: str
    component_type: ComponentType
    calculation_method: SalaryComponentCalculationType
    calculation_basis: SalaryComponentCalculationBasis | None
    included: bool
    monthly_amount: Decimal | None
    percentage: Decimal | None
    formula: str | None
    include_in_net_pay: bool


class SalaryStructureDetail(ApiModel):
    employee_id: int
    employee_code: str
    full_name: str
    department: str | None
    designation: str | None
    structure_id: int | None
    effective_from: date | None
    effective_to: date | None
    annual_ctc: Decimal | None
    monthly_gross: Decimal | None
    row_version: RowVersion | None
    lines: list[SalaryStructureLineItem]


class SalaryStructureLineWrite(InputModel):
    salary_component_id: int = Field(gt=0)
    included: bool = True
    monthly_amount: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    percentage: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    formula: str | None = Field(None, max_length=300)

    @field_validator("formula")
    @classmethod
    def blank_formula(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class SalaryStructureWrite(InputModel):
    effective_from: date
    effective_to: date | None = None
    annual_ctc: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    monthly_gross: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    lines: list[SalaryStructureLineWrite]

    @model_validator(mode="after")
    def dates_in_order(self) -> "SalaryStructureWrite":
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("Effective to must be later than effective from.")
        return self
