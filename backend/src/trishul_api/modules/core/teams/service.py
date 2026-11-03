"""Team management (core.team and core.team_member): add, rename, choose lead and members, activate/deactivate.

A team belongs to one branch for good; its lead and members must be active employees of that branch. An
employee is in at most one active team of each type, so a call's engineer has a single team lead. The
lead is not a member of their own team (they see their own calls anyway).

Leaving a team ends the membership (to_date today, row inactive) rather than deleting it, so the history
of who was in which team stays. Team leads see their team's service calls from the next request.
"""

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.db.models import Team, TeamMember
from trishul_api.modules.core.teams.repository import TeamRepository
from trishul_api.modules.core.teams.schemas import TeamCreate, TeamDetail, TeamUpdate


class TeamService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor
        self._repo = TeamRepository(db)

    def get(self, team_id: int) -> TeamDetail:
        self._require(team_id)
        return self._detail(team_id)

    def create(self, data: TeamCreate) -> TeamDetail:
        if not self._actor.can_use_branch(data.branch_id):
            raise ApiError("You do not have access to that branch.", errors={"branchId": ["Not one of your branches."]})
        name = data.name.strip()
        self._check_name(data.branch_id, name, None)
        members = set(data.member_employee_ids)
        self._check_people(data.branch_id, data.team_lead_employee_id, members)
        self._check_elsewhere(members, data.team_type, None)

        team = Team(
            branch_id=data.branch_id,
            name=name,
            team_type=data.team_type,
            team_lead_employee_id=data.team_lead_employee_id,
            created_by_user_id=self._actor.id,
        )
        self._repo.add(team)
        self._repo.flush()
        self._set_members(team.id, members)
        team_id = team.id
        self._db.commit()
        return self._detail(team_id)

    def update(self, team_id: int, expected_row_version: bytes, data: TeamUpdate) -> TeamDetail:
        team = self._require(team_id)
        check_row_version(team.row_version, expected_row_version)
        changed = data.model_fields_set

        name = data.name.strip() if "name" in changed and data.name else team.name
        team_type = data.team_type if "team_type" in changed and data.team_type else team.team_type
        lead = (
            data.team_lead_employee_id
            if "team_lead_employee_id" in changed and data.team_lead_employee_id
            else team.team_lead_employee_id
        )
        if "member_employee_ids" in changed and data.member_employee_ids is not None:
            members = set(data.member_employee_ids)
        else:
            members = {row.employee_id for row in self._repo.current_members(team_id)}

        if team.is_active:
            self._check_name(team.branch_id, name, team_id)
            self._check_elsewhere(members, team_type, team_id)
        self._check_people(team.branch_id, lead, members)

        team.name = name
        team.team_type = team_type
        team.team_lead_employee_id = lead
        self._set_members(team_id, members)
        _touch(team, self._actor)  # also moves row_version, so a stale form can't overwrite the member list
        self._db.commit()
        return self._detail(team_id)

    def deactivate(self, team_id: int) -> TeamDetail:
        team = self._require(team_id)
        if team.is_active:
            team.is_active = False
            _touch(team, self._actor)
            self._db.commit()
        return self._detail(team_id)

    def activate(self, team_id: int) -> TeamDetail:
        team = self._require(team_id)
        if not team.is_active:
            # Meanwhile another team may have taken the name or some of the members.
            self._check_name(team.branch_id, team.name, team_id)
            members = {row.employee_id for row in self._repo.current_members(team_id)}
            self._check_elsewhere(members, team.team_type, team_id)
            team.is_active = True
            _touch(team, self._actor)
            self._db.commit()
        return self._detail(team_id)

    # ------------------------------------------------------------------ helpers

    def _require(self, team_id: int) -> Team:
        team = self._repo.get(team_id)
        if team is None or not self._actor.can_use_branch(team.branch_id):
            raise NotFound("Team not found.")
        return team

    def _detail(self, team_id: int) -> TeamDetail:
        return TeamDetail.model_validate(self._repo.detail_row(team_id))

    def _check_name(self, branch_id: int, name: str, team_id: int | None) -> None:
        owner = self._repo.name_owner(branch_id, name)
        if owner is not None and owner != team_id:
            raise AlreadyExists(f"The branch already has a team named '{name}'.")

    def _check_people(self, branch_id: int, lead_id: int, member_ids: set[int]) -> None:
        errors: dict[str, list[str]] = {}
        found = self._repo.active_employees(member_ids | {lead_id}, branch_id)
        if lead_id not in found:
            errors["teamLeadEmployeeId"] = ["Pick an active employee of the team's branch."]
        unknown = sorted(member_ids - found)
        if unknown:
            errors["memberEmployeeIds"] = [
                f"Employee {i} is not an active employee of the team's branch." for i in unknown
            ]
        elif lead_id in member_ids:
            errors["memberEmployeeIds"] = ["The team lead can't also be a member of the team."]
        if errors:
            raise ApiError("Some of the selected people can't be in this team.", errors=errors)

    def _check_elsewhere(self, member_ids: set[int], team_type: str, team_id: int | None) -> None:
        taken = self._repo.memberships_elsewhere(member_ids, team_type, team_id)
        if taken:
            raise ApiError(
                f"Some people are already in another {team_type.lower()} team.",
                errors={"memberEmployeeIds": [f"{person} is in {team}." for person, team in taken]},
            )

    def _set_members(self, team_id: int, wanted: set[int]) -> None:
        """End the memberships of those leaving and start one for each newcomer."""
        today = date.today()
        now = _now()
        current = {row.employee_id: row for row in self._repo.current_members(team_id)}
        for employee_id, row in current.items():
            if employee_id not in wanted:
                row.to_date = today
                row.is_active = False
                row.updated_at = now
                row.updated_by_user_id = self._actor.id
        for employee_id in wanted - current.keys():
            self._repo.add(
                TeamMember(team_id=team_id, employee_id=employee_id, from_date=today, created_by_user_id=self._actor.id)
            )


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _touch(team: Team, actor: CurrentUser) -> None:
    team.updated_at = _now()
    team.updated_by_user_id = actor.id
