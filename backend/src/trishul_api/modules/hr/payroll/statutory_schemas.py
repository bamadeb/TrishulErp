"""Statutory rules and the monthly compliance view. Rates are entered, never assumed."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models.generated.hr import StatutoryConfigConfigType

Scheme = Literal["PF", "ESI", "PT", "TDS"]
ConfigurationStatus = Literal["Configured", "Partial", "Not configured"]
SchemeConfigurationStatus = Literal["Configured", "Not configured"]
CalculationStatus = Literal["Calculated", "Not calculated", "Not applicable"]
FilingStatus = Literal["Not filed"]


class StatutorySummaryQuery(ApiModel):
    month: date
    scheme: Scheme | None = None


class StateChoice(ApiModel):
    id: int
    name: str


class DepartmentChoice(ApiModel):
    id: int
    name: str


class StatutorySchemeStatus(ApiModel):
    scheme: Scheme
    name: str
    configuration_status: SchemeConfigurationStatus
    calculation_status: CalculationStatus
    filing_status: FilingStatus


class StatutorySummary(ApiModel):
    month: date
    financial_year: str
    eligible_employees: int
    employee_contribution: Decimal | None
    employer_contribution: Decimal | None
    total_liability: Decimal | None
    configuration_status: ConfigurationStatus
    calculation_status: CalculationStatus
    filing_status: FilingStatus
    schemes: list[StatutorySchemeStatus]
    states: list[StateChoice]
    departments: list[DepartmentChoice]


class StatutoryRule(ApiModel):
    id: int
    config_type: StatutoryConfigConfigType
    state_id: int | None
    state_name: str | None
    effective_from: date
    effective_to: date | None
    employee_rate: Decimal | None
    employer_rate: Decimal | None
    wage_ceiling: Decimal | None
    slab_json: str | None
    is_active: bool
    created_at: UtcDateTime
    created_by: str | None
    updated_at: UtcDateTime | None
    updated_by: str | None
    row_version: RowVersion


class StatutoryRuleWrite(InputModel):
    config_type: Scheme
    state_id: int | None = None
    effective_from: date
    employee_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    employer_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    wage_ceiling: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    slab_json: str | None = Field(default=None, max_length=4000)
    is_active: bool = True


class StatutoryContributionQuery(PageQuery):
    month: date
    scheme: Scheme
    department_id: int | None = None
    state_id: int | None = None


class StatutoryContribution(ApiModel):
    employee_id: int
    employee_code: str
    full_name: str
    department: str | None
    location: str | None
    applicable_wages: Decimal | None
    employee_contribution: Decimal | None
    employer_contribution: Decimal | None
    total_contribution: Decimal | None
    calculation_status: CalculationStatus
    reason: str | None = None
