from typing import Annotated

from fastapi import APIRouter, Depends, Query

from trishul_api.auth import CurrentUserDep, DbSession, ScopeDep, require_permission
from trishul_api.common.errors import Forbidden
from trishul_api.common.schemas import Page
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


def get_service_call_repository(db: DbSession) -> ServiceCallRepository:
    return ServiceCallRepository(db)


ServiceCallRepo = Annotated[ServiceCallRepository, Depends(get_service_call_repository)]


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
