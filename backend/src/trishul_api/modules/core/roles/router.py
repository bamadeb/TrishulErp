from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.auth.deps import get_user_directory
from trishul_api.auth.users import UserDirectory
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.modules.core.roles.repository import RoleRepository
from trishul_api.modules.core.roles.schemas import (
    PermissionItem,
    RoleCreate,
    RoleDetail,
    RoleListItem,
    RoleQuery,
    RoleUpdate,
)
from trishul_api.modules.core.roles.service import RoleService

router = APIRouter(prefix="/core", tags=["roles"])

CAN_VIEW = Depends(require_permission("core.role.view", "core.role.manage"))
CAN_MANAGE = Depends(require_permission("core.role.manage"))
# The user form picks roles from the same list.
CAN_LIST = Depends(require_permission("core.role.view", "core.role.manage", "core.user.view", "core.user.manage"))

RoleId = Annotated[int, Path(alias="roleId")]


def get_role_service(db: DbSession, directory: Annotated[UserDirectory, Depends(get_user_directory)]) -> RoleService:
    return RoleService(db, directory)


def get_role_repository(db: DbSession) -> RoleRepository:
    return RoleRepository(db)


Roles = Annotated[RoleService, Depends(get_role_service)]
RoleRepo = Annotated[RoleRepository, Depends(get_role_repository)]


@router.get("/roles", summary="Roles, with how many users and permissions each has", dependencies=[CAN_LIST])
def list_roles(query: Annotated[RoleQuery, Query()], repo: RoleRepo) -> list[RoleListItem]:
    return repo.search(query)


@router.get("/permissions", summary="Every permission a role can grant", dependencies=[CAN_VIEW])
def list_permissions(repo: RoleRepo) -> list[PermissionItem]:
    return repo.permissions()


@router.get(
    "/roles/{roleId}", summary="One role and its permissions", dependencies=[CAN_VIEW], responses=NOT_FOUND_RESPONSE
)
def get_role(role_id: RoleId, roles: Roles) -> RoleDetail:
    return roles.get(role_id)


@router.post("/roles", summary="Add a role", status_code=201, dependencies=[CAN_MANAGE])
def create_role(data: RoleCreate, actor: CurrentUserDep, roles: Roles, response: Response) -> RoleDetail:
    created = roles.create(actor, data)
    response.headers["Location"] = f"roles/{created.id}"
    return created


@router.patch(
    "/roles/{roleId}",
    summary="Change a role's name, description or permissions",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_role(
    role_id: RoleId,
    data: RoleUpdate,
    actor: CurrentUserDep,
    roles: Roles,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> RoleDetail:
    return roles.update(actor, role_id, row_version, data)


@router.post(
    "/roles/{roleId}/deactivate",
    summary="Mark a role inactive (its users lose its permissions)",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def deactivate_role(role_id: RoleId, actor: CurrentUserDep, roles: Roles) -> RoleDetail:
    return roles.deactivate(actor, role_id)


@router.post(
    "/roles/{roleId}/activate",
    summary="Mark a role active again",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def activate_role(role_id: RoleId, actor: CurrentUserDep, roles: Roles) -> RoleDetail:
    return roles.activate(actor, role_id)
