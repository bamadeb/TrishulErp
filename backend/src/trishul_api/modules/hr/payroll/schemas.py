"""Salary component requests and responses. JSON is camelCase."""

import re
from datetime import date
from decimal import Decimal
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models.generated.hr import (
    SalaryComponentCalculationBasis,
    SalaryComponentCalculationType,
    SalaryComponentComponentType,
)

ComponentType = SalaryComponentComponentType
CalculationMethod = SalaryComponentCalculationType
CalculationBasis = SalaryComponentCalculationBasis
StatusFilter = Literal["active", "inactive", "all"]

_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,19}")


class SalaryComponentQuery(PageQuery):
    """List filters. Search matches the code and the name."""

    component_type: ComponentType | None = None
    calculation_method: CalculationMethod | None = None
    status: StatusFilter = "all"


class SalaryComponentSummary(ApiModel):
    total: int
    earning: int
    deduction: int
    active: int


class SalaryComponentAuditItem(ApiModel):
    action: str
    changed_at: UtcDateTime
    changed_by: str | None


class SalaryComponentListItem(ApiModel):
    id: int
    code: str
    name: str
    component_type: ComponentType
    calculation_method: CalculationMethod
    calculation_basis: CalculationBasis | None
    include_in_gross: bool
    is_taxable: bool
    is_pf_applicable: bool
    is_esi_applicable: bool
    is_active: bool
    effective_from: date
    effective_to: date | None
    row_version: RowVersion


class SalaryComponentRevisionItem(ApiModel):
    revision_no: int
    calculation_method: CalculationMethod
    calculation_basis: CalculationBasis | None
    effective_from: date
    effective_to: date | None
    superseded_at: UtcDateTime


class SalaryComponentDetail(SalaryComponentListItem):
    description: str | None
    display_order: int
    fixed_amount: Decimal | None
    percentage: Decimal | None
    formula: str | None
    is_prorated: bool
    allow_manual_override: bool
    include_in_net_pay: bool
    allow_reversal: bool
    display_in_statement: bool
    display_in_payslip: bool
    in_use: bool
    rules_locked: bool
    created_at: UtcDateTime
    created_by: str | None
    updated_at: UtcDateTime | None
    updated_by: str | None
    revisions: list[SalaryComponentRevisionItem]
    audit: list[SalaryComponentAuditItem]


class SalaryComponentWrite(InputModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=80)
    component_type: ComponentType
    description: str | None = Field(None, max_length=400)
    display_order: int = Field(0, ge=0, le=9999)
    calculation_method: CalculationMethod
    calculation_basis: CalculationBasis | None = None
    fixed_amount: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    percentage: Decimal | None = Field(None, ge=0, le=100, max_digits=7, decimal_places=4)
    formula: str | None = Field(None, max_length=300)
    is_prorated: bool = False
    allow_manual_override: bool = False
    include_in_gross: bool = False
    is_taxable: bool = False
    is_pf_applicable: bool = False
    is_esi_applicable: bool = False
    include_in_net_pay: bool = True
    allow_reversal: bool = False
    display_in_statement: bool = True
    display_in_payslip: bool = True
    effective_from: date
    effective_to: date | None = None
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def code_shape(cls, value: str) -> str:
        value = value.upper()
        if _CODE.fullmatch(value) is None:
            raise ValueError("Use letters, digits and underscores, starting with a letter.")
        return value

    @field_validator("description", "formula")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @model_validator(mode="after")
    def dates_in_order(self) -> Self:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("Effective to cannot be earlier than effective from.")
        return self


class SalaryComponentUpdate(InputModel):
    """Only the fields sent are changed."""

    code: str | None = Field(None, min_length=1, max_length=20)
    name: str | None = Field(None, min_length=1, max_length=80)
    component_type: ComponentType | None = None
    description: str | None = Field(None, max_length=400)
    display_order: int | None = Field(None, ge=0, le=9999)
    calculation_method: CalculationMethod | None = None
    calculation_basis: CalculationBasis | None = None
    fixed_amount: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    percentage: Decimal | None = Field(None, ge=0, le=100, max_digits=7, decimal_places=4)
    formula: str | None = Field(None, max_length=300)
    is_prorated: bool | None = None
    allow_manual_override: bool | None = None
    include_in_gross: bool | None = None
    is_taxable: bool | None = None
    is_pf_applicable: bool | None = None
    is_esi_applicable: bool | None = None
    include_in_net_pay: bool | None = None
    allow_reversal: bool | None = None
    display_in_statement: bool | None = None
    display_in_payslip: bool | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def code_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.upper()
        if _CODE.fullmatch(value) is None:
            raise ValueError("Use letters, digits and underscores, starting with a letter.")
        return value

    @field_validator("description", "formula")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class SalaryComponentStatus(InputModel):
    is_active: bool
