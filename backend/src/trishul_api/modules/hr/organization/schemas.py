"""Request and response models for Organization Management.

Detail classes are the response bodies. They follow the same ApiModel / InputModel
split as the other modules: camelCase JSON, unknown input fields rejected.
Writes land on the existing tables named in ``models.py``. Create and update bodies
omit server-generated id, timestamps and row version.
"""

from decimal import Decimal
from typing import Literal, Self

from pydantic import EmailStr, Field, computed_field, model_validator

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models.generated.core import BranchBranchType, EmployeeStatus

OrganizationStatusFilter = Literal["active", "inactive", "all"]

# Branch phone is NVARCHAR(20). Digits, with an optional leading + and light punctuation.
_PHONE_PATTERN = r"^[0-9+\-() ]{6,20}$"


class OrganizationQuery(PageQuery):
    """Shared list filters. ``status`` is ``is_active`` on the underlying row."""

    status: OrganizationStatusFilter = "active"


class DepartmentListItem(ApiModel):
    id: int
    code: str
    name: str
    parent_department_id: int | None
    parent_department_name: str | None
    head_employee_id: int | None
    head_name: str | None
    employee_count: int
    is_active: bool
    created_at: UtcDateTime


class DepartmentDetail(DepartmentListItem):
    updated_at: UtcDateTime | None
    row_version: RowVersion


class DepartmentCreate(InputModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=80)
    parent_department_id: int | None = None
    head_employee_id: int | None = None


class DepartmentUpdate(InputModel):
    """Only the fields sent are changed."""

    code: str | None = Field(None, min_length=1, max_length=20)
    name: str | None = Field(None, min_length=1, max_length=80)
    parent_department_id: int | None = None
    head_employee_id: int | None = None
    is_active: bool | None = None


class DesignationListItem(ApiModel):
    id: int
    code: str
    name: str
    grade: str | None
    department_id: int | None
    department_name: str | None
    employee_count: int
    is_active: bool
    created_at: UtcDateTime


class DesignationDetail(DesignationListItem):
    updated_at: UtcDateTime | None
    row_version: RowVersion


class DesignationCreate(InputModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=80)
    grade: str | None = Field(None, min_length=1, max_length=10)
    department_id: int | None = None


class DesignationUpdate(InputModel):
    """Only the fields sent are changed."""

    code: str | None = Field(None, min_length=1, max_length=20)
    name: str | None = Field(None, min_length=1, max_length=80)
    grade: str | None = Field(None, min_length=1, max_length=10)
    department_id: int | None = None
    is_active: bool | None = None


class GradeDesignation(ApiModel):
    """One designation that carries this grade. The grade itself has no row version."""

    id: int
    code: str
    name: str
    department_id: int | None
    department_name: str | None
    employee_count: int
    is_active: bool
    row_version: RowVersion


class GradeListItem(ApiModel):
    """A distinct ``hr.designation.grade`` value, not a row in its own table."""

    grade: str
    designation_count: int
    employee_count: int


class GradeDetail(GradeListItem):
    designations: list[GradeDesignation] = Field(default_factory=list)


class GradeCreate(InputModel):
    """Stores the grade on an existing designation. It does not insert a grade row."""

    grade: str = Field(min_length=1, max_length=10)
    designation_id: int


class GradeUpdate(InputModel):
    """Renames the grade label on the designations that currently use it."""

    grade: str = Field(min_length=1, max_length=10)


class BranchListItem(ApiModel):
    """A ``core.branch`` row. This is the Locations section, not ``core.location``."""

    id: int
    code: str
    name: str
    branch_type: BranchBranchType
    company_id: int
    company_name: str | None
    state_id: int
    state_name: str | None
    employee_count: int
    is_active: bool
    created_at: UtcDateTime


class BranchDetail(BranchListItem):
    parent_warehouse_id: int | None
    parent_warehouse_name: str | None
    address: str | None
    district_id: int | None
    pincode_id: int | None
    gstin_registration_id: int | None
    phone: str | None
    email: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    updated_at: UtcDateTime | None
    row_version: RowVersion


