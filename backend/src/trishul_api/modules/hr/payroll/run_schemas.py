"""Payroll run requests and responses. JSON is camelCase."""

from datetime import date
from decimal import Decimal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel
from trishul_api.db.models.generated.hr import PayrollRunStatus


class PayrollRunRequest(InputModel):
    month: date


class PayrollLine(ApiModel):
    code: str
    name: str
    amount: Decimal
    source: str


class PayrollEmployeeDetail(ApiModel):
    employee_id: int
    employee_code: str
    full_name: str
    department: str | None
    designation: str | None
    paid_days: Decimal
    lop_days: Decimal
    gross: Decimal
    deductions: Decimal
    net_pay: Decimal
    lines: list[PayrollLine]


class PayrollDifference(ApiModel):
    employee_code: str
    full_name: str
    previous_net: Decimal | None
    next_net: Decimal | None
    change: str


class PayrollPreview(ApiModel):
    run_id: int
    status: PayrollRunStatus
    previous_employees: int
    next_employees: int
    previous_gross: Decimal
    next_gross: Decimal
    previous_deductions: Decimal
    next_deductions: Decimal
    previous_net: Decimal
    next_net: Decimal
    differences: list[PayrollDifference]


class PayrollRunItem(ApiModel):
    id: int
    period_month: date
    run_date: date
    status: PayrollRunStatus
    employees: int = Field(ge=0)
    gross: Decimal
    deductions: Decimal
    net_pay: Decimal
