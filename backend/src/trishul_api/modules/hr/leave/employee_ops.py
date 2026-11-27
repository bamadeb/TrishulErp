"""Employee leave register. Employees come from core.employee and balances from hr.leave_balance."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import NotFound
from trishul_api.db.models import (
    AppUser,
    Branch,
    Department,
    Designation,
    Employee,
    LeaveBalanceTransaction,
    LeaveRequest,
    LeaveType,
)
from trishul_api.modules.hr.leave.balance_ops import _balances, _kind_totals
from trishul_api.modules.hr.leave.employee_schemas import (
    EmployeeLeaveBalanceView,
    EmployeeLeaveDetail,
    EmployeeLeaveHistoryItem,
    EmployeeLeaveOption,
    EmployeeLeavePage,
    EmployeeLeaveQuery,
    EmployeeLeaveRow,
    EmployeeLeaveSpan,
    EmployeeLeaveStats,
    EmployeeUpcomingLeave,
)
from trishul_api.modules.hr.leave.mine_repository import _year_bounds

_ZERO = Decimal("0.0")
_CODES = ("CL", "AL", "EL", "CO")
_SORTS = {"code", "name", "department", "designation", "cl", "el", "sl", "co", "taken", "upcoming"}


@dataclass
class _Person:
    employee: Employee
    department: str | None
    designation: str | None
    location: str | None
    cl: Decimal
    el: Decimal
    sl: Decimal
    co: Decimal
    taken: Decimal
    upcoming: LeaveRequest | None
    upcoming_code: str | None
    last_leave: LeaveRequest | None
    last_code: str | None
    on_leave_today: bool
    financial_year: int
    requests: list[tuple[LeaveRequest, str, str]]


class EmployeeLeaveRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def stats(self, actor: CurrentUser, query: EmployeeLeaveQuery) -> EmployeeLeaveStats:
        people = self._people(actor, query)
        taken = sum((person.taken for person in people), _ZERO)
        return EmployeeLeaveStats(
            employees=len(people),
            on_leave=sum(1 for person in people if person.on_leave_today),
            upcoming=sum(1 for person in people if person.upcoming is not None),
            taken=taken,
            departments=self._options(actor, Department, Employee.department_id),
            designations=self._options(actor, Designation, Employee.designation_id),
            locations=self._options(actor, Branch, Employee.branch_id),
        )

    def page(self, actor: CurrentUser, query: EmployeeLeaveQuery) -> EmployeeLeavePage:
        ordered = self._ordered(self._people(actor, query), query.sort)
        start = (query.page - 1) * query.page_size
        rows = ordered[start : start + query.page_size]
        return EmployeeLeavePage(
            items=[self._row(person) for person in rows],
            total=len(ordered),
            page=query.page,
            page_size=query.page_size,
        )

    def export(self, actor: CurrentUser, query: EmployeeLeaveQuery) -> EmployeeLeavePage:
        ordered = self._ordered(self._people(actor, query), query.sort)
        return EmployeeLeavePage(
            items=[self._row(person) for person in ordered[:500]],
            total=len(ordered),
            page=1,
            page_size=max(len(ordered), 1),
        )

    def upcoming(self, actor: CurrentUser, query: EmployeeLeaveQuery) -> list[EmployeeUpcomingLeave]:
        found = [person for person in self._ordered(self._people(actor, query), "upcoming") if person.upcoming]
        return [
            EmployeeUpcomingLeave(
                employee_id=person.employee.id,
                code=person.employee.employee_code,
                name=_name(person.employee),
                **self._span(person.upcoming, person.upcoming_code or "").model_dump(),
            )
            for person in found
            if person.upcoming is not None
        ]

    def detail(self, actor: CurrentUser, employee_id: int, financial_year: int) -> EmployeeLeaveDetail:
        person = self._one(actor, employee_id, financial_year)
        return EmployeeLeaveDetail(
            **self._row(person).model_dump(),
            last_leave=None if person.last_leave is None else self._span(person.last_leave, person.last_code or ""),
            balances=self._balance_views(person),
            history=self._history(person),
        )

    def history(self, actor: CurrentUser, employee_id: int, financial_year: int) -> list[EmployeeLeaveHistoryItem]:
        return self._history(self._one(actor, employee_id, financial_year))

    def balance(self, actor: CurrentUser, employee_id: int, financial_year: int) -> dict[str, EmployeeLeaveBalanceView]:
        return self._balance_views(self._one(actor, employee_id, financial_year))

    def _one(self, actor: CurrentUser, employee_id: int, financial_year: int) -> _Person:
        query = EmployeeLeaveQuery(financial_year=financial_year, page=1, page_size=1)
        found = next((person for person in self._people(actor, query) if person.employee.id == employee_id), None)
        if found is None:
            raise NotFound("Employee")
        return found

    def _people(self, actor: CurrentUser, query: EmployeeLeaveQuery) -> list[_Person]:
        employees = self._employees(actor, query)
        if not employees:
            return []
        start, end = _year_bounds(query.financial_year)
        balances = _balances(self._db, [employee.id for employee, *_rest in employees], query.financial_year)
        requests = self._requests([employee.id for employee, *_rest in employees], start, end)
        today = date.today()
        built: list[_Person] = []
        for employee, department, designation, location in employees:
            own = requests.get(employee.id, [])
            buckets = balances.get(employee.id, {})
            built.append(_Person(
                employee=employee,
                department=department,
                designation=designation,
                location=location,
                cl=_closing(buckets.get("CL")),
                el=_closing(buckets.get("AL") or buckets.get("EL")),
                sl=_ZERO,
                co=_closing(buckets.get("CO")),
                taken=_taken(own, start, end, today),
                upcoming=_next_leave(own, start, end, today),
                upcoming_code=_next_code(own, start, end, today),
                last_leave=_last_leave(own, start, end, today),
                last_code=_last_code(own, start, end, today),
                on_leave_today=_away(own, today),
                financial_year=query.financial_year,
                requests=own,
            ))
        return built

    def _employees(
        self, actor: CurrentUser, query: EmployeeLeaveQuery
    ) -> list[tuple[Employee, str | None, str | None, str | None]]:
        statement = (
            select(Employee, Department.name, Designation.name, Branch.name)
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(Designation, Designation.id == Employee.designation_id)
            .outerjoin(Branch, Branch.id == Employee.branch_id)
            .where(Employee.id.in_(self._scope(actor)))
        )
        if query.department_id is not None:
            statement = statement.where(Employee.department_id == query.department_id)
        if query.designation_id is not None:
            statement = statement.where(Employee.designation_id == query.designation_id)
        if query.branch_id is not None:
            statement = statement.where(Employee.branch_id == query.branch_id)
        if query.search and query.search.strip():
            term = query.search.strip()
            statement = statement.where(or_(
                Employee.employee_code.contains(term, autoescape=True),
                Employee.first_name.contains(term, autoescape=True),
                Employee.last_name.contains(term, autoescape=True),
            ))
        return list(self._db.execute(statement).all())

    def _scope(self, actor: CurrentUser):
        statement = select(Employee.id).where(Employee.status == "Active", Employee.is_active == True)  # noqa: E712
        if actor.branch_ids is not None:
            statement = statement.where(Employee.branch_id.in_(actor.branch_ids or [0]))
        if not actor.can("hr.leave.manage", "hr.leave.approve"):
            person = actor.employee_id
            statement = statement.where(or_(Employee.id == person, Employee.reporting_manager_id == person))
        return statement

    def _requests(
        self, employee_ids: list[int], start: date, end: date
    ) -> dict[int, list[tuple[LeaveRequest, str, str]]]:
        rows = self._db.execute(
            select(LeaveRequest, LeaveType.code, LeaveType.name)
            .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
            .where(
                LeaveRequest.employee_id.in_(employee_ids),
                LeaveRequest.is_active == True,  # noqa: E712
                LeaveRequest.from_date <= end,
                LeaveRequest.to_date >= start,
            )
            .order_by(LeaveRequest.from_date, LeaveRequest.id)
        ).all()
        found: dict[int, list[tuple[LeaveRequest, str, str]]] = {}
        for request, code, name in rows:
            found.setdefault(request.employee_id, []).append((request, code, name))
        return found

    def _options(
        self,
        actor: CurrentUser,
        model: type[Department] | type[Designation] | type[Branch],
        column,
    ) -> list[EmployeeLeaveOption]:
        rows = self._db.execute(
            select(model.id, model.name)
            .where(model.id.in_(select(column).where(Employee.id.in_(self._scope(actor)), column.is_not(None))))
            .order_by(model.name)
        ).all()
        return [EmployeeLeaveOption(id=row[0], name=row[1]) for row in rows]

    def _ordered(self, people: list[_Person], sort: str | None) -> list[_Person]:
        raw = sort or "code"
        descending = raw.startswith("-")
        key = raw[1:] if descending else raw
        if key not in _SORTS:
            key = "code"
        return sorted(people, key=lambda person: _sort_key(person, key), reverse=descending)

    def _row(self, person: _Person) -> EmployeeLeaveRow:
        upcoming = None if person.upcoming is None else self._span(person.upcoming, person.upcoming_code or "")
        return EmployeeLeaveRow(
            employee_id=person.employee.id,
            code=person.employee.employee_code,
            name=_name(person.employee),
            department=person.department,
            designation=person.designation,
            location=person.location,
            status=person.employee.status,
            date_of_joining=person.employee.date_of_joining,
            cl=person.cl,
            el=person.el,
            sl=person.sl,
            co=person.co,
            taken=person.taken,
            upcoming=upcoming,
            on_leave_today=person.on_leave_today,
        )

    def _span(self, request: LeaveRequest, code: str) -> EmployeeLeaveSpan:
        return EmployeeLeaveSpan(
            request_id=request.id,
            display_id=f"LV-{request.id:04d}",
            leave_code=code,
            from_date=request.from_date,
            to_date=request.to_date,
            days=request.days,
        )

    def _history(self, person: _Person) -> list[EmployeeLeaveHistoryItem]:
        names = self._approvers({request.approver_user_id for request, *_rest in person.requests})
        ordered = sorted(person.requests, key=lambda item: (item[0].from_date, item[0].id), reverse=True)
        return [
            EmployeeLeaveHistoryItem(
                request_id=request.id,
                display_id=f"LV-{request.id:04d}",
                leave_code=code,
                leave_type=f"{name} ({code})",
                from_date=request.from_date,
                to_date=request.to_date,
                days=request.days,
                status=request.status,
                approved_by=_approver(names, request),
            )
            for request, code, name in ordered
        ]

    def _balance_views(self, person: _Person) -> dict[str, EmployeeLeaveBalanceView]:
        from trishul_api.modules.hr.leave.comp_off_ops import expire_due, next_expiry, sync_balance

        expire_due(self._db, employee_id=person.employee.id, as_of=date.today())
        sync_balance(self._db, person.employee.id, None)
        self._db.commit()
        expiry = next_expiry(self._db, person.employee.id, date.today())
        stored = _balances(self._db, [person.employee.id], _financial_year_of(person)).get(person.employee.id, {})
        transactions = self._db.execute(
            select(LeaveBalanceTransaction, LeaveType.code)
            .join(LeaveType, LeaveType.id == LeaveBalanceTransaction.leave_type_id)
            .where(
                LeaveBalanceTransaction.employee_id == person.employee.id,
                LeaveBalanceTransaction.leave_year == _financial_year_of(person),
                LeaveBalanceTransaction.is_active == True,  # noqa: E712
            )
        ).all()
        views: dict[str, EmployeeLeaveBalanceView] = {}
        for code in _CODES:
            balance = stored.get(code)
            kinds = _kind_totals(transactions, code)
            views[code] = EmployeeLeaveBalanceView(
                opening=_ZERO if balance is None else balance.opening,
                credited=_ZERO if balance is None else balance.accrued,
                consumed=_ZERO if balance is None else balance.availed,
                adjustments=kinds.get("Adjustment", _ZERO),
                expired=kinds.get("Expiry", _ZERO),
                closing=_ZERO if balance is None else balance.closing,
                next_expiry=expiry if code == "CO" else None,
            )
        return views

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


def _financial_year_of(person: _Person) -> int:
    return person.financial_year


def _approver(names: dict[int, str], request: LeaveRequest) -> str | None:
    if request.status not in {"Approved", "Rejected"} or request.approver_user_id is None:
        return None
    return names.get(request.approver_user_id)


def _closing(balance) -> Decimal:
    return _ZERO if balance is None else balance.closing


def _taken(rows: list[tuple[LeaveRequest, str, str]], start: date, end: date, today: date) -> Decimal:
    return sum(
        (request.days for request, *_rest in rows if _counts_as_taken(request, start, end, today)),
        _ZERO,
    )


def _counts_as_taken(request: LeaveRequest, start: date, end: date, today: date) -> bool:
    return request.status == "Approved" and start <= request.from_date <= end and request.from_date <= today


def _next_leave(rows: list[tuple[LeaveRequest, str, str]], start: date, end: date, today: date) -> LeaveRequest | None:
    found = [
        request for request, *_rest in rows
        if request.status == "Approved" and today < request.from_date <= end and request.from_date >= start
    ]
    return min(found, key=lambda request: (request.from_date, request.id), default=None)


def _next_code(rows: list[tuple[LeaveRequest, str, str]], start: date, end: date, today: date) -> str | None:
    request = _next_leave(rows, start, end, today)
    if request is None:
        return None
    return next(code for item, code, _name in rows if item.id == request.id)


def _last_leave(rows: list[tuple[LeaveRequest, str, str]], start: date, end: date, today: date) -> LeaveRequest | None:
    found = [
        request for request, *_rest in rows
        if request.status == "Approved" and start <= request.from_date <= end and request.to_date < today
    ]
    return max(found, key=lambda request: (request.to_date, request.id), default=None)


def _last_code(rows: list[tuple[LeaveRequest, str, str]], start: date, end: date, today: date) -> str | None:
    request = _last_leave(rows, start, end, today)
    if request is None:
        return None
    return next(code for item, code, _name in rows if item.id == request.id)


def _away(rows: list[tuple[LeaveRequest, str, str]], today: date) -> bool:
    return any(
        request.status == "Approved" and request.from_date <= today <= request.to_date
        for request, *_rest in rows
    )


def _sort_key(person: _Person, key: str):
    if key == "upcoming":
        return person.upcoming.from_date if person.upcoming is not None else date.max
    if key in {"cl", "el", "sl", "co", "taken"}:
        return getattr(person, key)
    if key == "name":
        return _name(person.employee).casefold()
    if key == "department":
        return (person.department or "").casefold()
    if key == "designation":
        return (person.designation or "").casefold()
    return person.employee.employee_code


def _name(employee: Employee) -> str:
    return _person(employee.first_name, employee.last_name)


def _person(first: str | None, last: str | None) -> str:
    return " ".join(part for part in (first, last) if part).strip()
