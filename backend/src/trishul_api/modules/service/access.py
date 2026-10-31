"""Who may see and change what on a service call (shared by the router and the services)."""

from typing import get_args

from trishul_api.auth import CurrentUser
from trishul_api.db.models.generated.svc import ServiceCallCurrentStatus

# Any of these opens the full call register (svc.call.view comes from migration 0001). The Angular guard
# and menu use the same codes: SERVICE_CALL_VIEW_PERMISSIONS in libs/domains/service/data-access.
CAN_VIEW_CALLS = ("svc.call.view", "svc.call.create", "svc.call.assign")
# A Service Engineer sees only the calls assigned to them (migration 0007).
CAN_VIEW_OWN_CALLS = "svc.call.view.assigned"

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
# A call can be reopened only once it has been finished one way or another.
_FINISHED = frozenset({"Closed", "Completed", "Cancelled", "Pending OEM closure"})


def can_see_call(actor: CurrentUser, assigned_engineer_id: int | None) -> bool:
    """The register roles see every call; an engineer sees only their own."""
    if actor.can(*CAN_VIEW_CALLS):
        return True
    return actor.employee_id is not None and assigned_engineer_id == actor.employee_id


def allowed_statuses(actor: CurrentUser, current_status: str, assigned_engineer_id: int | None) -> list[str]:
    """The statuses this user may move the call to, in workflow order.

    * svc.call.assign (team lead): any status except the protected ones, on any call.
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
