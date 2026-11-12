from typing import Annotated

from fastapi import APIRouter, Depends, Path

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.errors import NOT_FOUND_RESPONSE, problem_response
from trishul_api.modules.service.parts.schemas import PartRequestCreate, PartRequestOut
from trishul_api.modules.service.parts.service import CAN_REQUEST_PARTS, PartRequestService

router = APIRouter(prefix="/svc", tags=["service-parts"])

CallId = Annotated[int, Path(alias="callId", gt=0)]


@router.post(
    "/service-calls/{callId}/part-requests",
    summary="Request spare parts for a service call (engineer on the call, from the mobile app)",
    dependencies=[Depends(require_permission(CAN_REQUEST_PARTS))],
    responses={
        **NOT_FOUND_RESPONSE,
        400: problem_response("A part, unit or visit is not valid for this call, or the call is finished."),
    },
)
def create_part_requests(
    call_id: CallId,
    data: PartRequestCreate,
    actor: CurrentUserDep,
    db: DbSession,
) -> list[PartRequestOut]:
    return PartRequestService(db, actor).create(call_id, data)
