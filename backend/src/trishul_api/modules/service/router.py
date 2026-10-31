from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, Query, UploadFile

from trishul_api.auth import CurrentUser, CurrentUserDep, DbSession, ScopeDep, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import (
    CONCURRENCY_RESPONSES,
    NOT_FOUND_RESPONSE,
    ApiError,
    Forbidden,
    problem_response,
)
from trishul_api.common.schemas import Page
from trishul_api.modules.service.access import CAN_VIEW_CALLS, CAN_VIEW_OWN_CALLS
from trishul_api.modules.service.imports.schemas import BydImportPreview, BydImportResult
from trishul_api.modules.service.imports.service import BydImportService
from trishul_api.modules.service.repository import ServiceCallRepository
from trishul_api.modules.service.schemas import (
    AssignedServiceCallListItem,
    AssignedServiceCallQuery,
    CallStatusLogItem,
    EngineerOption,
    EngineerOptionQuery,
    MachineOptionQuery,
    MachineUnitOption,
    ServiceCallCreate,
    ServiceCallDetail,
    ServiceCallListItem,
    ServiceCallQuery,
    ServiceCallStatusChange,
    ServiceCallTriageUpdate,
)
from trishul_api.modules.service.service import ServiceCallService
from trishul_api.modules.trk.schemas import CallTripHistoryItem
from trishul_api.modules.trk.service import TripService

router = APIRouter(prefix="/svc", tags=["service"])

# CAN_VIEW_CALLS (the register roles) and CAN_VIEW_OWN_CALLS (an engineer's own calls) live in access.py.
# A call's detail, history and status change are open to both; engineers are limited to their own calls
# inside the service. The status change itself is checked per status (access.allowed_statuses).
CAN_OPEN_CALL = Depends(require_permission(*CAN_VIEW_CALLS, CAN_VIEW_OWN_CALLS))
# The call register roles, the engineer looking at their own call, and team leads reviewing trips.
CAN_VIEW_CALL_TRIPS = (*CAN_VIEW_CALLS, CAN_VIEW_OWN_CALLS, "trk.trip.view.team")
CAN_CREATE = Depends(require_permission("svc.call.create"))
CAN_ASSIGN = Depends(require_permission("svc.call.assign"))
CAN_IMPORT = Depends(require_permission("svc.call.import"))

CallId = Annotated[int, Path(alias="callId", gt=0)]

# BYD exports are small (tens of KB); cap the upload well above that but still safely.
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def get_service_call_repository(db: DbSession) -> ServiceCallRepository:
    return ServiceCallRepository(db)


ServiceCallRepo = Annotated[ServiceCallRepository, Depends(get_service_call_repository)]

UploadBranchId = Annotated[int | None, Form(alias="branchId")]
UploadPrincipalId = Annotated[int | None, Form(alias="principalId")]


def _read_upload(file: UploadFile) -> bytes:
    content = file.file.read()
    if not content:
        raise ApiError("The uploaded file is empty.")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise ApiError("That file is too large. BYD exports are only a few hundred kilobytes.")
    return content


def _effective_branch_id(actor: CurrentUser, scope: ScopeDep, branch_id: int | None) -> int:
    chosen = branch_id if branch_id is not None else scope.branch_id
    if chosen is None:
        raise ApiError("Choose the branch these calls belong to before importing.")
    if not actor.can_use_branch(chosen):
        raise ApiError("You do not have access to that branch.", errors={"branchId": ["Not one of your branches."]})
    return chosen


@router.get(
    "/service-calls",
    summary="Call register for the selected branch and brand",
    dependencies=[Depends(require_permission(*CAN_VIEW_CALLS))],
)
def list_service_calls(
    query: Annotated[ServiceCallQuery, Query()],
    scope: ScopeDep,
    repo: ServiceCallRepo,
) -> Page[ServiceCallListItem]:
    return repo.list(scope, query)


@router.post(
    "/service-calls",
    summary="Log a new service call (office)",
    status_code=201,
    dependencies=[CAN_CREATE],
    responses={400: problem_response("Some of the selected values don't exist.")},
)
def create_service_call(
    data: ServiceCallCreate,
    actor: CurrentUserDep,
    scope: ScopeDep,
    db: DbSession,
) -> ServiceCallListItem:
    return ServiceCallService(db, actor).create(scope, data)