class BranchCreate(InputModel):
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=120)
    branch_type: BranchBranchType
    company_id: int
    state_id: int
    parent_warehouse_id: int | None = None
    address: str | None = Field(None, max_length=500)
    district_id: int | None = None
    pincode_id: int | None = None
    gstin_registration_id: int | None = None
    phone: str | None = Field(None, pattern=_PHONE_PATTERN, max_length=20)
    email: EmailStr | None = Field(None, max_length=120)
    latitude: Decimal | None = Field(None, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(None, max_digits=9, decimal_places=6)


class BranchUpdate(InputModel):
    """Only the fields sent are changed."""

    code: str | None = Field(None, min_length=1, max_length=10)
    name: str | None = Field(None, min_length=1, max_length=120)
    branch_type: BranchBranchType | None = None
    company_id: int | None = None
    state_id: int | None = None
    parent_warehouse_id: int | None = None
    address: str | None = Field(None, max_length=500)
    district_id: int | None = None
    pincode_id: int | None = None
    gstin_registration_id: int | None = None
    phone: str | None = Field(None, pattern=_PHONE_PATTERN, max_length=20)
    email: EmailStr | None = Field(None, max_length=120)
    latitude: Decimal | None = Field(None, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(None, max_digits=9, decimal_places=6)
    is_active: bool | None = None


class CompanyListItem(ApiModel):
    id: int
    code: str
    legal_name: str
    trade_name: str | None
    state_id: int | None
    state_name: str | None
    employee_count: int
    is_active: bool
    created_at: UtcDateTime


class CompanyDetail(CompanyListItem):
    pan: str | None
    cin: str | None
    address: str | None
    logo_url: str | None
    fiscal_year_start_month: int
    updated_at: UtcDateTime | None
    row_version: RowVersion


class CompanyCreate(InputModel):
    code: str = Field(min_length=1, max_length=10)
    legal_name: str = Field(min_length=1, max_length=200)
    trade_name: str | None = Field(None, max_length=200)
    pan: str | None = Field(None, max_length=10)
    cin: str | None = Field(None, max_length=21)
    address: str | None = Field(None, max_length=500)
    state_id: int | None = None
    logo_url: str | None = Field(None, max_length=500)
    fiscal_year_start_month: int = Field(4, ge=1, le=12)


class CompanyUpdate(InputModel):
    """Only the fields sent are changed."""

    code: str | None = Field(None, min_length=1, max_length=10)
    legal_name: str | None = Field(None, min_length=1, max_length=200)
    trade_name: str | None = Field(None, max_length=200)
    pan: str | None = Field(None, max_length=10)
    cin: str | None = Field(None, max_length=21)
    address: str | None = Field(None, max_length=500)
    state_id: int | None = None
    logo_url: str | None = Field(None, max_length=500)
    fiscal_year_start_month: int | None = Field(None, ge=1, le=12)
    is_active: bool | None = None


class HierarchyListItem(ApiModel):
    """An existing employee and who they report to. Not a separate level row."""

    id: int
    employee_code: str
    first_name: str
    last_name: str | None
    department_id: int | None
    department_name: str | None
    designation_id: int | None
    designation_name: str | None
    grade: str | None
    company_id: int
    company_name: str | None
    branch_id: int
    branch_name: str | None
    reporting_manager_id: int | None
    reporting_manager_code: str | None
    reporting_manager_name: str | None
    direct_report_count: int
    status: EmployeeStatus
    is_active: bool
    created_at: UtcDateTime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part)


class HierarchyDetail(HierarchyListItem):
    updated_at: UtcDateTime | None
    row_version: RowVersion


class HierarchyCreate(InputModel):
    """Links an existing employee to a manager. It does not create an employee."""

    employee_id: int
    reporting_manager_id: int | None = None

    @model_validator(mode="after")
    def manager_is_someone_else(self) -> Self:
        if self.reporting_manager_id is not None and self.reporting_manager_id == self.employee_id:
            raise ValueError("An employee cannot report to themselves.")
        return self


class HierarchyUpdate(InputModel):
    """Changes ``core.employee.reporting_manager_id`` only."""

    reporting_manager_id: int | None = None
