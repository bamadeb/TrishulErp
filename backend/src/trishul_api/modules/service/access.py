"""Who may see and change what on a service call (shared by the router and the services)."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import get_args

from trishul_api.auth import CurrentUser
from trishul_api.db.models.generated.svc import ServiceCallCurrentStatus

# Which calls a user sees in the register (and may open), widest first; row-level security still limits
# all three to the user's branches and brands:
#   svc.call.view           every call (office, management)
#   svc.call.view.team      calls of the engineers in teams they lead, plus unassigned calls (team lead)
#   svc.call.view.assigned  calls assigned to them (service engineer)
# The Angular guard and menu use the same codes: SERVICE_CALL_VIEW_PERMISSIONS in libs/domains/service/data-access.
CAN_VIEW_ALL_CALLS = "svc.call.view"
CAN_VIEW_TEAM_CALLS = "svc.call.view.team"
CAN_VIEW_OWN_CALLS = "svc.call.view.assigned"
CAN_VIEW_CALLS = (CAN_VIEW_ALL_CALLS, CAN_VIEW_TEAM_CALLS, CAN_VIEW_OWN_CALLS)

ALL_STATUSES: tuple[str, ...] = get_args(ServiceCallCurrentStatus)  # in workflow order

# Finishing, cancelling and reopening need their own permissions (svc.call.close / cancel / reopen).
_PROTECTED = frozenset({"Closed", "Completed", "Cancelled", "Reopened"})
# The progress steps a Service Engineer can set on a call assigned to them.
_ENGINEER_STATUSES = frozenset(
    {
        "Call ID linked",
        "Customer contacted",
        "Trip started",
        "Reached site",
        "In progress",
        "Report submitted",
        "Awaiting parts",
        "Parts ready",
        "Revisit scheduled",
        "Pending OEM closure",
    }
)
# A call can be reopened only once it has been finished one way or another. Alerts treat the same
# statuses as "no longer open" (modules/alerts).
FINISHED_STATUSES = frozenset({"Closed", "Completed", "Cancelled", "Pending OEM closure"})
_FINISHED = FINISHED_STATUSES


@dataclass(frozen=True)
class CallVisibility:
    """The calls a user sees, on top of row-level security (branch and brand)."""

    everything: bool = False
    engineer_ids: frozenset[int] = frozenset()
    """Calls assigned to these employees."""
    unassigned: bool = False
    """Calls with no engineer yet."""

    def allows(self, assigned_engineer_id: int | None) -> bool:
        if self.everything:
            return True
        if assigned_engineer_id is None:
            return self.unassigned
        return assigned_engineer_id in self.engineer_ids


def call_visibility(actor: CurrentUser, team_members: Callable[[int], Iterable[int]]) -> CallVisibility:
    """team_members(lead_employee_id) returns the engineers currently in the teams that employee leads;
    it is only called for a team lead."""
    if actor.can(CAN_VIEW_ALL_CALLS):
        return CallVisibility(everything=True)
    engineer_ids: set[int] = set()
    unassigned = False
    if actor.employee_id is not None and actor.can(CAN_VIEW_TEAM_CALLS, CAN_VIEW_OWN_CALLS):
        engineer_ids.add(actor.employee_id)
    if actor.can(CAN_VIEW_TEAM_CALLS):
        unassigned = True  # so the team lead can assign them
        if actor.employee_id is not None:
            engineer_ids.update(team_members(actor.employee_id))
    return CallVisibility(engineer_ids=frozenset(engineer_ids), unassigned=unassigned)


def allowed_statuses(actor: CurrentUser, current_status: str, assigned_engineer_id: int | None) -> list[str]:
    """The statuses this user may move the call to, in workflow order.

    * svc.call.assign (team lead): any status except the protected ones, on any call they can see.
    * svc.call.status.update (engineer): their progress steps, on calls assigned to them.
    * svc.call.close / svc.call.cancel / svc.call.reopen: Closed+Completed / Cancelled / Reopened.
    """
    allowed: set[str] = set()
    if actor.can("svc.call.assign"):
        allowed.update(status for status in ALL_STATUSES if status not in _PROTECTED)
    if (
        actor.can("svc.call.status.update")
        and actor.employee_id is not None
        and assigned_engineer_id == actor.employee_id
    ):
        allowed.update(_ENGINEER_STATUSES)
    if actor.can("svc.call.close"):
        allowed.update({"Closed", "Completed"})
    if actor.can("svc.call.cancel"):
        allowed.add("Cancelled")
    if actor.can("svc.call.reopen") and current_status in _FINISHED:
        allowed.add("Reopened")
    allowed.discard(current_status)
    return [status for status in ALL_STATUSES if status in allowed]