@router.patch(
    "/service-calls/{callId}",
    summary="Assign an engineer and/or set priority (team lead triage)",
    dependencies=[CAN_ASSIGN],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_service_call_triage(
    call_id: CallId,
    data: ServiceCallTriageUpdate,
    actor: CurrentUserDep,
    db: DbSession,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> ServiceCallListItem:
    return ServiceCallService(db, actor).update_triage(call_id, row_version, data)


@router.get(
    "/service-calls/machine-options",
    summary="Machines to pick when logging a call (search by serial or model)",
    dependencies=[Depends(require_permission(*CAN_VIEW_CALLS))],
)
def list_machine_options(
    query: Annotated[MachineOptionQuery, Query()],
    scope: ScopeDep,
    repo: ServiceCallRepo,
) -> list[MachineUnitOption]:
    return repo.machine_options(scope, query)


@router.get(
    "/service-calls/engineer-options",
    summary="Engineers a team lead can assign a call to",
    dependencies=[CAN_ASSIGN],
)
def list_engineer_options(
    query: Annotated[EngineerOptionQuery, Query()],
    scope: ScopeDep,
    repo: ServiceCallRepo,
) -> list[EngineerOption]:
    return repo.engineer_options(scope, query)


@router.get(
    "/service-calls/assigned-to-me",
    summary="Service calls assigned to the signed-in engineer",
    dependencies=[Depends(require_permission("svc.call.view.assigned"))],
)
def list_assigned_service_calls(
    query: Annotated[AssignedServiceCallQuery, Query()],
    user: CurrentUserDep,
    scope: ScopeDep,
    repo: ServiceCallRepo,
) -> Page[AssignedServiceCallListItem]:
    # Only an engineer (an app_user linked to an employee) has assigned calls; an office account
    # holding the permission but with no employee record gets an empty-by-definition list, so 403.
    if user.employee_id is None:
        raise Forbidden("Your account is not linked to a service engineer, so it has no assigned calls.")
    return repo.list_assigned(user.employee_id, scope, query)


@router.get(
    "/service-calls/{callId}/trips",
    summary="Trip history for a service call (all visits), with GPS and adjusted distance",
    responses=NOT_FOUND_RESPONSE,
    dependencies=[Depends(require_permission(*CAN_VIEW_CALL_TRIPS))],
)
def list_service_call_trips(
    call_id: CallId,
    user: CurrentUserDep,
    db: DbSession,
) -> list[CallTripHistoryItem]:
    return TripService(db).trips_for_service_call(user, call_id)


@router.post(
    "/service-calls/import/preview",
    summary="Dry run of a BYD service-call import (nothing is written)",
    dependencies=[CAN_IMPORT],
    responses={400: problem_response("The file is not a recognizable BYD export.")},
)
def preview_service_call_import(
    actor: CurrentUserDep,
    scope: ScopeDep,
    db: DbSession,
    file: Annotated[UploadFile, File(description="The BYD .xlsx export")],
    branch_id: UploadBranchId = None,
    principal_id: UploadPrincipalId = None,
) -> BydImportPreview:
    content = _read_upload(file)
    branch = _effective_branch_id(actor, scope, branch_id)
    return BydImportService(db, actor).preview(content, file.filename or "upload.xlsx", branch, principal_id)


@router.post(
    "/service-calls/import",
    summary="Import a BYD export, upserting calls on the C4C Ticket ID",
    status_code=201,
    dependencies=[CAN_IMPORT],
    responses={400: problem_response("The file is not a recognizable BYD export.")},
)
def apply_service_call_import(
    actor: CurrentUserDep,
    scope: ScopeDep,
    db: DbSession,
    file: Annotated[UploadFile, File(description="The BYD .xlsx export")],
    branch_id: UploadBranchId = None,
    principal_id: UploadPrincipalId = None,
) -> BydImportResult:
    content = _read_upload(file)
    branch = _effective_branch_id(actor, scope, branch_id)
    return BydImportService(db, actor).apply(content, file.filename or "upload.xlsx", branch, principal_id)


# Declared last so the literal GET paths above (machine-options, engineer-options, assigned-to-me)
# are matched before this {callId} route.
@router.get(
    "/service-calls/{callId}",
    summary="One service call, in full",
    dependencies=[CAN_OPEN_CALL],
    responses=NOT_FOUND_RESPONSE,
)
def get_service_call(call_id: CallId, actor: CurrentUserDep, db: DbSession) -> ServiceCallDetail:
    return ServiceCallService(db, actor).detail(call_id)


@router.get(
    "/service-calls/{callId}/status-history",
    summary="Every status change of a call, newest first",
    dependencies=[CAN_OPEN_CALL],
    responses=NOT_FOUND_RESPONSE,
)
def list_call_status_history(call_id: CallId, actor: CurrentUserDep, db: DbSession) -> list[CallStatusLogItem]:
    return ServiceCallService(db, actor).status_history(call_id)


@router.post(
    "/service-calls/{callId}/status",
    summary="Change a call's status (team lead: any call; engineer: their own)",
    dependencies=[CAN_OPEN_CALL],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def change_service_call_status(
    call_id: CallId,
    data: ServiceCallStatusChange,
    actor: CurrentUserDep,
    db: DbSession,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> ServiceCallDetail:
    return ServiceCallService(db, actor).change_status(call_id, row_version, data)
