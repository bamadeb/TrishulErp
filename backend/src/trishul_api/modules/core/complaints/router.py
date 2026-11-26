"""Complaint endpoints. Attachments go through /core/documents with entityType 'core.complaint'.

Raising a complaint and seeing one's own are open to every signed-in user, whatever their role: anyone can have
a complaint. Department complaints are open at the route too: a department head leads complaints without any
permission code, so the service decides (403 if the user leads no department, 404 for a complaint they may not
open).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import SIGNED_IN_USERS, CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.modules.core.complaints import documents  # noqa: F401  (registers the attachment target)
from trishul_api.modules.core.complaints.access import MANAGE_ALL
from trishul_api.modules.core.complaints.schemas import (
    ComplaintAccessOut,
    ComplaintCreate,
    ComplaintDepartmentOption,
    ComplaintDetail,
    ComplaintIssueTypeCreate,
    ComplaintIssueTypeItem,
    ComplaintIssueTypeQuery,
    ComplaintIssueTypeUpdate,
    ComplaintListItem,
    ComplaintQuery,
    ComplaintStatusChange,
    MyComplaintQuery,
)
from trishul_api.modules.core.complaints.service import ComplaintService

router = APIRouter(prefix="/core", tags=["Complaints"])

CAN_MANAGE_ALL = Depends(require_permission(MANAGE_ALL))

ComplaintId = Annotated[int, Path(alias="complaintId", gt=0)]
IssueTypeId = Annotated[int, Path(alias="issueTypeId", gt=0)]


def get_complaint_service(db: DbSession, user: CurrentUserDep) -> ComplaintService:
    return ComplaintService(db, user)


Complaints = Annotated[ComplaintService, Depends(get_complaint_service)]


@router.get(
    "/complaint-access",
    summary="What the signed-in user may do with complaints (raise, which departments they manage)",
    openapi_extra=SIGNED_IN_USERS,
)
def get_complaint_access(complaints: Complaints) -> ComplaintAccessOut:
    return complaints.my_access()


@router.get(
    "/complaint-departments",
    summary="Departments a complaint can be raised to, with their issue types",
    openapi_extra=SIGNED_IN_USERS,
)
def list_complaint_departments(complaints: Complaints) -> list[ComplaintDepartmentOption]:
    return complaints.departments()


@router.post(
    "/complaints",
    summary="Raise a complaint (then attach files through /core/documents, entityType core.complaint)",
    status_code=201,
    openapi_extra=SIGNED_IN_USERS,
)
def create_complaint(data: ComplaintCreate, complaints: Complaints, response: Response) -> ComplaintDetail:
    created = complaints.create(data)
    response.headers["Location"] = f"complaints/{created.id}"
    return created


@router.get("/my-complaints", summary="The signed-in user's own complaints", openapi_extra=SIGNED_IN_USERS)
def list_my_complaints(query: Annotated[MyComplaintQuery, Query()], complaints: Complaints) -> Page[ComplaintListItem]:
    return complaints.mine(query)


@router.get(
    "/complaints",
    summary="Complaints of the departments the user leads (every department for a Super Admin)",
    openapi_extra=SIGNED_IN_USERS,
)
def list_complaints(query: Annotated[ComplaintQuery, Query()], complaints: Complaints) -> Page[ComplaintListItem]:
    return complaints.department_list(query)


@router.get(
    "/complaints/{complaintId}",
    summary="One complaint with the person who raised it and its full history",
    responses=NOT_FOUND_RESPONSE,
    openapi_extra=SIGNED_IN_USERS,
)
def get_complaint(complaint_id: ComplaintId, complaints: Complaints) -> ComplaintDetail:
    return complaints.get(complaint_id)


@router.post(
    "/complaints/{complaintId}/status",
    summary="Change a complaint's status and/or add a note (the department's leaders)",
    responses=NOT_FOUND_RESPONSE,
    openapi_extra=SIGNED_IN_USERS,
)
def change_complaint_status(
    complaint_id: ComplaintId, data: ComplaintStatusChange, complaints: Complaints
) -> ComplaintDetail:
    return complaints.change_status(complaint_id, data)


@router.get(
    "/complaint-issue-types",
    summary="Issue types per department (Super Admin)",
    dependencies=[CAN_MANAGE_ALL],
)
def list_complaint_issue_types(
    query: Annotated[ComplaintIssueTypeQuery, Query()], complaints: Complaints
) -> list[ComplaintIssueTypeItem]:
    return complaints.issue_types(query)


@router.post(
    "/complaint-issue-types",
    summary="Add an issue type to a department",
    status_code=201,
    dependencies=[CAN_MANAGE_ALL],
)
def create_complaint_issue_type(
    data: ComplaintIssueTypeCreate, complaints: Complaints, response: Response
) -> ComplaintIssueTypeItem:
    created = complaints.create_issue_type(data)
    response.headers["Location"] = f"complaint-issue-types/{created.id}"
    return created


@router.patch(
    "/complaint-issue-types/{issueTypeId}",
    summary="Rename, reorder, or switch an issue type off or on",
    dependencies=[CAN_MANAGE_ALL],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_complaint_issue_type(
    issue_type_id: IssueTypeId,
    data: ComplaintIssueTypeUpdate,
    complaints: Complaints,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> ComplaintIssueTypeItem:
    return complaints.update_issue_type(issue_type_id, row_version, data)
