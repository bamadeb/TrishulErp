from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response

from trishul_api.auth import SIGNED_IN_USERS, CurrentUserDep, DbSession
from trishul_api.auth.deps import get_identity_provider
from trishul_api.auth.identity import IdentityProvider
from trishul_api.common.errors import NOT_FOUND_RESPONSE, ApiError, NotFound
from trishul_api.modules.core.repository import CoreRepository
from trishul_api.modules.core.schemas import LookupValueOut, Me, OwnPasswordChange

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
        role_names=repo.role_names(user.roles),
        email=user.email,
        default_branch_id=user.default_branch_id,
        permissions=sorted(user.permissions | repo.derived_permissions(user.employee_id)),
        branches=repo.branches(user.branch_ids),
        principals=repo.principals(user.principal_ids),
    )


@router.post(
    "/me/password",
    summary="Change my own password (needs the current password)",
    status_code=204,
    response_class=Response,
    openapi_extra=SIGNED_IN_USERS,
)
def change_my_password(
    data: OwnPasswordChange,
    request: Request,
    _: CurrentUserDep,  # a valid signed-in session
    identity: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> Response:
    """Changes the password of whoever the access token belongs to. Other devices stay signed in until
    their session ends; the new password is needed at the next sign-in."""
    if data.new_password == data.current_password:
        raise ApiError(
            "The new password must be different from the current one.",
            errors={"newPassword": ["Same as the current password."]},
        )
    scheme, _sep, token = request.headers.get("Authorization", "").partition(" ")
    identity.change_own_password(
        token.strip() if scheme.lower() == "bearer" else "", data.current_password, data.new_password
    )
    return Response(status_code=204)


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
