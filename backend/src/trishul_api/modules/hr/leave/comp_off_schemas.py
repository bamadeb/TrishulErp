"""Comp Off authorization and ledger contracts."""

from datetime import date
from decimal import Decimal
from pydantic import Field, model_validator

from trishul_api.common.schemas import ApiModel, InputModel

class CompOffAuthorizeIn(InputModel):
    employee_id: int | None = Field(None, gt=0)
    employee_code: str | None = Field(None, max_length=30)
    work_date: date
    remarks: str | None = Field(None, max_length=300)

    @model_validator(mode="after")
    def employee_given(self) -> "CompOffAuthorizeIn":
        if self.employee_id is None and not (self.employee_code and self.employee_code.strip()):
            raise ValueError("Enter the employee who is authorized to work.")
        return self


class CompOffReport(ApiModel):
    employee_id: int
    employee_code: str
    employee_name: str


class CompOffAuthorizationItem(ApiModel):
    id: int
    employee_id: int
    employee_code: str
    employee_name: str
    work_date: date
    day_kind: str
    status: str
    remarks: str | None = None


class CompOffLedgerItem(ApiModel):
    id: int
    credit_id: int
    kind: str
    days: Decimal
    leave_request_id: int | None
    remarks: str | None
    created_at: date


class CompOffLapseResult(ApiModel):
    lapsed: int
