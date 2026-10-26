from trishul_api.common.schemas import ApiModel


class BranchRef(ApiModel):
    id: int
    code: str
    name: str


class PrincipalRef(ApiModel):
    id: int
    code: str
    name: str


class Me(ApiModel):
    """The signed-in user, as the Angular AuthStore expects it."""

    id: int
    username: str
    display_name: str
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
