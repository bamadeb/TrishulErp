from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.auth.deps import get_identity_provider, get_user_directory
from trishul_api.auth.identity import IdentityProvider
from trishul_api.auth.users import UserDirectory
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.modules.core.users.repository import UserRepository
from trishul_api.modules.core.users.schemas import (
    EmployeeOption,
    EmployeeOptionQuery,
    PasswordResetRequest,
    PasswordResetResult,
    RoleOption,
    UserCreate,
    UserCreated,
    UserDetail,
    UserListItem,
    UserQuery,
    UserUpdate,
)
from trishul_api.modules.core.users.service import UserService

router = APIRouter(prefix="/core", tags=["users"])

CAN_VIEW = Depends(require_permission("core.user.view", "core.user.manage"))
CAN_MANAGE = Depends(require_permission("core.user.manage"))

UserId = Annotated[int, Path(alias="userId")]


def get_user_service(
    db: DbSession,
    identity: Annotated[IdentityProvider, Depends(get_identity_provider)],
    directory: Annotated[UserDirectory, Depends(get_user_directory)],
) -> UserService:
    return UserService(db, identity, directory)


def get_user_repository(db: DbSession) -> UserRepository:
    return UserRepository(db)


Users = Annotated[UserService, Depends(get_user_service)]
UserRepo = Annotated[UserRepository, Depends(get_user_repository)]


@router.get("/users", summary="Users, with their roles", dependencies=[CAN_VIEW])
def list_users(query: Annotated[UserQuery, Query()], repo: UserRepo) -> Page[UserListItem]:
    return repo.search(query)


# Declared before /users/{userId} so "employee-options" is not parsed as a user id.
@router.get(
    "/users/employee-options",
    summary="Active employees matching a search, to link a user to",
    dependencies=[CAN_MANAGE],  # the user form's picker; full employee screens live in the employees module
)
def list_employee_options(query: Annotated[EmployeeOptionQuery, Query()], repo: UserRepo) -> list[EmployeeOption]:
    return repo.employee_options(query)


@router.get("/users/{userId}", summary="One user", dependencies=[CAN_VIEW], responses=NOT_FOUND_RESPONSE)
def get_user(user_id: UserId, users: Users) -> UserDetail:
    return users.get(user_id)


@router.post(
    "/users",
    summary="Add a user and their sign-in account",
    status_code=201,
    dependencies=[CAN_MANAGE],
)
def create_user(data: UserCreate, actor: CurrentUserDep, users: Users, response: Response) -> UserCreated:
    created = users.create(actor, data)
    response.headers["Location"] = f"users/{created.id}"
    return created


@router.patch(
    "/users/{userId}",
    summary="Change the linked employee, mobile, default branch, roles or brands",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_user(
    user_id: UserId,
    data: UserUpdate,
    actor: CurrentUserDep,
    users: Users,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> UserDetail:
    return users.update(actor, user_id, row_version, data)


@router.post(
    "/users/{userId}/deactivate",
    summary="Block sign-in and end the user's sessions",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def deactivate_user(user_id: UserId, actor: CurrentUserDep, users: Users) -> UserDetail:
    return users.deactivate(actor, user_id)


@router.post(
    "/users/{userId}/activate",
    summary="Allow the user to sign in again",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def activate_user(user_id: UserId, actor: CurrentUserDep, users: Users) -> UserDetail:
    return users.activate(actor, user_id)


@router.post(
    "/users/{userId}/reset-password",
    summary="Email a reset, or return a temporary password to hand over",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def reset_user_password(
    user_id: UserId, data: PasswordResetRequest, actor: CurrentUserDep, users: Users
) -> PasswordResetResult:
    return users.reset_password(actor, user_id, data.delivery)


@router.get("/roles", summary="Roles that can be granted", dependencies=[CAN_VIEW])
def list_roles(repo: UserRepo) -> list[RoleOption]:
    return repo.roles()
