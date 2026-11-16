"""Leave dashboard aggregates from the existing employee, request, balance and type tables."""

import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.db.models import Department, Employee, LeaveBalance, LeaveRequest, LeaveType
from trishul_api.modules.hr.leave.dashboard_schemas import (
    BalanceRow,
    FilterOption,
    LeaveDashboard,
    LeaveDashboardQuery,
    MineBalance,
    MinePanel,
    MonthPoint,
    Overview,
    RequestPage,
    RequestRow,
)

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_SORTS = {
    "employee": Employee.first_name,
    "fromDate": LeaveRequest.from_date,
    "days": LeaveRequest.days,
    "status": LeaveRequest.status,
}


class LeaveDashboardRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def build(self, actor: CurrentUser, query: LeaveDashboardQuery) -> LeaveDashboard:
        year, month = _period(query)
        start, end = _month_bounds(year, month)
        today = date.today()
        reference = today if start <= today <= end else end if end < today else start
        wide = actor.can("hr.leave.manage", "hr.leave.approve")
        scoped = self._employees(actor)
        on_leave_people = self._people_count(scoped, "Approved", reference, reference)
        pending_people = self._pending_people(scoped, start, end, reference)
        active = self._count(scoped)
        return LeaveDashboard(
            year=year,
            month=month,
            as_of=today,
            organisation_wide=wide,
            active_employees=active,
            on_leave_today=self._people_count(scoped, "Approved", today, today),
            pending_requests=self._request_count(scoped, "Pending", start, end),
            approved_requests=self._request_count(scoped, "Approved", start, end),
            rejected_requests=self._request_count(scoped, "Rejected", start, end),
            upcoming_leaves=self._upcoming(scoped, start, end, today),
            overview=Overview(
                working=max(active - on_leave_people - pending_people, 0),
                on_leave=on_leave_people,
                pending=pending_people,
            ),
            trend=self._trend(scoped, year, month),
            balances=self._balances(scoped, year),
            requests=self._requests(scoped, query, start, end, today),
            mine=self._mine(actor, year, start, end),
            department_options=self._departments(scoped),
            leave_type_options=self._types(),
        )

    def _employees(self, actor: CurrentUser) -> Select[tuple[int]]:
        query = select(Employee.id).where(Employee.status == "Active", Employee.is_active == True)  # noqa: E712
        if not actor.can("hr.leave.manage", "hr.leave.approve"):
            person = actor.employee_id
            query = query.where(or_(Employee.id == person, Employee.reporting_manager_id == person))
        return query

    def _count(self, employees: Select[tuple[int]]) -> int:
        return int(self._db.scalar(select(func.count()).select_from(employees.subquery())) or 0)

    def _overlap(self, start: date, end: date) -> list[object]:
        return [
            LeaveRequest.from_date <= end,
            LeaveRequest.to_date >= start,
            LeaveRequest.is_active == True,  # noqa: E712
        ]

    def _request_count(self, employees: Select[tuple[int]], status: str, start: date, end: date) -> int:
        query = select(func.count(LeaveRequest.id)).where(
            LeaveRequest.status == status,
            LeaveRequest.employee_id.in_(employees),
            *self._overlap(start, end),
        )
        return int(self._db.scalar(query) or 0)

    def _people_count(self, employees: Select[tuple[int]], status: str, start: date, end: date) -> int:
        query = select(func.count(func.distinct(LeaveRequest.employee_id))).where(
            LeaveRequest.status == status,
            LeaveRequest.employee_id.in_(employees),
            *self._overlap(start, end),
        )
        return int(self._db.scalar(query) or 0)

    def _pending_people(self, employees: Select[tuple[int]], start: date, end: date, reference: date) -> int:
        """Pending employees who are not already on approved leave on the reference day."""
        on_leave = select(LeaveRequest.employee_id).where(
            LeaveRequest.status == "Approved",
            LeaveRequest.employee_id.in_(employees),
            *self._overlap(reference, reference),
        )
        query = select(func.count(func.distinct(LeaveRequest.employee_id))).where(
            LeaveRequest.status == "Pending",
            LeaveRequest.employee_id.in_(employees),
            LeaveRequest.employee_id.notin_(on_leave),
            *self._overlap(start, end),
        )
        return int(self._db.scalar(query) or 0)

    def _upcoming(self, employees: Select[tuple[int]], start: date, end: date, today: date) -> int:
        query = select(func.count(LeaveRequest.id)).where(
            LeaveRequest.status == "Approved",
            LeaveRequest.employee_id.in_(employees),
            LeaveRequest.is_active == True,  # noqa: E712
            LeaveRequest.from_date > today,
            LeaveRequest.from_date >= start,
            LeaveRequest.from_date <= end,
        )
        return int(self._db.scalar(query) or 0)

    def _approved_days(self, employees: Select[tuple[int]], start: date, end: date) -> Decimal:
        total = self._db.scalar(
            select(func.coalesce(func.sum(LeaveRequest.days), 0)).where(
                LeaveRequest.status == "Approved",
                LeaveRequest.employee_id.in_(employees),
                LeaveRequest.from_date >= start,
                LeaveRequest.from_date <= end,
                LeaveRequest.is_active == True,  # noqa: E712
            )
        )
        return Decimal(total or 0)

    def _trend(self, employees: Select[tuple[int]], year: int, month: int) -> list[MonthPoint]:
        points: list[MonthPoint] = []
        for offset in range(-5, 1):
            point_year, point_month = _shift(year, month, offset)
            start, end = _month_bounds(point_year, point_month)
            points.append(
                MonthPoint(
                    month=f"{_MONTHS[point_month - 1]} {str(point_year)[2:]}",
                    days=self._approved_days(employees, start, end),
                )
            )
        return points

    def _latest_balances(self, employees: Select[tuple[int]], year: int):
        return (
            select(func.max(LeaveBalance.id).label("id"))
            .where(
                LeaveBalance.leave_year == year,
                LeaveBalance.is_active == True,  # noqa: E712
                LeaveBalance.employee_id.in_(employees),
            )
            .group_by(LeaveBalance.employee_id, LeaveBalance.leave_type_id)
            .subquery()
        )

    def _balances(self, employees: Select[tuple[int]], year: int) -> list[BalanceRow]:
        latest = self._latest_balances(employees, year)
        entitlement = func.coalesce(func.sum(LeaveBalance.opening + LeaveBalance.accrued), 0)
        used = func.coalesce(func.sum(LeaveBalance.availed), 0)
        closing = func.coalesce(func.sum(LeaveBalance.closing), 0)
        rows = self._db.execute(
            select(LeaveType.code, LeaveType.name, entitlement, used, closing)
            .select_from(LeaveType)
            .outerjoin(
                LeaveBalance,
                (LeaveBalance.leave_type_id == LeaveType.id) & LeaveBalance.id.in_(select(latest.c.id)),
            )
            .where(LeaveType.is_active == True)  # noqa: E712
            .group_by(LeaveType.code, LeaveType.name)
            .order_by(LeaveType.name)
        ).all()
        return [
            BalanceRow(
                code=code,
                name=name,
                entitlement=Decimal(entitled or 0),
                used=Decimal(taken or 0),
                closing=Decimal(left or 0),
            )
            for code, name, entitled, taken, left in rows
        ]

    def _requests(
        self, employees: Select[tuple[int]], query: LeaveDashboardQuery, start: date, end: date, today: date
    ) -> RequestPage:
        filters = self._request_filters(employees, query, start, end, today)
        total = int(
            self._db.scalar(
                select(func.count(LeaveRequest.id)).select_from(LeaveRequest).join(Employee).where(*filters)
            )
            or 0
        )
        sort_name = (query.sort or "-fromDate").removeprefix("-")
        column = _SORTS.get(sort_name, LeaveRequest.from_date)
        descending = query.sort is None or query.sort.startswith("-")
        ordered = column.desc() if descending else column.asc()
        rows = self._db.execute(
            self._request_select()
            .where(*filters)
            .order_by(ordered, LeaveRequest.id)
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
        return RequestPage(
            items=[_request_row(row) for row in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def _request_filters(
        self, employees: Select[tuple[int]], query: LeaveDashboardQuery, start: date, end: date, today: date
    ) -> list[object]:
        filters: list[object] = [
            LeaveRequest.employee_id.in_(employees),
            *self._overlap(start, end),
        ]
        if query.status is not None:
            filters.append(LeaveRequest.status == query.status)
        if query.leave_type_id is not None:
            filters.append(LeaveRequest.leave_type_id == query.leave_type_id)
        if query.department_id is not None:
            filters.append(Employee.department_id == query.department_id)
        if query.upcoming:
            filters.append(LeaveRequest.from_date > today)
        if query.search and query.search.strip():
            term = query.search.strip()
            filters.append(
                or_(
                    Employee.employee_code.contains(term),
                    Employee.first_name.contains(term),
                    func.coalesce(Employee.last_name, "").contains(term),
                )
            )
        return filters

    def _request_select(self):
        return (
            select(
                LeaveRequest.id,
                Employee.employee_code,
                Employee.first_name,
                Employee.last_name,
                Department.name,
                LeaveType.name,
                LeaveRequest.from_date,
                LeaveRequest.to_date,
                LeaveRequest.days,
                LeaveRequest.reason,
                LeaveRequest.status,
            )
            .join(Employee, Employee.id == LeaveRequest.employee_id)
            .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
            .outerjoin(Department, Department.id == Employee.department_id)
        )

    def _mine(self, actor: CurrentUser, year: int, start: date, end: date) -> MinePanel:
        person = actor.employee_id
        if person is None:
            return MinePanel(balances=[], requests=[], history=[])
        latest = self._latest_balances(select(Employee.id).where(Employee.id == person), year)
        rows = self._db.execute(
            select(LeaveType.code, LeaveType.name, func.coalesce(LeaveBalance.closing, 0))
            .select_from(LeaveType)
            .outerjoin(
                LeaveBalance,
                (LeaveBalance.leave_type_id == LeaveType.id) & LeaveBalance.id.in_(select(latest.c.id)),
            )
            .where(LeaveType.is_active == True)  # noqa: E712
            .order_by(LeaveType.name)
        ).all()
        own = select(Employee.id).where(Employee.id == person)
        pending = self._db.execute(
            self._request_select()
            .where(LeaveRequest.employee_id.in_(own), LeaveRequest.status == "Pending", *self._overlap(start, end))
            .order_by(LeaveRequest.from_date, LeaveRequest.id)
            .limit(8)
        ).all()
        history = self._db.execute(
            self._request_select()
            .where(
                LeaveRequest.employee_id.in_(own),
                LeaveRequest.status != "Pending",
                *self._overlap(start, end),
            )
            .order_by(LeaveRequest.from_date.desc(), LeaveRequest.id)
            .limit(8)
        ).all()
        return MinePanel(
            balances=[MineBalance(code=code, name=name, closing=Decimal(closing or 0)) for code, name, closing in rows],
            requests=[_request_row(row) for row in pending],
            history=[_request_row(row) for row in history],
        )

    def _departments(self, employees: Select[tuple[int]]) -> list[FilterOption]:
        rows = self._db.execute(
            select(Department.id, Department.name)
            .join(Employee, Employee.department_id == Department.id)
            .where(Employee.id.in_(employees), Department.is_active == True)  # noqa: E712
            .distinct()
            .order_by(Department.name)
        ).all()
        return [FilterOption(id=row[0], name=row[1]) for row in rows]

    def _types(self) -> list[FilterOption]:
        rows = self._db.execute(
            select(LeaveType.id, LeaveType.name)
            .where(LeaveType.is_active == True)  # noqa: E712
            .order_by(LeaveType.name)
        ).all()
        return [FilterOption(id=row[0], name=row[1]) for row in rows]


def _period(query: LeaveDashboardQuery) -> tuple[int, int]:
    today = date.today()
    return query.year or today.year, query.month or today.month


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _shift(year: int, month: int, offset: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + offset
    return index // 12, index % 12 + 1


def _person(first: str, last: str | None) -> str:
    return " ".join(part for part in (first, last) if part)


def _request_row(row: object) -> RequestRow:
    values = tuple(row)  # type: ignore[arg-type]
    return RequestRow(
        request_id=values[0],
        employee_code=values[1],
        employee_name=_person(values[2], values[3]),
        department=values[4],
        leave_type=values[5],
        from_date=values[6],
        to_date=values[7],
        days=values[8],
        reason=values[9],
        status=values[10],
    )
