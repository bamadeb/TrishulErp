from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query

from trishul_api.auth import CurrentUserDep, DbSession, ScopeDep, require_permission
from trishul_api.common.errors import NOT_FOUND_RESPONSE, problem_response
from trishul_api.common.schemas import Page
from trishul_api.modules.sal.common import QUOTATION_MANAGE
from trishul_api.modules.service.access import CAN_VIEW_CALLS
from trishul_api.modules.service.parts.schemas import (
    PartAvailability,
    PartRequestCall,
    PartRequestCreate,
    PartRequestListItem,
    PartRequestOut,
    PartRequestQuery,
    PartRequestQuotationCreate,
    PartRequestQuotationDraft,
    PartRequestQuotationOut,
    PartRequestReject,
)
from trishul_api.modules.service.parts.service import CAN_REQUEST_PARTS, CAN_REVIEW_PARTS, PartRequestService

router = APIRouter(prefix="/svc", tags=["service-parts"])

CallId = Annotated[int, Path(alias="callId", gt=0)]
PartRequestId = Annotated[int, Path(alias="partRequestId", gt=0)]
CAN_REVIEW = Depends(require_permission(CAN_REVIEW_PARTS))
ALREADY_REVIEWED: dict[int | str, dict[str, Any]] = {409: problem_response("The part was already quoted or rejected.")}


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


@router.get(
    "/service-calls/{callId}/part-availability",
    summary="Stock of parts for a call: in the warehouse supplying the call's branch and in the other warehouses",
    description="Quantities only, across all warehouses (not only the user's branches). Call it after the engineer "
    "picks the parts (GET /inv/items) and before sending the request; a request is allowed when stock is short.",
    dependencies=[Depends(require_permission(CAN_REQUEST_PARTS, CAN_REVIEW_PARTS))],
    responses={**NOT_FOUND_RESPONSE, 400: problem_response("An item is unknown or of another brand.")},
)
def list_part_availability(
    call_id: CallId,
    item_ids: Annotated[list[int], Query(alias="itemIds", min_length=1, max_length=50)],
    actor: CurrentUserDep,
    db: DbSession,
) -> list[PartAvailability]:
    return PartRequestService(db, actor).availability(call_id, item_ids)


@router.get(
    "/service-calls/{callId}/part-requests",
    summary="Parts requested on a service call, with what the office did with each",
    dependencies=[Depends(require_permission(*CAN_VIEW_CALLS, CAN_REQUEST_PARTS, CAN_REVIEW_PARTS))],
    responses=NOT_FOUND_RESPONSE,
)
def list_service_call_part_requests(call_id: CallId, actor: CurrentUserDep, db: DbSession) -> list[PartRequestListItem]:
    return PartRequestService(db, actor).of_call(call_id)


@router.get(
    "/part-requests",
    summary="All parts requests in the user's branches and brands, newest first (office review)",
    dependencies=[CAN_REVIEW],
)
def list_part_requests(
    query: Annotated[PartRequestQuery, Query()],
    actor: CurrentUserDep,
    scope: ScopeDep,
    db: DbSession,
) -> Page[PartRequestListItem]:
    return PartRequestService(db, actor).search(scope, query)


@router.get(
    "/part-request-calls",
    summary="Parts requests grouped by service call, latest request first (office review)",
    dependencies=[CAN_REVIEW],
)
def list_part_request_calls(
    query: Annotated[PartRequestQuery, Query()],
    actor: CurrentUserDep,
    scope: ScopeDep,
    db: DbSession,
) -> Page[PartRequestCall]:
    return PartRequestService(db, actor).calls(scope, query)


@router.get(
    "/part-request-quotation-draft",
    summary="What a quotation for these requested parts would be (prices filled in); nothing is saved",
    dependencies=[CAN_REVIEW, Depends(require_permission(QUOTATION_MANAGE))],
    responses={
        **NOT_FOUND_RESPONSE,
        **ALREADY_REVIEWED,
        400: problem_response("The parts are of different customers or brands."),
    },
)
def get_part_request_quotation_draft(
    part_request_ids: Annotated[list[int], Query(alias="partRequestIds", min_length=1, max_length=200)],
    actor: CurrentUserDep,
    db: DbSession,
) -> PartRequestQuotationDraft:
    return PartRequestService(db, actor).draft(part_request_ids)


@router.post(
    "/part-requests/{partRequestId}/reject",
    summary="Reject a requested part (it won't be supplied), with the reason",
    dependencies=[CAN_REVIEW],
    responses={**NOT_FOUND_RESPONSE, **ALREADY_REVIEWED},
)
def reject_part_request(
    part_request_id: PartRequestId,
    data: PartRequestReject,
    actor: CurrentUserDep,
    db: DbSession,
) -> PartRequestListItem:
    return PartRequestService(db, actor).reject(part_request_id, data)


@router.post(
    "/part-request-quotations",
    summary="Save the checked draft quotation for requested parts; the parts become Quoted",
    status_code=201,
    dependencies=[CAN_REVIEW, Depends(require_permission(QUOTATION_MANAGE))],
    responses={
        **NOT_FOUND_RESPONSE,
        **ALREADY_REVIEWED,
        400: problem_response("The parts are of another customer or brand than the quotation, or a line is invalid."),
    },
)
def create_part_request_quotation(
    data: PartRequestQuotationCreate,
    actor: CurrentUserDep,
    db: DbSession,
) -> PartRequestQuotationOut:
    return PartRequestService(db, actor).quote(data)
