"""Saves a reporting manager on the employee and records the assignment."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError, NotFound
from trishul_api.db.models import AppUser, Employee, ReportingAssignment
from trishul_api.modules.hr.organization.repository import OrganizationRepository
from trishul_api.modules.hr.organization.schemas import HierarchyListItem, OrganizationQuery
from trishul_api.modules.hr.reporting.schemas import (
    ReportingAssignmentCreate,
    ReportingAssignmentSaved,
    ReportingEmployee,
    ReportingHistoryItem,
    ReportingRemovalCreate,
)

_PAGE = 200


class ReportingService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._org = OrganizationRepository(db)

    def list_employees(self) -> list[ReportingEmployee]:
        rows: list[HierarchyListItem] = []
        page = 1
        while True:
            result = self._org.search_hierarchy(OrganizationQuery(page=page, page_size=_PAGE, status="all"))
            rows.extend(result.items)
            if len(rows) >= result.total or not result.items:
                break
            page += 1
        upcoming = self._upcoming({row.id for row in rows})
        return [_employee(row, upcoming.get(row.id)) for row in rows]

    def _upcoming(self, ids: set[int]) -> dict[int, date]:
        if not ids:
            return {}
        today = date.today()
        rows = self._db.execute(
            select(ReportingAssignment.employee_id, ReportingAssignment.effective_from).where(
                ReportingAssignment.employee_id.in_(ids),
                ReportingAssignment.is_active == True,  # noqa: E712
                ReportingAssignment.effective_to.is_(None),
                ReportingAssignment.manager_id.is_not(None),
                ReportingAssignment.effective_from > today,
            )
        ).all()
        found: dict[int, date] = {}
        for employee_id, effective_from in rows:
            current = found.get(employee_id)
            if current is None or effective_from > current:
                found[employee_id] = effective_from
        return found

    def history(self, employee_id: int) -> list[ReportingHistoryItem]:
        employee = self._db.get(Employee, employee_id)
        if employee is None:
            raise NotFound("Employee not found.")
        rows = self._db.scalars(
            select(ReportingAssignment)
            .where(ReportingAssignment.employee_id == employee_id, ReportingAssignment.is_active == True)  # noqa: E712
            .order_by(ReportingAssignment.id.desc())
        ).all()
        names = self._names({row_id for row in rows for row_id in (row.previous_manager_id, row.manager_id) if row_id})
        authors = self._authors({row.created_by_user_id for row in rows if row.created_by_user_id})
        return [_history_item(row, names, authors, employee.reporting_manager_id) for row in rows]

    def assign(self, actor: CurrentUser, data: ReportingAssignmentCreate) -> ReportingAssignmentSaved:
        employee = self._db.get(Employee, data.employee_id)
        if employee is None:
            raise NotFound("Employee not found.")
        self._check_manager(employee.id, data.reporting_manager_id)
        previous = employee.reporting_manager_id
        remarks = (data.remarks or "").strip() or None
        self._close_open(employee.id, data.effective_from)
        employee.reporting_manager_id = data.reporting_manager_id
        employee.updated_at = datetime.now(UTC).replace(tzinfo=None)
        employee.updated_by_user_id = actor.id
        self._db.add(
            ReportingAssignment(
                employee_id=employee.id,
                previous_manager_id=previous,
                manager_id=data.reporting_manager_id,
                effective_from=data.effective_from,
                remarks=remarks,
                created_by_user_id=actor.id,
                is_active=True,
            )
        )
        self._db.commit()
        return ReportingAssignmentSaved(
            employee_id=employee.id,
            previous_manager_id=previous,
            manager_id=data.reporting_manager_id,
            effective_from=data.effective_from,
            remarks=remarks,
        )

    def remove(self, actor: CurrentUser, data: ReportingRemovalCreate) -> ReportingAssignmentSaved:
        employee = self._db.get(Employee, data.employee_id)
        if employee is None:
            raise NotFound("Employee not found.")
        previous = employee.reporting_manager_id
        if previous is None:
            raise ApiError("This employee has no reporting manager.", errors={"employeeId": ["No manager to remove."]})
        remarks = data.remarks.strip()
        if not remarks:
            raise ApiError("Enter the reason for removing the manager.", errors={"remarks": ["A reason is required."]})
        self._close_open(employee.id, data.effective_from)
        employee.reporting_manager_id = None
        employee.updated_at = datetime.now(UTC).replace(tzinfo=None)
        employee.updated_by_user_id = actor.id
        self._db.add(
            ReportingAssignment(
                employee_id=employee.id,
                previous_manager_id=previous,
                manager_id=None,
                effective_from=data.effective_from,
                effective_to=data.effective_from,
                remarks=remarks,
                created_by_user_id=actor.id,
                is_active=True,
            )
        )
        self._db.commit()
        return ReportingAssignmentSaved(
            employee_id=employee.id,
            previous_manager_id=previous,
            manager_id=None,
            effective_from=data.effective_from,
            remarks=remarks,
        )

    def _close_open(self, employee_id: int, effective_from: date) -> None:
        """Ends the open assignment without changing who it recorded."""
        rows = self._db.scalars(
            select(ReportingAssignment)
            .where(
                ReportingAssignment.employee_id == employee_id,
                ReportingAssignment.effective_to.is_(None),
                ReportingAssignment.is_active == True,  # noqa: E712
            )
            .order_by(ReportingAssignment.id.desc())
        ).all()
        for row in rows:
            end = effective_from - timedelta(days=1)
            row.effective_to = end if end >= row.effective_from else row.effective_from

    def _check_manager(self, employee_id: int, manager_id: int) -> None:
        if manager_id == employee_id:
            raise ApiError(
                "An employee cannot report to themselves.",
                errors={"reportingManagerId": ["Choose someone else."]},
            )
        manager = self._db.get(Employee, manager_id)
        if manager is None or not manager.is_active:
            raise ApiError(
                "Choose an active manager.",
                errors={"reportingManagerId": ["That manager is not an active employee."]},
            )
        seen: set[int] = set()
        current: int | None = manager_id
        while current is not None and current not in seen:
            if current == employee_id:
                raise ApiError(
                    "That person already reports through this employee.",
                    errors={"reportingManagerId": ["Choose a manager outside this chain."]},
                )
            seen.add(current)
            current = self._org.manager_of(current)

    def _names(self, ids: set[int]) -> dict[int, str]:
        if not ids:
            return {}
        rows = self._db.scalars(select(Employee).where(Employee.id.in_(ids))).all()
        return {row.id: " ".join(part for part in (row.first_name, row.last_name) if part) for row in rows}

    def _authors(self, ids: set[int]) -> dict[int, str]:
        if not ids:
            return {}
        users = self._db.scalars(select(AppUser).where(AppUser.id.in_(ids))).all()
        names = self._names({user.employee_id for user in users if user.employee_id})
        return {
            user.id: names.get(user.employee_id) if user.employee_id and user.employee_id in names else user.username
            for user in users
        }


def _history_item(
    row: ReportingAssignment,
    names: dict[int, str],
    authors: dict[int, str],
    live_manager_id: int | None,
) -> ReportingHistoryItem:
    open_assignment = row.effective_to is None and row.manager_id is not None and row.manager_id == live_manager_id
    return ReportingHistoryItem(
        id=row.id,
        previous_manager_id=row.previous_manager_id,
        previous_manager_name=names.get(row.previous_manager_id) if row.previous_manager_id else None,
        manager_id=row.manager_id,
        manager_name=names.get(row.manager_id) if row.manager_id else None,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        remarks=row.remarks,
        changed_by=authors.get(row.created_by_user_id) if row.created_by_user_id else None,
        status="Active" if open_assignment else "Closed",
        created_at=row.created_at,
    )


def _employee(row: HierarchyListItem, manager_effective_from: date | None = None) -> ReportingEmployee:
    return ReportingEmployee(
        id=row.id,
        code=row.employee_code,
        name=row.full_name,
        designation=row.designation_name or "Not assigned",
        department=row.department_name or "Not assigned",
        location=row.branch_name or "Not assigned",
        manager_id=row.reporting_manager_id,
        level=row.grade or "Not assigned",
        status="Active" if row.is_active else "Inactive",
        manager_effective_from=manager_effective_from,
    )
