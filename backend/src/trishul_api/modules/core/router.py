from typing import Annotated

from fastapi import APIRouter, Depends, Path

from trishul_api.auth import SIGNED_IN_USERS, CurrentUserDep, DbSession
from trishul_api.common.errors import NOT_FOUND_RESPONSE, NotFound
from trishul_api.modules.core.repository import CoreRepository
from trishul_api.modules.core.schemas import LookupValueOut, Me

router = APIRouter(tags=["core"])


def get_core_repository(db: DbSession) -> CoreRepository:
    return CoreRepository(db)


CoreRepo = Annotated[CoreRepository, Depends(get_core_repository)]


@router.get(
    "/me",
    summary="Signed-in user with permissions, branches and brands",
    openapi_extra=SIGNED_IN_USERS,
)
def get_me(user: CurrentUserDep, repo: CoreRepo) -> Me:
    return Me(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        default_branch_id=user.default_branch_id,
        permissions=sorted(user.permissions),
        branches=repo.branches(user.branch_ids),
        principals=repo.principals(user.principal_ids),
    )


@router.get(
    "/core/lookups/{typeCode}/values",
    summary="Values of an editable dropdown list",
    responses=NOT_FOUND_RESPONSE,
    openapi_extra=SIGNED_IN_USERS,  # every screen needs its dropdown values
)
def list_lookup_values(
    type_code: Annotated[str, Path(alias="typeCode", max_length=40, pattern=r"^[A-Z0-9_]+$")],
    _: CurrentUserDep,
    repo: CoreRepo,
) -> list[LookupValueOut]:
    values = repo.lookup_values(type_code)
    if values is None:
        raise NotFound(f"Lookup type {type_code} does not exist.")
    return values
