"""Who is on a service call: one lead engineer and any number of support engineers.

svc.service_call.assigned_engineer_id stays the lead, so reports and alerts keep one owner per call. The
support engineers are the current 'Support' rows of svc.call_assignment; that table also keeps the history
of who was on the call. Everyone on the call sees it in their list and can work it.
"""

from collections.abc import Collection, Iterable
from datetime import date, datetime

from sqlalchemy import ColumnElement, Select, and_, exists, func, select
from sqlalchemy.orm import Session

from trishul_api.db.models import CallAssignment, CallAssignmentAssignmentType, Employee, ServiceCall, ServiceVisit
from trishul_api.modules.service.schemas import CallEngineer


def _current_support() -> ColumnElement[bool]:
    return and_(CallAssignment.assignment_type == "Support", CallAssignment.is_current, CallAssignment.is_active)


def supports_call(engineer_ids: Collection[int]) -> ColumnElement[bool]:
    """SQL: one of these engineers is on the call as support."""
    return exists().where(
        CallAssignment.service_call_id == ServiceCall.id,
        CallAssignment.engineer_employee_id.in_(sorted(engineer_ids)),
        _current_support(),
    )


def support_ids(db: Session, call_id: int) -> set[int]:
    return set(
        db.scalars(
            select(CallAssignment.engineer_employee_id).where(
                CallAssignment.service_call_id == call_id, _current_support()
            )
        )
    )


def assignees(db: Session, call: ServiceCall) -> set[int]:
    """Everyone on the call: the lead and the support engineers."""
    on_call = support_ids(db, call.id)
    if call.assigned_engineer_id is not None:
        on_call.add(call.assigned_engineer_id)
    return on_call


def support_engineers(db: Session, call_ids: Iterable[int]) -> dict[int, list[CallEngineer]]:
    """The support engineers of each call, by name; calls without any are left out."""
    ids = sorted(set(call_ids))
    if not ids:
        return {}
    rows = db.execute(
        select(
            CallAssignment.service_call_id,
            Employee.id,
            func.concat_ws(" ", Employee.first_name, Employee.last_name).label("name"),
        )
        .join(Employee, Employee.id == CallAssignment.engineer_employee_id)
        .where(CallAssignment.service_call_id.in_(ids), _current_support())
        .order_by(Employee.first_name, Employee.last_name)
    )
    found: dict[int, list[CallEngineer]] = {}
    for row in rows:
        found.setdefault(row.service_call_id, []).append(CallEngineer(id=row.id, name=row.name))
    return found


def set_engineers(
    db: Session, call: ServiceCall, lead_id: int | None, support: Collection[int], user_id: int, now: datetime
) -> None:
    """Make this the call's lead and support engineers. Rows that no longer apply are closed, not deleted."""
    wanted: set[tuple[int, CallAssignmentAssignmentType]] = {(engineer, "Support") for engineer in support}
    if lead_id is not None:
        wanted.add((lead_id, "Primary"))
    kept: set[tuple[int, CallAssignmentAssignmentType]] = set()
    current = db.scalars(
        select(CallAssignment).where(
            CallAssignment.service_call_id == call.id, CallAssignment.is_current, CallAssignment.is_active
        )
    )
    for row in current:
        key = (row.engineer_employee_id, row.assignment_type)
        if key in wanted:
            kept.add(key)
        else:
            row.is_current = False
            row.unassigned_at = now
            row.updated_at = now
            row.updated_by_user_id = user_id
    db.flush()  # the old lead's row closes before the new lead's opens (UX_svc_call_assignment_current_primary)
    for engineer, assignment_type in sorted(wanted - kept):
        db.add(
            CallAssignment(
                service_call_id=call.id,
                engineer_employee_id=engineer,
                assignment_type=assignment_type,
                assigned_by_user_id=user_id,
                assigned_at=now,
                is_current=True,
                created_by_user_id=user_id,
            )
        )
    call.assigned_engineer_id = lead_id
    # Someone off the call no longer has that day's visit, or it would still count in their workload.
    on_call = {engineer for engineer, _ in wanted}
    for visit in db.scalars(_planned_visits(call.id)):
        if visit.engineer_employee_id not in on_call:
            visit.status = "Cancelled"
            visit.updated_at = now
            visit.updated_by_user_id = user_id


def _planned_visits(call_id: int) -> Select[ServiceVisit]:
    return select(ServiceVisit).where(
        ServiceVisit.service_call_id == call_id, ServiceVisit.status == "Planned", ServiceVisit.is_active
    )


def plan_visit(db: Session, call: ServiceCall, engineer_id: int, day: date, user_id: int, now: datetime) -> None:
    """Put the engineer's visit on that day. Starting a trip picks this visit up (trk.handlers)."""
    visit = db.scalars(_planned_visits(call.id).where(ServiceVisit.engineer_employee_id == engineer_id)).first()
    if visit is not None:
        visit.planned_date = day
        visit.updated_at = now
        visit.updated_by_user_id = user_id
        return
    last = db.scalar(select(func.max(ServiceVisit.visit_no)).where(ServiceVisit.service_call_id == call.id)) or 0
    db.add(
        ServiceVisit(
            service_call_id=call.id,
            visit_no=last + 1,
            visit_purpose="Inspection",
            engineer_employee_id=engineer_id,
            planned_date=day,
            status="Planned",
            created_by_user_id=user_id,
        )
    )
