from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.modules.core.teams.repository import TeamRepository
from trishul_api.modules.core.teams.schemas import (
    TeamCreate,
    TeamDetail,
    TeamEmployeeOption,
    TeamEmployeeOptionQuery,
    TeamListItem,
    TeamQuery,
    TeamUpdate,
)
from trishul_api.modules.core.teams.service import TeamService

router = APIRouter(prefix="/core", tags=["teams"])

CAN_VIEW = Depends(require_permission("core.team.view", "core.team.manage"))
CAN_MANAGE = Depends(require_permission("core.team.manage"))

TeamId = Annotated[int, Path(alias="teamId", gt=0)]


def get_team_service(db: DbSession, actor: CurrentUserDep) -> TeamService:
    return TeamService(db, actor)


def get_team_repository(db: DbSession) -> TeamRepository:
    return TeamRepository(db)


Teams = Annotated[TeamService, Depends(get_team_service)]
TeamRepo = Annotated[TeamRepository, Depends(get_team_repository)]


@router.get("/teams", summary="Teams in the user's branches, with lead and member count", dependencies=[CAN_VIEW])
def list_teams(query: Annotated[TeamQuery, Query()], actor: CurrentUserDep, repo: TeamRepo) -> list[TeamListItem]:
    return repo.search(query, actor.branch_ids)


@router.get(
    "/teams/employee-options",
    summary="Active employees of a branch, to pick a team's lead and members",
    dependencies=[CAN_MANAGE],
)
def list_team_employee_options(
    query: Annotated[TeamEmployeeOptionQuery, Query()], actor: CurrentUserDep, repo: TeamRepo
) -> list[TeamEmployeeOption]:
    if not actor.can_use_branch(query.branch_id):
        return []
    return repo.employee_options(query)


# Declared after /teams/employee-options so that literal path is not parsed as a team id.
@router.get(
    "/teams/{teamId}", summary="One team and its members", dependencies=[CAN_VIEW], responses=NOT_FOUND_RESPONSE
)
def get_team(team_id: TeamId, teams: Teams) -> TeamDetail:
    return teams.get(team_id)


@router.post("/teams", summary="Add a team", status_code=201, dependencies=[CAN_MANAGE])
def create_team(data: TeamCreate, teams: Teams, response: Response) -> TeamDetail:
    created = teams.create(data)
    response.headers["Location"] = f"teams/{created.id}"
    return created


@router.patch(
    "/teams/{teamId}",
    summary="Change a team's name, type, lead or members",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_team(
    team_id: TeamId,
    data: TeamUpdate,
    teams: Teams,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> TeamDetail:
    return teams.update(team_id, row_version, data)


@router.post(
    "/teams/{teamId}/deactivate",
    summary="Mark a team inactive (its lead no longer sees its calls)",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def deactivate_team(team_id: TeamId, teams: Teams) -> TeamDetail:
    return teams.deactivate(team_id)


@router.post(
    "/teams/{teamId}/activate",
    summary="Mark a team active again",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def activate_team(team_id: TeamId, teams: Teams) -> TeamDetail:
    return teams.activate(team_id)
