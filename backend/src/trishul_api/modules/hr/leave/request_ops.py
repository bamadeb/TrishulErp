"""Leave request queue. Employees come from core.employee; applications come from hr.leave_request."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, aliased

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import Forbidden, NotFound
from trishul_api.db.models import (
    AppUser,
    Branch,
    Department,
    Designation,
    Employee,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    StatusHistory,
)
from trishul_api.modules.hr.leave.mine_repository import LeaveMineRepository, LeaveRuleError, _financial_year
from trishul_api.modules.hr.leave.mine_schemas import MineApply
from trishul_api.modules.hr.leave.request_schemas import (
    LeaveHistoryEvent,
    LeaveOption,
    LeaveRequestDetail,
    LeaveRequestEmployee,
    LeaveRequestFilter,
    LeaveRequestPage,
    LeaveRequestQuery,
    LeaveRequestRow,
    LeaveRequestSummary,
)

_ZERO = Decimal("0")
_ENTITY = "hr.leave_request"


class LeaveRequestRepository:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._mine = LeaveMineRepository(db)

    def summary(self, actor: CurrentUser, query: LeaveRequestFilter) -> LeaveRequestSummary:
        counts = dict(
            self._db.execute(
                select(LeaveRequest.status, func.count(LeaveRequest.id))
                .select_from(LeaveRequest)
                .join(Employee, Employee.id == LeaveRequest.employee_id)
                .where(*self._clauses(actor, query))
                .group_by(LeaveRequest.status)
            ).all()
        )
        pending = int(counts.get("Pending", 0))
        approved = int(counts.get("Approved", 0))
        rejected = int(counts.get("Rejected", 0))
        return LeaveRequestSummary(
            pending=pending,
            approved=approved,
            rejected=rejected,
            total=pending + approved + rejected,
            departments=self._departments(actor),
            leave_types=self._types(),
        )

    def page(self, actor: CurrentUser, query: LeaveRequestQuery) -> LeaveRequestPage:
        clauses = self._clauses(actor, query)
        if query.status is not None:
            clauses.append(LeaveRequest.status == query.status)
        total = int(
            self._db.scalar(
                select(func.count(LeaveRequest.id))
                .select_from(LeaveRequest)
                .join(Employee, Employee.id == LeaveRequest.employee_id)
                .where(*clauses)
            )
            or 0
        )
        stmt = self._ordered(self._joined().where(*clauses), query.sort)
        start = (query.page - 1) * query.page_size
        found = self._db.execute(stmt.offset(start).limit(query.page_size)).all()
        balances = self._balances([row[0] for row in found])
        return LeaveRequestPage(
            items=[self._item(actor, *row, balances) for row in found],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def detail(self, actor: CurrentUser, request_id: int) -> LeaveRequestDetail:
        found = self._one(actor, request_id)
        row = found[0]
        history = self._history(row)
        return LeaveRequestDetail(
            **self._item(actor, *found, self._balances([row])).model_dump(),
            approver_user_id=row.approver_user_id,
            acted_at=row.acted_at,
            history=history,
            comments=[event.remarks for event in history if event.action == "Comment"],
        )

    def history(self, actor: CurrentUser, request_id: int) -> list[LeaveHistoryEvent]:
        return self._history(self._one(actor, request_id)[0])

    def approve(self, actor: CurrentUser, request_id: int) -> LeaveRequestDetail:
        row, employee = self._pending(actor, request_id, "approved")
        days = self._checked_days(employee, row)
        leave_type = self._db.get(LeaveType, row.leave_type_id)
        if leave_type is not None and leave_type.is_paid:
            self._deduct(employee.id, row.leave_type_id, row.from_date, days, actor.id)
        row.days = days
        self._finish(row, "Approved", "Approved.", actor)
        self._db.commit()
        return self.detail(actor, request_id)

    def reject(self, actor: CurrentUser, request_id: int, remarks: str) -> LeaveRequestDetail:
        row, _employee = self._pending(actor, request_id, "rejected")
        self._finish(row, "Rejected", remarks.strip(), actor)
        self._db.commit()
        return self.detail(actor, request_id)

    def comment(self, actor: CurrentUser, request_id: int, remarks: str) -> LeaveRequestDetail:
        row = self._one(actor, request_id)[0]
        self._mine._history(row.id, row.status, row.status, f"Comment: {remarks.strip()}"[:500], actor.id)
        self._db.commit()
        return self.detail(actor, request_id)

    def _pending(self, actor: CurrentUser, request_id: int, action: str) -> tuple[LeaveRequest, Employee]:
        row = self._lock(request_id)
        employee = self._lock_employee(row.employee_id)
        if not self._visible(actor, employee.id):
            raise NotFound("Leave request not found.")
        if row.status != "Pending":
            raise LeaveRuleError(f"Only a pending request can be {action}.")
        if not self._can_decide(actor, employee):
            if actor.employee_id == employee.id:
                raise LeaveRuleError("You cannot decide your own leave.")
            raise Forbidden("You can only decide leave for employees who report to you.")
        return row, employee

    def _checked_days(self, employee: Employee, row: LeaveRequest) -> Decimal:
        data = MineApply(
            leave_type_id=row.leave_type_id,
            from_date=row.from_date,
            to_date=row.to_date,
            is_half_day=row.is_half_day,
            half_day_part="First half" if row.is_half_day else None,
            reason=row.reason or "Leave",
        )
        return self._mine._validated_days(employee, data, current_id=row.id)

    def _deduct(self, employee_id: int, leave_type_id: int, start: date, days: Decimal, user_id: int) -> None:
        year = _financial_year(start)
        stmt = select(LeaveBalance).where(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.leave_year == year,
            LeaveBalance.is_active == True,  # noqa: E712
        ).order_by(LeaveBalance.id)
        if self._db.get_bind().dialect.name != "sqlite":
            stmt = stmt.with_for_update()
        balance = self._db.scalars(stmt).all()
        if not balance:
            raise LeaveRuleError("No leave balance row exists for this request.")
        chosen = balance[-1]
        chosen.availed = (chosen.availed or _ZERO) + days
        chosen.closing = (chosen.closing or _ZERO) - days
        chosen.updated_by_user_id = user_id

    def _finish(self, row: LeaveRequest, status: str, remarks: str, actor: CurrentUser) -> None:
        previous = row.status
        row.status = status
        row.approver_user_id = actor.id
        row.acted_at = datetime.now(UTC).replace(tzinfo=None)
        row.updated_by_user_id = actor.id
        self._mine._history(row.id, previous, status, remarks[:500], actor.id)

    def _clauses(self, actor: CurrentUser, query: LeaveRequestFilter) -> list[object]:
        clauses: list[object] = [
            LeaveRequest.is_active == True,  # noqa: E712
            LeaveRequest.status.in_(("Pending", "Approved", "Rejected")),
            LeaveRequest.employee_id.in_(self._scope(actor)),
        ]
        if query.department_id is not None:
            clauses.append(Employee.department_id == query.department_id)
        if query.leave_type_id is not None:
            clauses.append(LeaveRequest.leave_type_id == query.leave_type_id)
        if query.from_date is not None:
            clauses.append(LeaveRequest.from_date >= query.from_date)
        if query.to_date is not None:
            clauses.append(LeaveRequest.from_date <= query.to_date)
        if query.search and query.search.strip():
            clauses.append(self._search(query.search.strip()))
        return clauses

    def _search(self, term: str):
        like = f"%{term.replace('%', '').replace('_', '')}%"
        clauses = [
            Employee.employee_code.like(like),
            Employee.first_name.like(like),
            Employee.last_name.like(like),
        ]
        token = term.upper().removeprefix("LV-").lstrip("0") or "0"
        if token.isdigit():
            clauses.append(LeaveRequest.id == int(token))
        return or_(*clauses)

    def _scope(self, actor: CurrentUser) -> Select[tuple[int]]:
        query = select(Employee.id).where(Employee.status == "Active", Employee.is_active == True)  # noqa: E712
        if not actor.can("hr.leave.manage", "hr.leave.approve"):
            person = actor.employee_id
            query = query.where(or_(Employee.id == person, Employee.reporting_manager_id == person))
        return query

    def _visible(self, actor: CurrentUser, employee_id: int) -> bool:
        return employee_id in set(self._db.scalars(self._scope(actor)).all())

    def _can_decide(self, actor: CurrentUser, employee: Employee) -> bool:
        if actor.employee_id is not None and actor.employee_id == employee.id:
            return False
        if actor.can("hr.leave.manage"):
            return True
        return bool(
            actor.can("hr.leave.approve")
            and actor.employee_id is not None
            and employee.reporting_manager_id == actor.employee_id
        )

    def _joined(self):
        manager = aliased(Employee)
        return (
            select(
                LeaveRequest,
                Employee,
                Department.name,
                Designation.name,
                Branch.name,
                manager.first_name,
                manager.last_name,
                LeaveType,
            )
            .join(Employee, Employee.id == LeaveRequest.employee_id)
            .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(Designation, Designation.id == Employee.designation_id)
            .outerjoin(Branch, Branch.id == Employee.branch_id)
            .outerjoin(manager, manager.id == Employee.reporting_manager_id)
        )

    def _ordered(self, stmt, sort: str | None):
        raw = sort or "-appliedOn"
        descending = raw.startswith("-")
        key = raw.lstrip("-")
        columns = {
            "appliedOn": LeaveRequest.created_at,
            "fromDate": LeaveRequest.from_date,
            "employee": Employee.first_name,
            "status": LeaveRequest.status,
            "days": LeaveRequest.days,
            "requestId": LeaveRequest.id,
        }
        column = columns.get(key, LeaveRequest.created_at)
        direction = column.desc() if descending else column.asc()
        return stmt.order_by(direction, LeaveRequest.id.desc())

    def _one(self, actor: CurrentUser, request_id: int):
        found = self._db.execute(
            self._joined().where(LeaveRequest.id == request_id, *self._clauses(actor, LeaveRequestFilter()))
        ).first()
        if found is None:
            raise NotFound("Leave request not found.")
        return found

    def _item(
        self,
        actor: CurrentUser,
        row: LeaveRequest,
        employee: Employee,
        department: str | None,
        designation: str | None,
        location: str | None,
        manager_first: str | None,
        manager_last: str | None,
        leave_type: LeaveType,
        balances: dict[tuple[int, int, int], Decimal],
    ) -> LeaveRequestRow:
        applied = row.created_at.date() if row.created_at is not None else row.from_date
        year = _financial_year(row.from_date)
        return LeaveRequestRow(
            request_id=row.id,
            display_id=f"LV-{row.id:04d}",
            employee=LeaveRequestEmployee(
                code=employee.employee_code,
                name=_person(employee.first_name, employee.last_name),
                department=department,
                designation=designation,
                location=location,
                manager=_person(manager_first, manager_last) or None,
            ),
            leave_type_id=leave_type.id,
            leave_type=f"{leave_type.name} ({leave_type.code})",
            leave_code=leave_type.code,
            from_date=row.from_date,
            to_date=row.to_date,
            is_half_day=row.is_half_day,
            days=row.days,
            reason=row.reason,
            applied_on=applied,
            status=row.status,
            balance=balances.get((employee.id, leave_type.id, year)),
            can_approve=row.status == "Pending" and self._can_decide(actor, employee),
        )

    def _balances(self, rows: list[LeaveRequest]) -> dict[tuple[int, int, int], Decimal]:
        if not rows:
            return {}
        found = self._db.scalars(
            select(LeaveBalance)
            .where(
                LeaveBalance.employee_id.in_({row.employee_id for row in rows}),
                LeaveBalance.leave_year.in_({_financial_year(row.from_date) for row in rows}),
                LeaveBalance.is_active == True,  # noqa: E712
            )
            .order_by(LeaveBalance.id)
        ).all()
        return {(row.employee_id, row.leave_type_id, row.leave_year): row.closing for row in found}

    def _history(self, row: LeaveRequest) -> list[LeaveHistoryEvent]:
        stored = self._db.scalars(
            select(StatusHistory)
            .where(StatusHistory.entity_type == _ENTITY, StatusHistory.entity_id == row.id)
            .order_by(StatusHistory.changed_at, StatusHistory.id)
        ).all()
        if stored:
            return [
                LeaveHistoryEvent(
                    id=item.id,
                    action="Comment" if item.from_status == item.to_status else (item.to_status or "Updated"),
                    actor=self._actor(item.changed_by_user_id),
                    at=item.changed_at.date(),
                    remarks=(item.remarks or "").removeprefix("Comment: ").strip(),
                )
                for item in stored
            ]
        applied = row.created_at.date() if row.created_at is not None else row.from_date
        actor = self._actor(row.created_by_user_id) if row.created_by_user_id else self._employee_name(row.employee_id)
        events = [
            LeaveHistoryEvent(id=0, action="Applied", actor=actor, at=applied, remarks=row.reason or "Submitted.")
        ]
        if row.status in ("Approved", "Rejected") and row.acted_at is not None:
            events.append(
                LeaveHistoryEvent(
                    id=-1,
                    action=row.status,
                    actor=self._actor(row.approver_user_id),
                    at=row.acted_at.date(),
                    remarks="",
                )
            )
        return events

    def _employee_name(self, employee_id: int) -> str:
        person = self._db.get(Employee, employee_id)
        if person is None:
            return "Employee"
        return _person(person.first_name, person.last_name)

    def _actor(self, user_id: int | None) -> str:
        if user_id is None:
            return "System"
        found = self._db.execute(
            select(Employee.first_name, Employee.last_name, AppUser.username)
            .select_from(AppUser)
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .where(AppUser.id == user_id)
        ).first()
        if found is None:
            return "User"
        first, last, username = found
        return _person(first, last) or username

    def _departments(self, actor: CurrentUser) -> list[LeaveOption]:
        rows = self._db.execute(
            select(Department.id, Department.name)
            .where(
                Department.id.in_(
                    select(Employee.department_id).where(
                        Employee.id.in_(self._scope(actor)),
                        Employee.department_id.is_not(None),
                    )
                )
            )
            .order_by(Department.name)
        ).all()
        return [LeaveOption(id=row.id, name=row.name) for row in rows]

    def _types(self) -> list[LeaveOption]:
        rows = self._db.scalars(select(LeaveType).where(LeaveType.is_active == True).order_by(LeaveType.name)).all()  # noqa: E712
        return [LeaveOption(id=row.id, name=f"{row.name} ({row.code})") for row in rows]

    def _lock(self, request_id: int) -> LeaveRequest:
        stmt = select(LeaveRequest).where(LeaveRequest.id == request_id)
        if self._db.get_bind().dialect.name != "sqlite":
            stmt = stmt.with_for_update()
        row = self._db.scalars(stmt).one_or_none()
        if row is None or not row.is_active:
            raise NotFound("Leave request not found.")
        return row

    def _lock_employee(self, employee_id: int) -> Employee:
        stmt = select(Employee).where(Employee.id == employee_id)
        if self._db.get_bind().dialect.name != "sqlite":
            stmt = stmt.with_for_update()
        employee = self._db.scalars(stmt).one_or_none()
        if employee is None:
            raise NotFound("Employee not found.")
        return employee


def _person(first: str | None, last: str | None) -> str:
    return " ".join(part for part in (first, last) if part).strip()
