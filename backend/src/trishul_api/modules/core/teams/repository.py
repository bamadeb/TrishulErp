from collections.abc import Collection
from datetime import date
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import Session, aliased

from trishul_api.db.models import Branch, Designation, Employee, Team, TeamMember
from trishul_api.modules.core.teams.schemas import (
    TeamEmployeeOption,
    TeamEmployeeOptionQuery,
    TeamListItem,
    TeamMemberItem,
    TeamQuery,
)

_lead = aliased(Employee)


def _name(employee: type[Employee]) -> ColumnElement[str]:
    return func.concat_ws(" ", employee.first_name, employee.last_name)


def current_member(today: date) -> ColumnElement[bool]:
    """A core.team_member row that counts today (the service-call register uses the same test)."""
    return (
        TeamMember.is_active
        & (TeamMember.from_date <= today)
        & or_(TeamMember.to_date.is_(None), TeamMember.to_date >= today)
    )


def _member_count(today: date) -> ColumnElement[int]:
    return (
        select(func.count(TeamMember.id))
        .where(TeamMember.team_id == Team.id, current_member(today))
        .correlate(Team)
        .scalar_subquery()
    )


def _list_select(today: date) -> Select[*tuple[Any, ...]]:
    """Columns of TeamListItem."""
    return (
        select(
            Team.id,
            Team.name,
            Team.team_type,
            Team.branch_id,
            Branch.name.label("branch_name"),
            Team.team_lead_employee_id,
            _name(_lead).label("team_lead_name"),
            Team.is_active,
            _member_count(today).label("member_count"),
        )
        .join(Branch, Branch.id == Team.branch_id)
        .join(_lead, _lead.id == Team.team_lead_employee_id)
    )


class TeamRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ reads

    def search(self, query: TeamQuery, branch_ids: frozenset[int] | None) -> list[TeamListItem]:
        """branch_ids: the user's branches (None: all)."""
        statement = _list_select(date.today())
        if branch_ids is not None:
            statement = statement.where(Team.branch_id.in_(branch_ids or [0]))
        if query.branch_id is not None:
            statement = statement.where(Team.branch_id == query.branch_id)
        if query.status != "all":
            statement = statement.where(Team.is_active == (query.status == "active"))
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(Team.name.contains(term, autoescape=True), _name(_lead).contains(term, autoescape=True))
            )
        rows = self._session.execute(statement.order_by(Branch.name, Team.name, Team.id)).mappings()
        return [TeamListItem.model_validate(row) for row in rows]

    def get(self, team_id: int) -> Team | None:
        return self._session.get(Team, team_id)

    def detail_row(self, team_id: int) -> dict[str, Any]:
        """One team with every field TeamDetail needs; the team must exist."""
        today = date.today()
        statement = (
            _list_select(today)
            .add_columns(Team.created_at, Team.updated_at, Team.row_version)
            .where(Team.id == team_id)
        )
        row = dict(self._session.execute(statement).mappings().one())
        members = self._session.execute(
            select(
                Employee.id.label("employee_id"),
                Employee.employee_code,
                _name(Employee).label("name"),
                Designation.name.label("designation"),
                TeamMember.from_date,
            )
            .join(Employee, Employee.id == TeamMember.employee_id)
            .outerjoin(Designation, Designation.id == Employee.designation_id)
            .where(TeamMember.team_id == team_id, current_member(today))
            .order_by(Employee.first_name, Employee.last_name)
        ).mappings()
        row["members"] = [TeamMemberItem.model_validate(member) for member in members]
        return row

    def current_members(self, team_id: int) -> list[TeamMember]:
        return list(
            self._session.scalars(select(TeamMember).where(TeamMember.team_id == team_id, current_member(date.today())))
        )

    def active_employees(self, employee_ids: Collection[int], branch_id: int) -> set[int]:
        """Those of `employee_ids` who are active employees of the branch."""
        if not employee_ids:
            return set()
        return set(
            self._session.scalars(
                select(Employee.id).where(
                    Employee.id.in_(employee_ids), Employee.is_active, Employee.branch_id == branch_id
                )
            )
        )

    def memberships_elsewhere(
        self, employee_ids: Collection[int], team_type: str, team_id: int | None
    ) -> list[tuple[str, str]]:
        """(employee name, team name) for each of `employee_ids` already in another active team of this type."""
        if not employee_ids:
            return []
        statement = (
            select(_name(Employee), Team.name)
            .join(TeamMember, TeamMember.employee_id == Employee.id)
            .join(Team, Team.id == TeamMember.team_id)
            .where(
                Employee.id.in_(employee_ids),
                Team.is_active,
                Team.team_type == team_type,
                current_member(date.today()),
            )
            .order_by(Employee.first_name)
        )
        if team_id is not None:
            statement = statement.where(Team.id != team_id)
        return [(name, team) for name, team in self._session.execute(statement)]

    def name_owner(self, branch_id: int, name: str) -> int | None:
        """The id of the active team of the branch with this name, or None."""
        return self._session.scalar(
            select(Team.id).where(Team.branch_id == branch_id, Team.name == name, Team.is_active).limit(1)
        )

    def employee_options(self, query: TeamEmployeeOptionQuery) -> list[TeamEmployeeOption]:
        name = _name(Employee)
        statement = (
            select(
                Employee.id,
                Employee.employee_code,
                name.label("name"),
                Designation.name.label("designation"),
                Designation.code.label("designation_code"),
            )
            .outerjoin(Designation, Designation.id == Employee.designation_id)
            .where(Employee.is_active, Employee.branch_id == query.branch_id)
        )
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(name.contains(term, autoescape=True), Employee.employee_code.contains(term, autoescape=True))
            )
        statement = statement.order_by(Employee.first_name, Employee.last_name).limit(query.limit)
        return [TeamEmployeeOption.model_validate(row) for row in self._session.execute(statement).mappings()]

    # ------------------------------------------------------------------ writes (committed by the service)

    def add(self, row: object) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()
