from datetime import date
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models.complaint import ComplaintHistoryAction, ComplaintStatus

STATUSES: tuple[ComplaintStatus, ...] = ("Open", "In Progress", "On Hold", "Resolved", "Closed")
OPEN_STATUSES: tuple[ComplaintStatus, ...] = ("Open", "In Progress", "On Hold")

# ---------------------------------------------------------------- the raise form


class ComplaintIssueTypeOption(ApiModel):
    id: int
    name: str
    description: str | None


class ComplaintDepartmentOption(ApiModel):
    """A department a complaint can be raised to, with its active issue types."""

    id: int
    code: str
    name: str
    issue_types: list[ComplaintIssueTypeOption]


class ComplaintAccessOut(ApiModel):
    """What the signed-in user may do with complaints, for menus and buttons."""

    can_raise: bool
    can_manage_all: bool
    managed_departments: list["ComplaintDepartmentRef"] = Field(
        description="Departments whose complaints the user works (all of them for a Super Admin)."
    )


class ComplaintDepartmentRef(ApiModel):
    id: int
    name: str
    is_head: bool = Field(False, description="The user is the department's head.")


class ComplaintCreate(InputModel):
    department_id: int = Field(gt=0)
    issue_type_id: int = Field(gt=0)
    description: str = Field(min_length=5, max_length=2000, description="What the issue is, in detail.")


# ---------------------------------------------------------------- lists


class ComplaintQuery(PageQuery):
    """Department complaints. Sort: raisedAt (default -raisedAt), complaintNo, status, statusChangedAt."""

    status: list[ComplaintStatus] | None = Field(None, description="Leave empty for every status.")
    open_only: bool = Field(False, description="Only Open, In Progress and On Hold.")
    department_id: int | None = Field(None, gt=0)
    issue_type_id: int | None = Field(None, gt=0)
    raised_from: date | None = None
    raised_to: date | None = None


class MyComplaintQuery(PageQuery):
    status: list[ComplaintStatus] | None = None
    open_only: bool = False


class ComplaintListItem(ApiModel):
    id: int
    complaint_no: str
    department_id: int
    department_name: str
    issue_type_id: int
    issue_type_name: str
    description: str
    status: ComplaintStatus
    raised_at: UtcDateTime
    raised_by_user_id: int
    raised_by_name: str
    raised_by_employee_code: str | None
    status_changed_at: UtcDateTime | None
    attachment_count: int = 0


# ---------------------------------------------------------------- detail


class ComplaintRaisedBy(ApiModel):
    user_id: int
    name: str
    employee_id: int | None
    employee_code: str | None
    mobile: str | None
    email: str | None
    branch_name: str | None
    department_name: str | None
    designation_name: str | None


class ComplaintHistoryItem(ApiModel):
    id: int
    action: ComplaintHistoryAction
    from_status: ComplaintStatus | None
    to_status: ComplaintStatus
    note: str | None
    changed_by_user_id: int
    changed_by_name: str
    changed_at: UtcDateTime


class ComplaintDetail(ApiModel):
    id: int
    complaint_no: str
    department_id: int
    department_name: str
    issue_type_id: int
    issue_type_name: str
    description: str
    status: ComplaintStatus
    raised_at: UtcDateTime
    raised_via: str | None
    raised_by: ComplaintRaisedBy
    status_changed_at: UtcDateTime | None
    resolved_at: UtcDateTime | None
    closed_at: UtcDateTime | None
    history: list[ComplaintHistoryItem]
    can_manage: bool = Field(description="The signed-in user may change the status or add a note.")
    can_attach: bool = Field(description="The signed-in user may add or remove attachments.")
    allowed_statuses: list[ComplaintStatus] = Field(
        description="Statuses the complaint can move to now (empty once Closed, or if the user cannot manage it)."
    )
    row_version: RowVersion


class ComplaintStatusChange(InputModel):
    """Change the status, add a note, or both. A note alone keeps the status (send the current one)."""

    status: ComplaintStatus
    note: str | None = Field(None, max_length=1000, description="Optional; shown to the person who raised it.")
    row_version: RowVersion | None = Field(
        None, description="The rowVersion the user saw; if sent and the complaint has changed since, 409."
    )


# ---------------------------------------------------------------- issue types (Super Admin)


IssueTypeStatusFilter = Literal["active", "inactive", "all"]


class ComplaintIssueTypeQuery(ApiModel):
    department_id: int | None = Field(None, gt=0)
    status: IssueTypeStatusFilter = "active"


class ComplaintIssueTypeItem(ApiModel):
    id: int
    department_id: int
    department_name: str
    name: str
    description: str | None
    sort_order: int
    is_active: bool
    complaint_count: int = 0
    row_version: RowVersion


class ComplaintIssueTypeCreate(InputModel):
    department_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=80)
    description: str | None = Field(None, max_length=300)
    sort_order: int = Field(0, ge=0, le=9999)


class ComplaintIssueTypeUpdate(InputModel):
    """Only the fields sent are changed. The department cannot be changed."""

    name: str | None = Field(None, min_length=2, max_length=80)
    description: str | None = Field(None, max_length=300)
    sort_order: int | None = Field(None, ge=0, le=9999)
    is_active: bool | None = None


ComplaintAccessOut.model_rebuild()
