from typing import Annotated

from fastapi import APIRouter, Depends, Query

from trishul_api.auth import DbSession, ScopeDep, require_permission
from trishul_api.common.schemas import Page
from trishul_api.modules.service.repository import ServiceCallRepository
from trishul_api.modules.service.schemas import ServiceCallListItem, ServiceCallQuery

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
