from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from trishul_api.auth import CurrentUser, CurrentUserDep, DbSession, ScopeDep, require_permission
from trishul_api.common.errors import ApiError, Forbidden, problem_response
from trishul_api.common.schemas import Page
from trishul_api.modules.service.imports.schemas import BydImportPreview, BydImportResult
from trishul_api.modules.service.imports.service import BydImportService
from trishul_api.modules.service.repository import ServiceCallRepository
from trishul_api.modules.service.schemas import (
    AssignedServiceCallListItem,
    AssignedServiceCallQuery,
    ServiceCallListItem,
    ServiceCallQuery,
)

router = APIRouter(prefix="/svc", tags=["service"])

# Any of these may open the call register (svc.call.view comes from migration 0001). The Angular
# guard and menu use the same codes: SERVICE_CALL_VIEW_PERMISSIONS in libs/domains/service/data-access.
CAN_VIEW_CALLS = ("svc.call.view", "svc.call.create", "svc.call.assign")
CAN_IMPORT = Depends(require_permission("svc.call.import"))

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
