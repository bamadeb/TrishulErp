"""Leave calendar reads. Employees, requests and holidays stay in their existing tables."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, or_, select, true
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.db.models import AppUser, Branch, Department, Designation, Employee, Holiday, LeaveRequest, LeaveType
from trishul_api.modules.hr.leave.calendar_schemas import (
    LeaveCalendarBoard,
    LeaveCalendarEmployee,
    LeaveCalendarEntry,
    LeaveCalendarHoliday,
    LeaveCalendarQuery,
    LeaveCalendarSummary,
    LeaveCalendarTypeOption,
)
from trishul_api.modules.hr.leave.employee_ops import EmployeeLeaveRepository
from trishul_api.modules.hr.leave.employee_schemas import EmployeeLeaveQuery
from trishul_api.modules.hr.leave.holiday_ops import applies_to_branch

_HUNDRED = Decimal(100)
_PERCENT = Decimal("0.01")


class LeaveCalendarRepository:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._register = EmployeeLeaveRepository(db)

    def summary(self, actor: CurrentUser, query: LeaveCalendarQuery) -> LeaveCalendarSummary:
        return self.board(actor, query).summary

    def board(self, actor: CurrentUser, query: LeaveCalendarQuery) -> LeaveCalendarBoard:
        start, end = _month(query.year, query.month)
        people = self._register._employees(actor, _employee_query(query, start))
        by_id = {
            employee.id: (employee, department, designation, location)
            for employee, department, designation, location in people
        }
        rows = self._requests(list(by_id), query, start, end)
        today = date.today()
        names = self._approvers({request.approver_user_id for request, *_rest in rows})
        entries = [
            self._entry(request, code, leave_name, by_id[request.employee_id], names)
            for request, code, leave_name in rows
            if request.employee_id in by_id
        ]
        summary = _summary(len(by_id), rows, start, end, today)
        return LeaveCalendarBoard(
            summary=summary,
            entries=entries,
            holidays=self._holidays(actor, query, start, end),
            departments=self._register._options(actor, Department, Employee.department_id),
            designations=self._register._options(actor, Designation, Employee.designation_id),
            locations=self._register._options(actor, Branch, Employee.branch_id),
            leave_types=self._types(),
        )

    def _requests(
        self, employee_ids: list[int], query: LeaveCalendarQuery, start: date, end: date
    ) -> list[tuple[LeaveRequest, str, str]]:
        if not employee_ids:
            return []
        today = date.today()
        soon = today + timedelta(days=30)
        statement = (
            select(LeaveRequest, LeaveType.code, LeaveType.name)
            .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
            .where(
                LeaveRequest.employee_id.in_(employee_ids),
                LeaveRequest.is_active == True,  # noqa: E712
                LeaveRequest.status != "Cancelled",
                or_(
                    (LeaveRequest.from_date <= end) & (LeaveRequest.to_date >= start),
                    (LeaveRequest.status == "Approved")
                    & (LeaveRequest.from_date <= today)
                    & (LeaveRequest.to_date >= today),
                    (LeaveRequest.status == "Approved")
                    & (LeaveRequest.from_date > today)
                    & (LeaveRequest.from_date <= soon),
                ),
            )
            .order_by(LeaveRequest.from_date, LeaveRequest.id)
        )
        if query.leave_type_id is not None:
            statement = statement.where(LeaveRequest.leave_type_id == query.leave_type_id)
        return list(self._db.execute(statement).all())

    def _holidays(
        self, actor: CurrentUser, query: LeaveCalendarQuery, start: date, end: date
    ) -> list[LeaveCalendarHoliday]:
        statement = select(Holiday).where(
            Holiday.is_active == True,  # noqa: E712
            Holiday.holiday_type != "Optional",
            Holiday.holiday_date >= start,
            Holiday.holiday_date <= end,
            self._holiday_scope(query.branch_id, None if query.branch_id is not None else actor.branch_ids),
        )
        rows = self._db.execute(statement.order_by(Holiday.holiday_date, Holiday.name, Holiday.id)).scalars().all()
        seen: set[tuple[date, str]] = set()
        holidays: list[LeaveCalendarHoliday] = []
        for row in rows:
            key = (row.holiday_date, row.name)
            if key in seen:
                continue
            seen.add(key)
            holidays.append(LeaveCalendarHoliday(holiday_date=row.holiday_date, name=row.name))
        return holidays

    def _holiday_scope(self, branch_id: int | None, branch_ids: frozenset[int] | None):
        state_col = Holiday.__table__.c.state_id
        if branch_id is not None:
            state_id = self._db.scalar(select(Branch.state_id).where(Branch.id == branch_id))
            return applies_to_branch(branch_id, state_id)
        if branch_ids is not None:
            ids = list(branch_ids) or [0]
            states = select(Branch.state_id).where(Branch.id.in_(ids))
            return or_(
                Holiday.branch_id.in_(ids),
                and_(Holiday.branch_id.is_(None), or_(state_col.is_(None), state_col.in_(states))),
            )
        return true()

    def _types(self) -> list[LeaveCalendarTypeOption]:
        rows = self._db.execute(
            select(LeaveType.id, LeaveType.code, LeaveType.name)
            .where(LeaveType.is_active == True)  # noqa: E712
            .order_by(LeaveType.code)
        ).all()
        return [LeaveCalendarTypeOption(id=row[0], code=row[1], name=row[2]) for row in rows]

    def _approvers(self, user_ids: set[int | None]) -> dict[int, str]:
        ids = {user_id for user_id in user_ids if user_id is not None}
        if not ids:
            return {}
        rows = self._db.execute(
            select(AppUser.id, Employee.first_name, Employee.last_name, AppUser.username)
            .select_from(AppUser)
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .where(AppUser.id.in_(ids))
        ).all()
        return {row[0]: _person(row[1], row[2]) or row[3] for row in rows}

    def _entry(
        self,
        request: LeaveRequest,
        code: str,
        leave_name: str,
        person: tuple[Employee, str | None, str | None, str | None],
        names: dict[int, str],
    ) -> LeaveCalendarEntry:
        employee, department, designation, location = person
        approved_by = None
        if request.status in {"Approved", "Rejected"} and request.approver_user_id is not None:
            approved_by = names.get(request.approver_user_id)
        return LeaveCalendarEntry(
            request_id=request.id,
            display_id=f"LV-{request.id:04d}",
            employee=LeaveCalendarEmployee(
                employee_id=employee.id,
                code=employee.employee_code,
                name=_person(employee.first_name, employee.last_name),
                department=department,
                designation=designation,
                location=location,
                status=employee.status,
            ),
            leave_code=code,
            leave_type=leave_name,
            from_date=request.from_date,
            to_date=request.to_date,
            days=request.days,
            status=request.status,
            reason=request.reason,
            approved_by=approved_by,
        )


def _employee_query(query: LeaveCalendarQuery, start: date) -> EmployeeLeaveQuery:
    year = start.year if start.month >= 4 else start.year - 1
    return EmployeeLeaveQuery(
        financial_year=year,
        department_id=query.department_id,
        designation_id=query.designation_id,
        branch_id=query.branch_id,
        search=query.search,
    )


def _summary(
    total: int, rows: list[tuple[LeaveRequest, str, str]], start: date, end: date, today: date
) -> LeaveCalendarSummary:
    def overlaps(request: LeaveRequest) -> bool:
        return request.from_date <= end and request.to_date >= start

    on_leave = {
        request.employee_id
        for request, *_rest in rows
        if request.status == "Approved" and request.from_date <= today <= request.to_date
    }
    upcoming_until = today + timedelta(days=30)
    percent = Decimal(0) if total == 0 else (Decimal(len(on_leave)) * _HUNDRED / Decimal(total)).quantize(_PERCENT)
    return LeaveCalendarSummary(
        total_employees=total,
        on_leave_today=len(on_leave),
        on_leave_percent=percent,
        pending_approval=sum(1 for request, *_rest in rows if request.status == "Pending" and overlaps(request)),
        approved_mtd=sum(1 for request, *_rest in rows if request.status == "Approved" and overlaps(request)),
        rejected_mtd=sum(1 for request, *_rest in rows if request.status == "Rejected" and overlaps(request)),
        upcoming_leaves=sum(
            1 for request, *_rest in rows
            if request.status == "Approved" and today < request.from_date <= upcoming_until
        ),
    )


def _month(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        return start, date(year, 12, 31)
    return start, date(year, month + 1, 1) - timedelta(days=1)


def _person(first: str | None, last: str | None) -> str:
    return " ".join(part for part in (first, last) if part).strip()
