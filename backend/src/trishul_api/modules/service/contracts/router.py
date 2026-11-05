import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, Query, Response, UploadFile

from trishul_api.auth import CurrentUser, CurrentUserDep, DbSession, RequestScope, ScopeDep, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE, ApiError, Forbidden, problem_response
from trishul_api.common.schemas import Page
from trishul_api.modules.service.contracts.asc_import import AscImportService
from trishul_api.modules.service.contracts.repository import ContractRepository
from trishul_api.modules.service.contracts.schemas import (
    AscCallVisit,
    AscCallVisitSet,
    AscImportResult,
    ContractFormOptions,
    ContractPlanCreate,
    ContractPlanItem,
    ContractPlanQuery,
    ContractPlanUpdate,
    ServiceContractCreate,
    ServiceContractDetail,
    ServiceContractListItem,
    ServiceContractQuery,
    ServiceContractRenew,
    ServiceContractUpdate,
)
from trishul_api.modules.service.contracts.service import ContractService

router = APIRouter(prefix="/svc", tags=["contracts"])

CAN_VIEW = Depends(require_permission("svc.contract.view", "svc.contract.manage"))
CAN_MANAGE = Depends(require_permission("svc.contract.manage"))
CAN_IMPORT = Depends(require_permission("svc.contract.import"))
CAN_COUNT_VISITS = Depends(require_permission("svc.contract.visit"))

ContractId = Annotated[int, Path(alias="contractId", gt=0)]
PlanId = Annotated[int, Path(alias="planId", gt=0)]
CallId = Annotated[int, Path(alias="callId", gt=0)]
RowVersionDep = Annotated[bytes, Depends(if_match_row_version)]

# The register is a few hundred kilobytes to a few megabytes.
_MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def get_contract_repository(db: DbSession) -> ContractRepository:
    return ContractRepository(db)


ContractRepo = Annotated[ContractRepository, Depends(get_contract_repository)]


# ---------------------------------------------------------------------------------------------- plans


@router.get("/contract-plans", summary="ASC plans (price list) of the selected brand", dependencies=[CAN_VIEW])
def list_contract_plans(
    query: Annotated[ContractPlanQuery, Query()], scope: ScopeDep, repo: ContractRepo
) -> list[ContractPlanItem]:
    return repo.plans(scope, query)


@router.post("/contract-plans", summary="Add an ASC plan", status_code=201, dependencies=[CAN_MANAGE])
def create_contract_plan(
    data: ContractPlanCreate, actor: CurrentUserDep, scope: ScopeDep, db: DbSession
) -> ContractPlanItem:
    return ContractService(db, actor).create_plan(scope, data)


