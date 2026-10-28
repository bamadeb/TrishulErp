from datetime import date
from typing import Literal

from pydantic import EmailStr, Field, computed_field

from trishul_api.common.schemas import MOBILE_PATTERN, ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models.generated.core import EmployeeEmployeeType, EmployeeMobilePlatform, EmployeeStatus

EmployeeStatusFilter = Literal["active", "inactive", "all"]


class EmployeeQuery(PageQuery):
    status: EmployeeStatusFilter = "active"
    branch_id: int | None = None
    department_id: int | None = None
    employee_type: EmployeeEmployeeType | None = None


class EmployeeListItem(ApiModel):
    id: int
    employee_code: str
    first_name: str
    last_name: str | None
    mobile: str | None
    email: str | None
    branch_id: int
    branch_name: str | None
    department_id: int | None
    department: str | None
    designation_id: int | None
    designation: str | None
    employee_type: EmployeeEmployeeType
    status: EmployeeStatus
    is_active: bool
    user_id: int | None = Field(description="The sign-in account linked to this employee, if any.")
    created_at: UtcDateTime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_login(self) -> bool:
        return self.user_id is not None


class EmployeeDetail(EmployeeListItem):
    company_id: int
    company_name: str | None
    reporting_manager_id: int | None
    reporting_manager_name: str | None
    date_of_joining: date | None
    date_of_exit: date | None
    mobile_platform: EmployeeMobilePlatform | None
    row_version: RowVersion


class EmployeeCreate(InputModel):
    employee_code: str = Field(min_length=1, max_length=20, description="Unique across all employees.")
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str | None = Field(None, max_length=60)
    mobile: str | None = Field(None, pattern=MOBILE_PATTERN, description="Unique; at most one employee may have none.")
    email: EmailStr | None = Field(None, max_length=120)
    company_id: int
    branch_id: int
    department_id: int | None = None
    designation_id: int | None = None
    reporting_manager_id: int | None = None
    employee_type: EmployeeEmployeeType
    status: EmployeeStatus = "Active"
    date_of_joining: date | None = None
    date_of_exit: date | None = None
    mobile_platform: EmployeeMobilePlatform | None = None


class EmployeeUpdate(InputModel):
    """Only the fields sent are changed."""

    employee_code: str | None = Field(None, min_length=1, max_length=20)
    first_name: str | None = Field(None, min_length=1, max_length=60)
    last_name: str | None = Field(None, max_length=60)
    mobile: str | None = Field(None, pattern=MOBILE_PATTERN)
    email: EmailStr | None = Field(None, max_length=120)
    company_id: int | None = None
    branch_id: int | None = None
    department_id: int | None = None
    designation_id: int | None = None
    reporting_manager_id: int | None = None
    employee_type: EmployeeEmployeeType | None = None
    status: EmployeeStatus | None = None
    date_of_joining: date | None = None
    date_of_exit: date | None = None
    mobile_platform: EmployeeMobilePlatform | None = None


class CompanyOption(ApiModel):
    id: int
    name: str


class DepartmentOption(ApiModel):
    id: int
    code: str
    name: str


class DesignationOption(ApiModel):
    id: int
    code: str
    name: str
    department_id: int | None
