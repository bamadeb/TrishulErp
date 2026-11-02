from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, ScopeDep, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.modules.service.machines.repository import MachineRepository
from trishul_api.modules.service.machines.schemas import (
    MachineCreate,
    MachineDetail,
    MachineFormOptions,
    MachineListItem,
    MachineQuery,
    MachineUpdate,
)
from trishul_api.modules.service.machines.service import MachineService

router = APIRouter(prefix="/svc", tags=["machines"])

CAN_VIEW = Depends(require_permission("core.machine.view", "core.machine.manage"))
CAN_MANAGE = Depends(require_permission("core.machine.manage"))

MachineId = Annotated[int, Path(alias="machineId", gt=0)]


def get_machine_repository(db: DbSession) -> MachineRepository:
    return MachineRepository(db)


MachineRepo = Annotated[MachineRepository, Depends(get_machine_repository)]


@router.get("/machines", summary="Machines of the selected brand, filtered and paged", dependencies=[CAN_VIEW])
def list_machines(query: Annotated[MachineQuery, Query()], scope: ScopeDep, repo: MachineRepo) -> Page[MachineListItem]:
    return repo.search(scope, query)


# Declared before /machines/{machineId} so "form-options" is not parsed as a machine id.
@router.get("/machines/form-options", summary="Dropdown values for the machine form", dependencies=[CAN_MANAGE])
def get_machine_form_options(scope: ScopeDep, repo: MachineRepo) -> MachineFormOptions:
    return MachineFormOptions(models=repo.models(scope))


@router.get("/machines/{machineId}", summary="One machine", dependencies=[CAN_VIEW], responses=NOT_FOUND_RESPONSE)
def get_machine(machine_id: MachineId, actor: CurrentUserDep, db: DbSession) -> MachineDetail:
    return MachineService(db, actor).get(machine_id)


@router.post("/machines", summary="Add a machine for a customer", status_code=201, dependencies=[CAN_MANAGE])
def create_machine(data: MachineCreate, actor: CurrentUserDep, db: DbSession, response: Response) -> MachineDetail:
    created = MachineService(db, actor).create(data)
    response.headers["Location"] = f"machines/{created.id}"
    return created


@router.patch(
    "/machines/{machineId}",
    summary="Change a machine's details or owner",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_machine(
    machine_id: MachineId,
    data: MachineUpdate,
    actor: CurrentUserDep,
    db: DbSession,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> MachineDetail:
    return MachineService(db, actor).update(machine_id, row_version, data)


@router.post(
    "/machines/{machineId}/deactivate",
    summary="Mark a machine inactive (no new calls; existing calls keep it)",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def deactivate_machine(machine_id: MachineId, actor: CurrentUserDep, db: DbSession) -> MachineDetail:
    return MachineService(db, actor).deactivate(machine_id)


@router.post(
    "/machines/{machineId}/activate",
    summary="Mark a machine active again",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def activate_machine(machine_id: MachineId, actor: CurrentUserDep, db: DbSession) -> MachineDetail:
    return MachineService(db, actor).activate(machine_id)
