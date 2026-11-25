"""Raise complaints, list them, show one with its history, change the status, maintain issue types."""

from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, aliased

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, Forbidden, NotFound
from trishul_api.common.numbering import next_document_no
from trishul_api.common.schemas import Page
from trishul_api.db.audit import audit_source
from trishul_api.db.models import (
    AppUser,
    Attachment,
    Branch,
    Complaint,
    ComplaintHistory,
    ComplaintIssueType,
    Department,
    Designation,
    Employee,
)
from trishul_api.modules.core.complaints import alerts
from trishul_api.modules.core.complaints.access import RAISE, ComplaintAccess, complaint_access
from trishul_api.modules.core.complaints.schemas import (
    OPEN_STATUSES,
    STATUSES,
    ComplaintAccessOut,
    ComplaintCreate,
    ComplaintDepartmentOption,
    ComplaintDepartmentRef,
    ComplaintDetail,
    ComplaintHistoryItem,
    ComplaintIssueTypeCreate,
    ComplaintIssueTypeItem,
    ComplaintIssueTypeOption,
    ComplaintIssueTypeQuery,
    ComplaintIssueTypeUpdate,
    ComplaintListItem,
    ComplaintQuery,
    ComplaintRaisedBy,
    ComplaintStatusChange,
    MyComplaintQuery,
)

ENTITY_TYPE = "core.complaint"
DOCUMENT_TYPE = "COMPLAINT"

_RAISER = aliased(Employee)
_SORT = {
    "raisedAt": Complaint.raised_at,
    "complaintNo": Complaint.complaint_no,
    "status": Complaint.status,
    "statusChangedAt": Complaint.status_changed_at,
}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _name(first: str | None, last: str | None, fallback: str) -> str:
    return " ".join(p for p in (first, last) if p) or fallback


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def allowed_statuses(current: str) -> list[Any]:
    """Any other status, until the complaint is Closed (final)."""
    if current == "Closed":
        return []
    return [s for s in STATUSES if s != current]


