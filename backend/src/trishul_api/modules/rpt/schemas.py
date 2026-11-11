"""The home dashboard. Each section is present only for users whose permissions cover it."""

import datetime as dt
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel
from trishul_api.modules.service.schemas import CallPriority, CallStatus


class DashboardVisit(ApiModel):
    """A service call with a planned visit (not yet started): its earliest planned day and who is planned."""

    service_call_id: int
    call_no: str
    customer_name: str
    machine_model: str | None
    machine_serial_no: str | None
    complaint_description: str
    priority: CallPriority
    is_machine_down: bool
    current_status: CallStatus
    planned_date: dt.date
    engineer_name: str | None = Field(description="Everyone planned for the call, comma separated.")


class MyWork(ApiModel):
    """The signed-in engineer's own calls and visits."""

    open_calls: int = Field(description="Open calls they are on, as lead or support.")
    machine_down: int = Field(description="Of those, calls with the machine down.")
    visits_today: int = Field(description="Calls with my visit planned for today.")
    visits_tomorrow: int
    overdue_visits: int = Field(description="Calls whose planned day has passed without my visit starting.")
    upcoming: list[DashboardVisit] = Field(
        description="Overdue visits and the next 7 days, earliest first (at most 10)."
    )


class StatusCount(ApiModel):
    status: CallStatus
    count: int


class EngineerLoad(ApiModel):
    engineer_id: int
    name: str
    open_calls: int = Field(description="Open calls they lead or support.")
    visits_today: int


class CallsOverview(ApiModel):
    """Calls the user oversees: every call (office, management) or their team's (team lead)."""

    scope: Literal["all", "team"]
    open_calls: int
    unassigned: int
    machine_down: int
    sla_breached: int = Field(description="Open calls past their SLA due time.")
    sla_due_soon: int = Field(description="Open calls due within the next 24 hours.")
    visits_today: int = Field(description="Calls with a visit planned for today.")
    visits_tomorrow: int
    overdue_visits: int = Field(description="Calls whose planned visit day has passed without the visit starting.")
    completed_this_month: int
    by_status: list[StatusCount] = Field(description="Open calls per status, in workflow order.")
    engineers: list[EngineerLoad] = Field(description="Busiest engineers first (at most 10).")
    overdue: list[DashboardVisit] = Field(description="Calls with an overdue visit, oldest first (at most 10).")


class ExpiringContract(ApiModel):
    id: int
    contract_no: str
    customer_name: str
    machine_serial_no: str | None
    end_date: dt.date
    visits_remaining: int | None


class AscOverview(ApiModel):
    """ASC contracts the user may see."""

    active: int
    expiring_soon: int = Field(description="Active and ending within 30 days.")
    visits_included: int = Field(description="Visits of the active contracts that have a limit.")
    visits_used: int
    visits_remaining: int
    calls_to_count: int = Field(
        description="Completed or closed calls linked to a live ASC whose visits are not counted yet."
    )
    expiring: list[ExpiringContract] = Field(description="Soonest first (at most 5).")


class Dashboard(ApiModel):
    """Sections the user's permissions allow; a missing section is None."""

    my_work: MyWork | None = None
    calls: CallsOverview | None = None
    asc: AscOverview | None = None