@router.patch(
    "/contract-plans/{planId}",
    summary="Change an ASC plan (contracts already sold keep their own values)",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_contract_plan(
    plan_id: PlanId, data: ContractPlanUpdate, actor: CurrentUserDep, db: DbSession, row_version: RowVersionDep
) -> ContractPlanItem:
    return ContractService(db, actor).update_plan(plan_id, row_version, data)


@router.post(
    "/contract-plans/{planId}/deactivate",
    summary="Stop offering an ASC plan",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def deactivate_contract_plan(plan_id: PlanId, actor: CurrentUserDep, db: DbSession) -> ContractPlanItem:
    return ContractService(db, actor).set_plan_active(plan_id, False)


@router.post(
    "/contract-plans/{planId}/activate",
    summary="Offer an ASC plan again",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def activate_contract_plan(plan_id: PlanId, actor: CurrentUserDep, db: DbSession) -> ContractPlanItem:
    return ContractService(db, actor).set_plan_active(plan_id, True)


# ------------------------------------------------------------------------------------------ contracts


@router.get(
    "/service-contracts",
    summary="ASC contracts in the user's branches, filtered and paged",
    dependencies=[CAN_VIEW],
)
def list_service_contracts(
    query: Annotated[ServiceContractQuery, Query()], actor: CurrentUserDep, scope: ScopeDep, repo: ContractRepo
) -> Page[ServiceContractListItem]:
    return repo.search(actor, scope, query, dt.date.today())


# Declared before /service-contracts/{contractId} so "form-options" is not parsed as an id.
@router.get(
    "/service-contracts/form-options",
    summary="Plans and engineers for the ASC form",
    dependencies=[CAN_MANAGE],
)
def get_service_contract_form_options(
    scope: ScopeDep, repo: ContractRepo, branch_id: Annotated[int | None, Query(alias="branchId")] = None
) -> ContractFormOptions:
    return ContractFormOptions(
        plans=repo.plans(scope, ContractPlanQuery(status="active")),
        engineers=repo.engineers(branch_id if branch_id is not None else scope.branch_id),
    )


@router.post(
    "/service-contracts/import/preview",
    summary="Dry run of an ASC register upload (nothing is written)",
    dependencies=[CAN_IMPORT],
    responses={400: problem_response("The file is not a recognizable ASC register.")},
)
def preview_service_contract_import(
    actor: CurrentUserDep,
    scope: ScopeDep,
    db: DbSession,
    file: Annotated[UploadFile, File(description="The ASC register (.xlsx)")],
    branch_id: Annotated[int | None, Form(alias="branchId")] = None,
) -> AscImportResult:
    content = _read_upload(file)
    branch = _upload_branch(actor, scope, branch_id)
    return AscImportService(db, actor).run(
        content, file.filename or "asc.xlsx", branch, scope.principal_id, apply=False
    )


@router.post(
    "/service-contracts/import",
    summary="Import the ASC register, upserting contracts on machine + start date",
    status_code=201,
    dependencies=[CAN_IMPORT],
    responses={400: problem_response("The file is not a recognizable ASC register.")},
)
def apply_service_contract_import(
    actor: CurrentUserDep,
    scope: ScopeDep,
    db: DbSession,
    file: Annotated[UploadFile, File(description="The ASC register (.xlsx)")],
    branch_id: Annotated[int | None, Form(alias="branchId")] = None,
) -> AscImportResult:
    content = _read_upload(file)
    branch = _upload_branch(actor, scope, branch_id)
    return AscImportService(db, actor).run(content, file.filename or "asc.xlsx", branch, scope.principal_id, apply=True)


@router.get("/service-contracts/{contractId}", summary="One ASC", dependencies=[CAN_VIEW], responses=NOT_FOUND_RESPONSE)
def get_service_contract(contract_id: ContractId, actor: CurrentUserDep, db: DbSession) -> ServiceContractDetail:
    return ContractService(db, actor).get(contract_id)


@router.post("/service-contracts", summary="Add an ASC for a machine", status_code=201, dependencies=[CAN_MANAGE])
def create_service_contract(
    data: ServiceContractCreate, actor: CurrentUserDep, scope: ScopeDep, db: DbSession, response: Response
) -> ServiceContractDetail:
    created = ContractService(db, actor).create(scope, data)
    response.headers["Location"] = f"service-contracts/{created.id}"
    return created


@router.patch(
    "/service-contracts/{contractId}",
    summary="Change an ASC",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_service_contract(
    contract_id: ContractId,
    data: ServiceContractUpdate,
    actor: CurrentUserDep,
    db: DbSession,
    row_version: RowVersionDep,
) -> ServiceContractDetail:
    return ContractService(db, actor).update(contract_id, row_version, data)


@router.post(
    "/service-contracts/{contractId}/renew",
    summary="Renew an ASC: a new contract for the same machine, linked to this one",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def renew_service_contract(
    contract_id: ContractId, data: ServiceContractRenew, actor: CurrentUserDep, db: DbSession
) -> ServiceContractDetail:
    return ContractService(db, actor).renew(contract_id, data)


@router.post(
    "/service-contracts/{contractId}/cancel",
    summary="Cancel an ASC (kept in the history)",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def cancel_service_contract(contract_id: ContractId, actor: CurrentUserDep, db: DbSession) -> ServiceContractDetail:
    return ContractService(db, actor).cancel(contract_id)


@router.get(
    "/service-contracts/{contractId}/call-visits",
    summary="Finished service calls under an ASC and the visits counted for each",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def list_contract_call_visits(contract_id: ContractId, actor: CurrentUserDep, db: DbSession) -> list[AscCallVisit]:
    return ContractService(db, actor).call_visits(contract_id)


@router.put(
    "/service-contracts/{contractId}/call-visits/{callId}",
    summary="Record the visits a completed service call took (0 takes it off the ASC's count)",
    dependencies=[CAN_COUNT_VISITS],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_contract_call_visits(
    contract_id: ContractId,
    call_id: CallId,
    data: AscCallVisitSet,
    actor: CurrentUserDep,
    db: DbSession,
    row_version: RowVersionDep,
) -> ServiceContractDetail:
    return ContractService(db, actor).set_call_visits(contract_id, call_id, row_version, data)


def _read_upload(file: UploadFile) -> bytes:
    content = file.file.read()
    if not content:
        raise ApiError("The uploaded file is empty.")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise ApiError("That file is too large for an ASC register (15 MB at most).")
    return content


def _upload_branch(actor: CurrentUser, scope: RequestScope, branch_id: int | None) -> int:
    """The branch rows go under when the register names a branch Trishul doesn't have."""
    chosen = branch_id if branch_id is not None else scope.branch_id
    if chosen is None:
        raise ApiError("Choose a branch for the import.")
    if not actor.can_use_branch(chosen):
        raise Forbidden("You do not have access to this branch.")
    return chosen
