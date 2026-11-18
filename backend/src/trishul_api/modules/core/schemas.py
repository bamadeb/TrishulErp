from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel


class OwnPasswordChange(InputModel):
    """The signed-in user's current password and the one to change it to. The pool's password rules
    (length, characters) are checked by the sign-in service."""

    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256, description="At least 12 characters (the pool's rule).")


class BranchRef(ApiModel):
    id: int
    code: str
    name: str
    branch_type: str
    warehouse_id: int | None
    """The warehouse that supplies this branch (a warehouse's own id for a warehouse)."""
    warehouse_name: str | None
    region_id: int | None
    region_name: str | None


class PrincipalRef(ApiModel):
    id: int
    code: str
    name: str


class Me(ApiModel):
    """The signed-in user, as the Angular AuthStore expects it."""

    id: int
    username: str
    display_name: str
    role_names: list[str]
    """Names of the user's active roles, e.g. "Service Team Lead"; shown beside their name."""
    email: str | None
    default_branch_id: int | None
    permissions: list[str]
    branches: list[BranchRef]
    principals: list[PrincipalRef]


class LookupValueOut(ApiModel):
    id: int
    code: str
    name: str
    sort_order: int
