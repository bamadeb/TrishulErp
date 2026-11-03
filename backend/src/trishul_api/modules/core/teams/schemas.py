from datetime import date
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, RowVersion, UtcDateTime
from trishul_api.db.models.generated.core import TeamTeamType

TeamStatusFilter = Literal["active", "inactive", "all"]


class TeamQuery(ApiModel):
    """Teams are a short list, so it is not paged."""

    status: TeamStatusFilter = "active"
    branch_id: int | None = Field(None, gt=0)
    search: str | None = Field(None, max_length=100, description="Team name or lead's name.")


class TeamListItem(ApiModel):
    id: int
    name: str
    team_type: TeamTeamType
    branch_id: int
    branch_name: str
    team_lead_employee_id: int
    team_lead_name: str
    is_active: bool
    member_count: int = Field(0, description="Employees currently in the team.")


class TeamMemberItem(ApiModel):
    employee_id: int
    employee_code: str
    name: str
    designation: str | None
    from_date: date


class TeamDetail(TeamListItem):
    members: list[TeamMemberItem]
    created_at: UtcDateTime
    updated_at: UtcDateTime | None
    row_version: RowVersion


class TeamCreate(InputModel):
    name: str = Field(min_length=1, max_length=80)
    team_type: TeamTeamType = "Service"
    branch_id: int = Field(gt=0, description="Cannot be changed later.")
    team_lead_employee_id: int = Field(gt=0)
    member_employee_ids: list[int] = Field(default_factory=list, max_length=200)


class TeamUpdate(InputModel):
    """Only the fields sent are changed. memberEmployeeIds, when sent, is the team's complete list."""

    name: str | None = Field(None, min_length=1, max_length=80)
    team_type: TeamTeamType | None = None
    team_lead_employee_id: int | None = Field(None, gt=0)
    member_employee_ids: list[int] | None = Field(None, max_length=200)


class TeamEmployeeOptionQuery(ApiModel):
    branch_id: int = Field(gt=0)
    search: str | None = Field(None, max_length=100)
    limit: int = Field(200, ge=1, le=500)


class TeamEmployeeOption(ApiModel):
    id: int
    employee_code: str
    name: str
    designation: str | None
    designation_code: str | None
