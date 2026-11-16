"""Reads and stores leave types and policies."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trishul_api.db.models import (
    Branch,
    Department,
    LeavePolicy,
    LeavePolicyLine,
    LeaveType,
    LeaveTypeSetting,
    State,
)
from trishul_api.modules.hr.leave.schemas import LeavePolicyQuery, LeaveTypeQuery


class LeaveRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: LeaveType | LeaveTypeSetting | LeavePolicy | LeavePolicyLine) -> None:
        self._session.add(row)
        self._session.flush()

    def leave_type(self, leave_type_id: int) -> LeaveType | None:
        return self._session.get(LeaveType, leave_type_id)

    def setting(self, leave_type_id: int) -> LeaveTypeSetting | None:
        return self._session.get(LeaveTypeSetting, leave_type_id)

    def code_owner(self, code: str) -> int | None:
        return self._session.scalar(select(LeaveType.id).where(func.upper(LeaveType.code) == code.upper()).limit(1))

    def search_types(self, query: LeaveTypeQuery) -> tuple[list[tuple[LeaveType, LeaveTypeSetting | None]], int]:
        statement = select(LeaveType, LeaveTypeSetting).outerjoin(
            LeaveTypeSetting, LeaveTypeSetting.leave_type_id == LeaveType.id
        )
        if query.status == "active":
            statement = statement.where(LeaveType.is_active == True)  # noqa: E712
        elif query.status == "inactive":
            statement = statement.where(LeaveType.is_active == False)  # noqa: E712
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                LeaveType.code.contains(term, autoescape=True) | LeaveType.name.contains(term, autoescape=True)
            )
        total = int(self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        rows = self._session.execute(
            statement.order_by(LeaveType.name).offset((query.page - 1) * query.page_size).limit(query.page_size)
        ).all()
        return [(row[0], row[1]) for row in rows], total

    def policy(self, policy_id: int) -> LeavePolicy | None:
        return self._session.get(LeavePolicy, policy_id)

    def policy_name_owner(self, name: str) -> int | None:
        return self._session.scalar(
            select(LeavePolicy.id).where(func.lower(LeavePolicy.name) == name.strip().lower()).limit(1)
        )

    def lines(self, policy_id: int, *, active_only: bool = True) -> list[tuple[LeavePolicyLine, LeaveType]]:
        statement = (
            select(LeavePolicyLine, LeaveType)
            .join(LeaveType, LeaveType.id == LeavePolicyLine.leave_type_id)
            .where(LeavePolicyLine.leave_policy_id == policy_id)
            .order_by(LeaveType.name)
        )
        if active_only:
            statement = statement.where(LeavePolicyLine.is_active == True)  # noqa: E712
        rows = self._session.execute(statement).all()
        return [(row[0], row[1]) for row in rows]

    def search_policies(self, query: LeavePolicyQuery) -> tuple[list[LeavePolicy], int]:
        statement = select(LeavePolicy)
        if query.status == "active":
            statement = statement.where(LeavePolicy.is_active == True)  # noqa: E712
        elif query.status == "inactive":
            statement = statement.where(LeavePolicy.is_active == False)  # noqa: E712
        if query.department_id is not None:
            statement = statement.where(LeavePolicy.department_id == query.department_id)
        if query.branch_id is not None:
            statement = statement.where(LeavePolicy.branch_id == query.branch_id)
        if query.search:
            statement = statement.where(LeavePolicy.name.contains(query.search.strip(), autoescape=True))
        total = int(self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        rows = self._session.scalars(
            statement.order_by(LeavePolicy.name).offset((query.page - 1) * query.page_size).limit(query.page_size)
        ).all()
        return list(rows), total

    def department_name(self, department_id: int | None) -> str | None:
        if department_id is None:
            return None
        return self._session.scalar(select(Department.name).where(Department.id == department_id))

    def branch_name(self, branch_id: int | None) -> str | None:
        if branch_id is None:
            return None
        return self._session.scalar(select(Branch.name).where(Branch.id == branch_id))

    def department_exists(self, department_id: int) -> bool:
        return self._session.get(Department, department_id) is not None

    def branch_exists(self, branch_id: int) -> bool:
        return self._session.get(Branch, branch_id) is not None

    def state_name(self, state_id: int | None) -> str | None:
        if state_id is None:
            return None
        return self._session.scalar(select(State.name).where(State.id == state_id))

    def state_exists(self, state_id: int) -> bool:
        return self._session.get(State, state_id) is not None
