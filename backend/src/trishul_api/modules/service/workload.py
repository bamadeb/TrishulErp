"""What a team lead weighs up when assigning a call: each engineer's day, and how far they are from the site.

"Calls on a date" counts visits: the one planned when the call was assigned (assignment.plan_visit) or, with no
planned date, the one an engineer started a trip on that day. A call assigned without a date has no day yet, so
it only shows in the engineer's open calls.
"""

from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import RequestScope
from trishul_api.common.errors import NotFound
from trishul_api.db.models import (
    Branch,
    CallAssignment,
    CustomerSite,
    Holiday,
    LeaveRequest,
    MachineUnit,
    ServiceCall,
    ServiceVisit,
)
from trishul_api.modules.service.access import FINISHED_STATUSES, CallVisibility
from trishul_api.modules.service.assignment import assignees
from trishul_api.modules.service.repository import ServiceCallRepository
from trishul_api.modules.service.schemas import Availability, EngineerWorkload, EngineerWorkloadQuery
from trishul_api.modules.trk.distance import haversine_km

_AVAILABILITY_ORDER: dict[Availability, int] = {"Available": 0, "Half-day leave": 1, "Holiday": 2, "On leave": 3}


def leave_on(db: Session, engineer_ids: Iterable[int], day: date) -> dict[int, bool]:
    """Engineers with approved leave on that day, and whether it's only half the day."""
    rows = db.execute(
        select(LeaveRequest.employee_id, LeaveRequest.is_half_day).where(
            LeaveRequest.employee_id.in_(sorted(set(engineer_ids))),
            LeaveRequest.status == "Approved",
            LeaveRequest.is_active,
            LeaveRequest.from_date <= day,
            LeaveRequest.to_date >= day,
        )
    )
    found: dict[int, bool] = {}
    for employee_id, half_day in rows:
        found[employee_id] = found.get(employee_id, True) and half_day
    return found


def _holiday_branches(db: Session, day: date) -> tuple[bool, set[int]]:
    """(a holiday for every branch, the branches with one of their own)."""
    branches = list(db.scalars(select(Holiday.branch_id).where(Holiday.holiday_date == day, Holiday.is_active)))
    return None in branches, {branch for branch in branches if branch is not None}


def _calls_on(db: Session, engineer_ids: list[int], day: date) -> dict[int, int]:
    start = datetime.combine(day, time.min)
    rows = db.execute(
        select(ServiceVisit.engineer_employee_id, func.count(ServiceVisit.service_call_id.distinct()))
        .join(ServiceCall, ServiceCall.id == ServiceVisit.service_call_id)
        .where(
            ServiceVisit.engineer_employee_id.in_(engineer_ids),
            ServiceVisit.is_active,
            ServiceVisit.status != "Cancelled",
            ServiceCall.is_active,
            ServiceCall.current_status != "Cancelled",
            or_(
                ServiceVisit.planned_date == day,
                and_(
                    ServiceVisit.planned_date.is_(None),
                    ServiceVisit.created_at >= start,
                    ServiceVisit.created_at < start + timedelta(days=1),
                ),
            ),
        )
        .group_by(ServiceVisit.engineer_employee_id)
    )
    return {engineer: count for engineer, count in rows.tuples()}


def _open_calls(db: Session, engineer_ids: list[int]) -> Counter[int]:
    still_open = and_(ServiceCall.is_active, ServiceCall.current_status.notin_(sorted(FINISHED_STATUSES)))
    counts: Counter[int] = Counter()
    # Read each result before the next query: SQL Server keeps one open result per connection.
    rows = list(
        db.execute(
            select(ServiceCall.assigned_engineer_id, func.count())
            .where(ServiceCall.assigned_engineer_id.in_(engineer_ids), still_open)
            .group_by(ServiceCall.assigned_engineer_id)
        )
    )
    rows += db.execute(
        select(CallAssignment.engineer_employee_id, func.count())
        .join(ServiceCall, ServiceCall.id == CallAssignment.service_call_id)
        .where(
            CallAssignment.engineer_employee_id.in_(engineer_ids),
            CallAssignment.assignment_type == "Support",
            CallAssignment.is_current,
            CallAssignment.is_active,
            still_open,
        )
        .group_by(CallAssignment.engineer_employee_id)
    ).all()
    for engineer, count in rows:
        if engineer is not None:
            counts[engineer] += count
    return counts