class ComplaintService:
    def __init__(self, db: Session, user: CurrentUser) -> None:
        self._db = db
        self._user = user
        self._access: ComplaintAccess | None = None

    @property
    def access(self) -> ComplaintAccess:
        if self._access is None:
            self._access = complaint_access(self._db, self._user)
        return self._access

    # ------------------------------------------------------------------ what the user may do

    def my_access(self) -> ComplaintAccessOut:
        access = self.access
        statement = select(Department.id, Department.name).where(Department.is_active).order_by(Department.name)
        if not access.all_departments:
            statement = statement.where(Department.id.in_(access.led_department_ids or {0}))
        departments = [
            ComplaintDepartmentRef(id=r.id, name=r.name, is_head=r.id in access.head_department_ids)
            for r in self._db.execute(statement)
        ]
        return ComplaintAccessOut(
            can_raise=self._user.can(RAISE),
            can_manage_all=access.all_departments,
            managed_departments=departments if access.manages_any else [],
        )

    def departments(self) -> list[ComplaintDepartmentOption]:
        """Active departments that have at least one active issue type, for the raise form."""
        rows = self._db.execute(
            select(Department.id, Department.code, Department.name, ComplaintIssueType)
            .join(ComplaintIssueType, ComplaintIssueType.department_id == Department.id)
            .where(Department.is_active, ComplaintIssueType.is_active)
            .order_by(Department.name, ComplaintIssueType.sort_order, ComplaintIssueType.name)
        ).all()
        options: dict[int, ComplaintDepartmentOption] = {}
        for row in rows:
            option = options.setdefault(
                row.id, ComplaintDepartmentOption(id=row.id, code=row.code, name=row.name, issue_types=[])
            )
            issue: ComplaintIssueType = row.ComplaintIssueType
            option.issue_types.append(
                ComplaintIssueTypeOption(id=issue.id, name=issue.name, description=issue.description)
            )
        return list(options.values())

    # ------------------------------------------------------------------ raise

    def create(self, data: ComplaintCreate) -> ComplaintDetail:
        department = self._db.get(Department, data.department_id)
        if department is None or not department.is_active:
            raise ApiError("Choose a department.", errors={"departmentId": ["Choose a department."]})
        issue = self._db.get(ComplaintIssueType, data.issue_type_id)
        if issue is None or not issue.is_active or issue.department_id != department.id:
            raise ApiError(
                "Choose an issue type of this department.",
                errors={"issueTypeId": ["Choose an issue type of this department."]},
            )
        company_id, branch_id = self._raiser_company()
        now = _now()
        complaint = Complaint(
            company_id=company_id,
            complaint_no=next_document_no(
                self._db, company_id=company_id, document_type=DOCUMENT_TYPE, branch_id=branch_id
            ),
            department_id=department.id,
            issue_type_id=issue.id,
            description=data.description,
            status="Open",
            raised_by_user_id=self._user.id,
            raised_by_employee_id=self._user.employee_id,
            branch_id=branch_id,
            raised_at=now,
            raised_via=audit_source(self._db) if audit_source(self._db) in ("Web", "Android", "iOS", "API") else None,
            created_at=now,
            created_by_user_id=self._user.id,
        )
        self._db.add(complaint)
        self._db.flush()
        self._db.add(
            ComplaintHistory(
                complaint_id=complaint.id,
                action="Raised",
                from_status=None,
                to_status="Open",
                note=None,
                changed_by_user_id=self._user.id,
                changed_at=now,
            )
        )
        self._db.flush()
        alerts.complaint_raised(
            self._db,
            complaint,
            raised_by=self._user.display_name,
            department=department.name,
            issue_type=issue.name,
            now=now,
        )
        self._db.commit()
        return self.get(complaint.id)

    def _raiser_company(self) -> tuple[int, int]:
        """The company and branch the complaint belongs to (its number comes from the branch's series): the
        raiser's employee record, else their default branch."""
        if self._user.employee_id is not None:
            employee = self._db.get(Employee, self._user.employee_id)
            if employee is not None and employee.branch_id is not None:
                return employee.company_id, employee.branch_id
        if self._user.default_branch_id is not None:
            branch = self._db.get(Branch, self._user.default_branch_id)
            if branch is not None:
                return branch.company_id, branch.id
        raise ApiError("Your account is not linked to an employee or a branch, so it cannot raise complaints.")

    # ------------------------------------------------------------------ lists

    def _list_select(self) -> Any:  # a Select of many columns; typed rows add nothing here
        attachments = (
            select(func.count(Attachment.id))
            .where(
                Attachment.entity_type == ENTITY_TYPE,
                Attachment.entity_id == Complaint.id,
                Attachment.is_active,
            )
            .correlate(Complaint)
            .scalar_subquery()
        )
        return (
            select(
                Complaint.id,
                Complaint.complaint_no,
                Complaint.department_id,
                Department.name.label("department_name"),
                Complaint.issue_type_id,
                ComplaintIssueType.name.label("issue_type_name"),
                Complaint.description,
                Complaint.status,
                Complaint.raised_at,
                Complaint.raised_by_user_id,
                AppUser.username,
                _RAISER.first_name,
                _RAISER.last_name,
                _RAISER.employee_code.label("raised_by_employee_code"),
                Complaint.status_changed_at,
                attachments.label("attachment_count"),
            )
            .join(Department, Department.id == Complaint.department_id)
            .join(ComplaintIssueType, ComplaintIssueType.id == Complaint.issue_type_id)
            .join(AppUser, AppUser.id == Complaint.raised_by_user_id)
            .outerjoin(_RAISER, _RAISER.id == Complaint.raised_by_employee_id)
            .where(Complaint.is_active)
        )

    def _page(
        self,
        statement: Select[Any],
        *,
        page: int,
        page_size: int,
        sort: str | None,
        search: str | None,
        statuses: list[str] | None,
        open_only: bool,
    ) -> Page[ComplaintListItem]:
        if statuses:
            statement = statement.where(Complaint.status.in_(statuses))
        if open_only:
            statement = statement.where(Complaint.status.in_(OPEN_STATUSES))
        if search and search.strip():
            pattern = _like(search.strip())
            statement = statement.where(
                or_(
                    Complaint.complaint_no.like(pattern, escape="\\"),
                    Complaint.description.like(pattern, escape="\\"),
                    _RAISER.first_name.like(pattern, escape="\\"),
                    _RAISER.last_name.like(pattern, escape="\\"),
                    _RAISER.employee_code.like(pattern, escape="\\"),
                    AppUser.username.like(pattern, escape="\\"),
                )
            )
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        key = (sort or "-raisedAt").lstrip("-")
        column = _SORT.get(key)
        if column is None:
            raise ApiError(f"Cannot sort by '{key}'.", errors={"sort": [f"Use one of: {', '.join(_SORT)}."]})
        order = column.desc() if (sort or "-raisedAt").startswith("-") else column.asc()
        rows = self._db.execute(
            statement.order_by(order, Complaint.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
        items = [
            ComplaintListItem(
                id=r.id,
                complaint_no=r.complaint_no,
                department_id=r.department_id,
                department_name=r.department_name,
                issue_type_id=r.issue_type_id,
                issue_type_name=r.issue_type_name,
                description=r.description,
                status=r.status,
                raised_at=r.raised_at,
                raised_by_user_id=r.raised_by_user_id,
                raised_by_name=_name(r.first_name, r.last_name, r.username),
                raised_by_employee_code=r.raised_by_employee_code,
                status_changed_at=r.status_changed_at,
                attachment_count=r.attachment_count or 0,
            )
            for r in rows
        ]
        return Page(items=items, total=total, page=page, page_size=page_size)

    def mine(self, query: MyComplaintQuery) -> Page[ComplaintListItem]:
        statement = self._list_select().where(Complaint.raised_by_user_id == self._user.id)
        return self._page(
            statement,
            page=query.page,
            page_size=query.page_size,
            sort=query.sort,
            search=query.search,
            statuses=list(query.status or []),
            open_only=query.open_only,
        )

    def department_list(self, query: ComplaintQuery) -> Page[ComplaintListItem]:
        access = self.access
        if not access.manages_any:
            raise Forbidden("You do not manage the complaints of any department.")
        statement = self._list_select()
        if not access.all_departments:
            statement = statement.where(Complaint.department_id.in_(access.led_department_ids))
        if query.department_id is not None:
            statement = statement.where(Complaint.department_id == query.department_id)
        if query.issue_type_id is not None:
            statement = statement.where(Complaint.issue_type_id == query.issue_type_id)
        if query.raised_from is not None:
            statement = statement.where(Complaint.raised_at >= _utc_start(query.raised_from))
        if query.raised_to is not None:
            statement = statement.where(Complaint.raised_at < _utc_start(query.raised_to) + timedelta(days=1))
        return self._page(
            statement,
            page=query.page,
            page_size=query.page_size,
            sort=query.sort,
            search=query.search,
            statuses=list(query.status or []),
            open_only=query.open_only,
        )

    # ------------------------------------------------------------------ one complaint

    def _visible(self, complaint_id: int) -> Complaint:
        complaint = self._db.get(Complaint, complaint_id)
        if (
            complaint is None
            or not complaint.is_active
            or (complaint.raised_by_user_id != self._user.id and not self.access.manages(complaint.department_id))
        ):
            raise NotFound("Complaint not found.")
        return complaint

    def can_attach(self, complaint: Complaint) -> bool:
        """The person who raised it while it is open; the department's leaders until it is Closed."""
        if self.access.manages(complaint.department_id):
            return complaint.status != "Closed"
        return complaint.raised_by_user_id == self._user.id and complaint.status in OPEN_STATUSES

    def get(self, complaint_id: int) -> ComplaintDetail:
        complaint = self._visible(complaint_id)
        department = self._db.get(Department, complaint.department_id)
        issue = self._db.get(ComplaintIssueType, complaint.issue_type_id)
        can_manage = self.access.manages(complaint.department_id)
        return ComplaintDetail(
            id=complaint.id,
            complaint_no=complaint.complaint_no,
            department_id=complaint.department_id,
            department_name=department.name if department else "",
            issue_type_id=complaint.issue_type_id,
            issue_type_name=issue.name if issue else "",
            description=complaint.description,
            status=complaint.status,
            raised_at=complaint.raised_at,
            raised_via=complaint.raised_via,
            raised_by=self._raised_by(complaint),
            status_changed_at=complaint.status_changed_at,
            resolved_at=complaint.resolved_at,
            closed_at=complaint.closed_at,
            history=self._history(complaint.id),
            can_manage=can_manage,
            can_attach=self.can_attach(complaint),
            allowed_statuses=allowed_statuses(complaint.status) if can_manage else [],
            row_version=complaint.row_version,
        )

    def _raised_by(self, complaint: Complaint) -> ComplaintRaisedBy:
        user = self._db.get(AppUser, complaint.raised_by_user_id)
        employee = self._db.get(Employee, complaint.raised_by_employee_id) if complaint.raised_by_employee_id else None
        branch = self._db.get(Branch, employee.branch_id) if employee and employee.branch_id else None
        department = self._db.get(Department, employee.department_id) if employee and employee.department_id else None
        designation = (
            self._db.get(Designation, employee.designation_id) if employee and employee.designation_id else None
        )
        username = user.username if user else ""
        return ComplaintRaisedBy(
            user_id=complaint.raised_by_user_id,
            name=_name(employee.first_name, employee.last_name, username) if employee else username,
            employee_id=employee.id if employee else None,
            employee_code=employee.employee_code if employee else None,
            mobile=(employee.mobile if employee else None) or (user.mobile if user else None),
            email=(employee.email if employee else None) or (user.email if user else None),
            branch_name=branch.name if branch else None,
            department_name=department.name if department else None,
            designation_name=designation.name if designation else None,
        )

    def _history(self, complaint_id: int) -> list[ComplaintHistoryItem]:
        rows = self._db.execute(
            select(ComplaintHistory, AppUser.username, Employee.first_name, Employee.last_name)
            .join(AppUser, AppUser.id == ComplaintHistory.changed_by_user_id)
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .where(ComplaintHistory.complaint_id == complaint_id)
            .order_by(ComplaintHistory.changed_at, ComplaintHistory.id)
        ).all()
        return [
            ComplaintHistoryItem(
                id=h.id,
                action=h.action,
                from_status=h.from_status,
                to_status=h.to_status,
                note=h.note,
                changed_by_user_id=h.changed_by_user_id,
                changed_by_name=_name(first, last, username),
                changed_at=h.changed_at,
            )
            for h, username, first, last in rows
        ]

    # ------------------------------------------------------------------ status

    def change_status(self, complaint_id: int, data: ComplaintStatusChange) -> ComplaintDetail:
        complaint = self._visible(complaint_id)
        if not self.access.manages(complaint.department_id):
            raise Forbidden("Only the department's leaders can change this complaint.")
        if data.row_version is not None:
            check_row_version(complaint.row_version, data.row_version)
        note = (data.note or "").strip() or None
        previous = complaint.status
        if data.status == previous:
            if note is None:
                raise ApiError("Choose a new status or write a note.", errors={"status": ["The status is unchanged."]})
            if previous == "Closed":
                raise ApiError("This complaint is closed.")
            action = "Note"
        else:
            if data.status not in allowed_statuses(previous):
                raise ApiError(
                    f"A {previous.lower()} complaint cannot be changed.",
                    errors={"status": [f"A {previous.lower()} complaint cannot be changed."]},
                )
            action = "Status changed"
        now = _now()
        if action == "Status changed":
            complaint.status = data.status
            complaint.status_changed_at = now
            if data.status == "Resolved":
                complaint.resolved_at = now
            elif data.status == "Closed":
                complaint.closed_at = now
                complaint.resolved_at = complaint.resolved_at or now
            else:
                complaint.resolved_at = None  # reopened
        complaint.updated_at = now
        complaint.updated_by_user_id = self._user.id
        history = ComplaintHistory(
            complaint_id=complaint.id,
            action=action,
            from_status=previous,
            to_status=complaint.status,
            note=note,
            changed_by_user_id=self._user.id,
            changed_at=now,
        )
        self._db.add(history)
        self._db.flush()
        alerts.complaint_updated(
            self._db,
            complaint,
            history_id=history.id,
            from_status=previous,
            note=note,
            changed_by_user_id=self._user.id,
            changed_by=self._user.display_name,
            now=now,
        )
        self._db.commit()
        return self.get(complaint.id)

    # ------------------------------------------------------------------ issue types

    def issue_types(self, query: ComplaintIssueTypeQuery) -> list[ComplaintIssueTypeItem]:
        used = (
            select(func.count(Complaint.id))
            .where(Complaint.issue_type_id == ComplaintIssueType.id)
            .correlate(ComplaintIssueType)
            .scalar_subquery()
        )
        statement = (
            select(ComplaintIssueType, Department.name, used.label("used"))
            .join(Department, Department.id == ComplaintIssueType.department_id)
            .order_by(Department.name, ComplaintIssueType.sort_order, ComplaintIssueType.name)
        )
        if query.department_id is not None:
            statement = statement.where(ComplaintIssueType.department_id == query.department_id)
        if query.status == "active":
            statement = statement.where(ComplaintIssueType.is_active)
        elif query.status == "inactive":
            statement = statement.where(~ComplaintIssueType.is_active)
        return [self._issue_out(row, name, used or 0) for row, name, used in self._db.execute(statement)]

    def _issue_out(self, row: ComplaintIssueType, department_name: str, used: int) -> ComplaintIssueTypeItem:
        return ComplaintIssueTypeItem(
            id=row.id,
            department_id=row.department_id,
            department_name=department_name,
            name=row.name,
            description=row.description,
            sort_order=row.sort_order,
            is_active=row.is_active,
            complaint_count=used,
            row_version=row.row_version,
        )

    def _issue_item(self, issue_id: int) -> ComplaintIssueTypeItem:
        for item in self.issue_types(ComplaintIssueTypeQuery(status="all")):
            if item.id == issue_id:
                return item
        raise NotFound("Issue type not found.")

    def _check_unique(self, department_id: int, name: str, exclude_id: int | None = None) -> None:
        statement = select(ComplaintIssueType.id).where(
            ComplaintIssueType.department_id == department_id,
            ComplaintIssueType.name == name,
            ComplaintIssueType.is_active,
        )
        if exclude_id is not None:
            statement = statement.where(ComplaintIssueType.id != exclude_id)
        if self._db.scalar(statement) is not None:
            raise ApiError(
                "This department already has an issue type with that name.",
                errors={"name": ["This department already has an issue type with that name."]},
            )

    def create_issue_type(self, data: ComplaintIssueTypeCreate) -> ComplaintIssueTypeItem:
        department = self._db.get(Department, data.department_id)
        if department is None or not department.is_active:
            raise ApiError("Choose a department.", errors={"departmentId": ["Choose a department."]})
        self._check_unique(department.id, data.name)
        now = _now()
        row = ComplaintIssueType(
            department_id=department.id,
            name=data.name,
            description=(data.description or "").strip() or None,
            sort_order=data.sort_order,
            created_at=now,
            created_by_user_id=self._user.id,
        )
        self._db.add(row)
        self._db.commit()
        return self._issue_item(row.id)

    def update_issue_type(
        self, issue_id: int, expected: bytes, data: ComplaintIssueTypeUpdate
    ) -> ComplaintIssueTypeItem:
        row = self._db.get(ComplaintIssueType, issue_id)
        if row is None:
            raise NotFound("Issue type not found.")
        check_row_version(row.row_version, expected)
        fields = data.model_dump(exclude_unset=True)
        name = fields.get("name", row.name)
        if fields.get("is_active", row.is_active) and ("name" in fields or fields.get("is_active")):
            self._check_unique(row.department_id, name, exclude_id=row.id)
        if "name" in fields:
            row.name = data.name  # type: ignore[assignment]
        if "description" in fields:
            row.description = (data.description or "").strip() or None
        if "sort_order" in fields and data.sort_order is not None:
            row.sort_order = data.sort_order
        if "is_active" in fields and data.is_active is not None:
            row.is_active = data.is_active
        row.updated_at = _now()
        row.updated_by_user_id = self._user.id
        self._db.commit()
        return self._issue_item(row.id)


def _utc_start(day: Any) -> datetime:
    """Midnight India time of a date, in UTC (the dates people pick are Indian dates)."""
    return datetime.combine(day, time()) - timedelta(hours=5, minutes=30)
