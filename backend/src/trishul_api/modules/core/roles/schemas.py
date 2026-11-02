from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, RowVersion, UtcDateTime

RoleStatusFilter = Literal["active", "inactive", "all"]

# Upper-case letters, digits and underscores, like the built-in codes (TEAM_LEAD). The column holds 40.
ROLE_CODE_PATTERN = r"^[A-Z][A-Z0-9_]{1,39}$"


class RoleQuery(ApiModel):
    """Roles are a short list, so it is not paged."""

    status: RoleStatusFilter = "active"
    search: str | None = Field(None, max_length=100, description="Code, name or description.")


class RoleListItem(ApiModel):
    id: int
    code: str
    name: str
    description: str | None
    is_system: bool = Field(description="Built-in role: its code is used by the system, so it can't be deactivated.")
    is_active: bool
    user_count: int = Field(0, description="Active users holding this role.")
    permission_count: int = Field(0, description="Permissions this role grants.")


class RoleDetail(RoleListItem):
    permission_codes: list[str]
    created_at: UtcDateTime
    updated_at: UtcDateTime | None
    row_version: RowVersion


class RoleCreate(InputModel):
    code: str = Field(
        pattern=ROLE_CODE_PATTERN,
        max_length=40,
        description="Upper-case letters, digits and _ (e.g. AREA_MANAGER). Cannot be changed later.",
    )
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    permission_codes: list[str] = Field(default_factory=list, max_length=500)


class RoleUpdate(InputModel):
    """Only the fields sent are changed. permissionCodes, when sent, is the role's complete list."""

    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    permission_codes: list[str] | None = Field(None, max_length=500)


class PermissionItem(ApiModel):
    id: int
    code: str
    module: str
    description: str | None