def _last_positions(db: Session, engineer_ids: list[int]) -> dict[int, tuple[float, float]]:
    """Where each engineer last started a trip: the newest visit with a position."""
    latest = (
        select(func.max(ServiceVisit.id))
        .where(ServiceVisit.engineer_employee_id.in_(engineer_ids), ServiceVisit.site_latitude.is_not(None))
        .group_by(ServiceVisit.engineer_employee_id)
    )
    rows = db.execute(
        select(ServiceVisit.engineer_employee_id, ServiceVisit.site_latitude, ServiceVisit.site_longitude).where(
            ServiceVisit.id.in_(latest)
        )
    )
    return {
        engineer: (float(latitude), float(longitude))
        for engineer, latitude, longitude in rows.tuples()
        if latitude is not None and longitude is not None
    }


def _site_position(db: Session, call: ServiceCall) -> tuple[float, float] | None:
    site_id = call.customer_site_id
    if site_id is None and call.machine_unit_id is not None:
        site_id = db.scalar(select(MachineUnit.customer_site_id).where(MachineUnit.id == call.machine_unit_id))
    site = db.get(CustomerSite, site_id) if site_id is not None else None
    if site is None or site.latitude is None or site.longitude is None:
        return None
    return float(site.latitude), float(site.longitude)


def engineer_workload(
    db: Session, scope: RequestScope, query: EngineerWorkloadQuery, visibility: CallVisibility
) -> list[EngineerWorkload]:
    call = None
    if query.call_id is not None:
        call = db.get(ServiceCall, query.call_id)
        if call is None or not call.is_active or not visibility.allows(assignees(db, call)):
            raise NotFound("Service call not found.")

    engineers = list(
        db.execute(
            ServiceCallRepository.engineers_statement(scope, visibility)
            .add_columns(Branch.id.label("branch_id"), Branch.name.label("branch_name"))
            .outerjoin(Branch, Branch.id == ServiceCallRepository.engineer_branch())
        ).mappings()
    )
    ids = [row["id"] for row in engineers]
    if not ids:
        return []

    leave = leave_on(db, ids, query.on_date)
    everywhere, holiday_branches = _holiday_branches(db, query.on_date)
    on_date = _calls_on(db, ids, query.on_date)
    open_calls = _open_calls(db, ids)
    site = _site_position(db, call) if call is not None else None
    positions = _last_positions(db, ids) if site is not None else {}

    def availability(engineer_id: int, branch_id: int) -> Availability:
        if engineer_id in leave:
            return "Half-day leave" if leave[engineer_id] else "On leave"
        return "Holiday" if everywhere or branch_id in holiday_branches else "Available"

    workload = [
        EngineerWorkload(
            id=row["id"],
            name=row["name"],
            employee_code=row["employee_code"],
            branch_name=row["branch_name"],
            availability=availability(row["id"], row["branch_id"]),
            calls_on_date=on_date.get(row["id"], 0),
            open_calls=open_calls[row["id"]],
            distance_km=(
                round(haversine_km(positions[row["id"]], site), 1)
                if site is not None and row["id"] in positions
                else None
            ),
            same_branch=call is not None and call.branch_id == row["branch_id"],
        )
        for row in engineers
    ]
    workload.sort(
        key=lambda e: (
            _AVAILABILITY_ORDER[e.availability],
            not e.same_branch,
            e.calls_on_date,
            e.distance_km is None,
            e.distance_km or 0,
            e.open_calls,
            e.name,
        )
    )
    return workload
