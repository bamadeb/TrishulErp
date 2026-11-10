"""Payroll run requests and responses. JSON is camelCase."""

from datetime import date
from decimal import Decimal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel
from trishul_api.db.models.generated.hr import PayrollRunStatus


class PayrollRunRequest(InputModel):
    month: date


class PayrollRunItem(ApiModel):
    id: int
    period_month: date
    run_date: date
    status: PayrollRunStatus
    employees: int = Field(ge=0)
    gross: Decimal
    deductions: Decimal
    net_pay: Decimal
