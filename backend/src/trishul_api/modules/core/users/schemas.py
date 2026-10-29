from typing import Literal

from pydantic import EmailStr, Field

from trishul_api.auth.identity import Delivery, SignInStatus
from trishul_api.common.schemas import MOBILE_PATTERN, ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime

UserStatusFilter = Literal["active", "inactive", "all"]


class UserQuery(PageQuery):
    status: UserStatusFilter = "active"
    role_id: int | None = None


class RoleGrant(ApiModel):
    """A role, on one branch or (branchId null) on all branches."""

    role_id: int
    role_code: str
    role_name: str
    branch_id: int | None
    branch_name: str | None


class UserListItem(ApiModel):
    id: int
    username: str
    email: str | None
    mobile: str | None = Field(description="The user's own mobile, if set.")
    phone: str | None = Field(description="The user's mobile, else the linked employee's.")
    display_name: str
    employee_id: int | None
    employee_code: str | None
    first_name: str | None
    last_name: str | None
    designation: str | None
    department: str | None
    is_active: bool
    is_locked: bool
    created_at: UtcDateTime
    roles: list[RoleGrant] = Field(default_factory=list)


class UserDetail(UserListItem):
    default_branch_id: int | None
    principal_ids: list[int]
    sign_in_status: SignInStatus
    row_version: RowVersion


class UserCreated(UserDetail):
    temporary_password: str | None = Field(
        None, description="Only when delivery was 'show': give it to the user once; it must be changed at sign-in."
    )


class RoleGrantInput(InputModel):
    role_id: int
    branch_id: int | None = None


class UserCreate(InputModel):
    email: EmailStr = Field(description="Sign-in name; cannot be changed later.")
    employee_id: int | None = Field(None, description="The employee this user signs in as.")
    mobile: str | None = Field(None, pattern=MOBILE_PATTERN)
    default_branch_id: int | None = None
    roles: list[RoleGrantInput] = Field(min_length=1)
    principal_ids: list[int] = Field(default_factory=list, description="Brands the user may see.")
    delivery: Delivery = Field("email", description="email: Cognito sends an invitation; show: return a password.")


class UserUpdate(InputModel):
    """Only the fields sent are changed; roles and principalIds replace the current lists."""

    employee_id: int | None = Field(None, description="null unlinks the employee.")
    mobile: str | None = Field(None, pattern=MOBILE_PATTERN)
    default_branch_id: int | None = None
    roles: list[RoleGrantInput] | None = Field(None, min_length=1)
    principal_ids: list[int] | None = None


class PasswordResetRequest(InputModel):
    delivery: Delivery = "email"


class PasswordResetResult(ApiModel):
    delivery: Delivery
    temporary_password: str | None
    sign_in_status: SignInStatus


class RoleOption(ApiModel):
    id: int
    code: str
    name: str
    description: str | None


class EmployeeOptionQuery(ApiModel):
    search: str | None = Field(None, max_length=100, description="Code, name, mobile or email.")
    limit: int = Field(20, ge=1, le=50)


class EmployeeOption(ApiModel):
    """An employee to link a user to."""

    id: int
    employee_code: str
    first_name: str
    last_name: str | None
    mobile: str | None
    email: str | None
    designation: str | None
    department: str | None
    branch_name: str | None
    linked_user_id: int | None = Field(description="The user already linked to this employee, if any.")
