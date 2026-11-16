"""Explicit assignment, attendance classification, and a read-only entitlement preview.

Saving a policy does not call these operations and does not write balances.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.db.models import (
    Attendance,
    Employee,
    LeaveAttendanceClass,
    LeavePolicy,
    LeavePolicyAssignment,
    LeavePolicyLine,
    LeaveWeeklyRestGrant,
)
from trishul_api.modules.hr.leave.calculation import add_calendar_months, earned_leave_days, joining_threshold
from trishul_api.modules.hr.leave.schemas import (
    AttendanceClassItem,
    AttendanceClassWrite,
    EntitlementPreview,
    EntitlementPreviewQuery,
    LeaveAssignmentItem,
    LeaveAssignmentWrite,
    WeeklyRestGrantItem,
    WeeklyRestGrantWrite,
)

ATTENDANCE_STATUSES = ("Present", "Absent", "Half day", "Leave", "Holiday", "Week off", "On duty")
_ZERO = Decimal("0.0")
_OPEN = date(9999, 12, 31)


def assignments(db: Session, policy_id: int) -> list[LeaveAssignmentItem]:
    _policy(db, policy_id)
    rows = db.execute(
        select(LeavePolicyAssignment, Employee)
        .join(Employee, Employee.id == LeavePolicyAssignment.employee_id)
        .where(LeavePolicyAssignment.leave_policy_id == policy_id, LeavePolicyAssignment.is_active == True)  # noqa: E712
        .order_by(Employee.employee_code)
    ).all()
    return [
        LeaveAssignmentItem(
            id=assignment.id,
            leave_policy_id=assignment.leave_policy_id,
            employee_id=employee.id,
            employee_code=employee.employee_code,
            employee_name=f"{employee.first_name} {employee.last_name}".strip(),
            effective_from=assignment.effective_from,
            effective_to=assignment.effective_to,
            is_active=assignment.is_active,
        )
        for assignment, employee in rows
    ]


def assign(db: Session, actor: CurrentUser, policy_id: int, data: LeaveAssignmentWrite) -> LeaveAssignmentItem:
    policy = _policy(db, policy_id)
    if not policy.is_active:
        raise ApiError("An inactive policy cannot be assigned or create balances.")
    employee = _employee(db, actor, data.employee_id)
    current = db.scalars(
        select(LeavePolicyAssignment).where(
            LeavePolicyAssignment.leave_policy_id == policy_id,
            LeavePolicyAssignment.employee_id == employee.id,
            LeavePolicyAssignment.is_active == True,  # noqa: E712
        )
    ).all()
    for row in current:
        if _overlaps(row.effective_from, row.effective_to, data.effective_from, data.effective_to):
            raise AlreadyExists("This employee already has an overlapping assignment for this policy.")
    created = LeavePolicyAssignment(
        leave_policy_id=policy_id,
        employee_id=employee.id,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        created_by_user_id=actor.id,
    )
    db.add(created)
    db.commit()
    db.refresh(created)
    return _one(db, created.id)


def attendance_classes(db: Session) -> list[AttendanceClassItem]:
    stored = {row.attendance_status: row for row in db.scalars(select(LeaveAttendanceClass)).all()}
    items: list[AttendanceClassItem] = []
    for status in ATTENDANCE_STATUSES:
        row = stored.get(status)
        items.append(
            AttendanceClassItem(
                attendance_status=status,  # type: ignore[arg-type]
                counts_for_eligibility=False if row is None else row.counts_for_eligibility,
                counts_as_days_worked=False if row is None else row.counts_as_days_worked,
                is_deemed_work=False if row is None else row.is_deemed_work,
                day_weight=None if row is None else row.day_weight,
                configured=row is not None,
            )
        )
    return items


def save_attendance_classes(
    db: Session, actor: CurrentUser, rows: list[AttendanceClassWrite]
) -> list[AttendanceClassItem]:
    statuses = [row.attendance_status for row in rows]
    if len(statuses) != len(set(statuses)):
        raise ApiError("Each attendance status can be classified once.")
    existing = {row.attendance_status: row for row in db.scalars(select(LeaveAttendanceClass)).all()}
    keep = set(statuses)
    for status, stored in existing.items():
        if status not in keep:
            db.delete(stored)
    for row in rows:
        stored = existing.get(row.attendance_status)
        if stored is None:
            db.add(
                LeaveAttendanceClass(
                    attendance_status=row.attendance_status,
                    counts_for_eligibility=row.counts_for_eligibility,
                    counts_as_days_worked=row.counts_as_days_worked,
                    is_deemed_work=row.is_deemed_work,
                    day_weight=row.day_weight,
                    created_by_user_id=actor.id,
                )
            )
            continue
        stored.counts_for_eligibility = row.counts_for_eligibility
        stored.counts_as_days_worked = row.counts_as_days_worked
        stored.is_deemed_work = row.is_deemed_work
        stored.day_weight = row.day_weight
        stored.updated_by_user_id = actor.id
    db.commit()
    return attendance_classes(db)


def preview_entitlement(
    db: Session, actor: CurrentUser, policy_id: int, query: EntitlementPreviewQuery
) -> EntitlementPreview:
    policy = _policy(db, policy_id)
    if not policy.is_active:
        raise ApiError("An inactive policy cannot calculate entitlements.")
    line = db.scalars(
        select(LeavePolicyLine).where(
            LeavePolicyLine.leave_policy_id == policy_id,
            LeavePolicyLine.is_active == True,  # noqa: E712
            LeavePolicyLine.calculation_method == "FORMULA",
        )
    ).first()
    if line is None or line.credit_days is None or line.qualifying_days_per_credit is None:
        raise ApiError("This policy has no formula entitlement to calculate.")
    if line.minimum_qualifying_days is None:
        raise ApiError("The formula entitlement has no eligibility minimum.")
    employee = _employee(db, actor, query.employee_id)
    start, end = _window(policy.year_basis, query.attendance_year)
    counts = db.execute(
        select(Attendance.status, func.count())
        .where(
            Attendance.employee_id == employee.id,
            Attendance.is_active == True,  # noqa: E712
            Attendance.attendance_date >= start,
            Attendance.attendance_date <= end,
        )
        .group_by(Attendance.status)
    ).all()
    mapped = {row.attendance_status: row for row in db.scalars(select(LeaveAttendanceClass)).all()}
    if not mapped:
        raise ApiError(
            "Attendance classification is not configured. Map each attendance status before Earned Leave "
            "can be calculated."
        )
    missing = [status for status, _count in counts if status not in mapped or mapped[status].day_weight is None]
    if missing:
        names = ", ".join(sorted(set(missing)))
        raise ApiError(
            "Attendance classification is incomplete. Map every status used in the year, including its day weight, "
            f"before Earned Leave can be calculated. Missing: {names}."
        )
    worked = _ZERO
    deemed = _ZERO
    eligibility = _ZERO
    for status, count in counts:
        weight = mapped[status].day_weight or _ZERO
        total = Decimal(count) * weight
        if mapped[status].counts_for_eligibility:
            eligibility += total
        if mapped[status].counts_as_days_worked:
            worked += total
        if mapped[status].is_deemed_work:
            deemed += total
    credited = earned_leave_days(
        eligibility_days=eligibility,
        days_worked=worked,
        credit_days=line.credit_days,
        per_days=line.qualifying_days_per_credit,
        minimum_qualifying_days=line.minimum_qualifying_days,
        joining=employee.date_of_joining,
        attendance_year=query.attendance_year,
        joining_rule=line.joining_year_rule,
    )
    threshold = line.minimum_qualifying_days
    if line.joining_year_rule == "TWO_THIRDS_REMAINDER":
        threshold = joining_threshold(employee.date_of_joining, query.attendance_year, threshold)
    return EntitlementPreview(
        attendance_year=query.attendance_year,
        available_in_year=query.attendance_year + 1,
        eligibility_days=eligibility,
        days_worked=worked,
        deemed_days=deemed,
        credited_days=credited,
        threshold=threshold,
    )


def grant_weekly_rest(
    db: Session, actor: CurrentUser, data: WeeklyRestGrantWrite
) -> WeeklyRestGrantItem:
    employee = _employee(db, actor, data.employee_id)
    line = db.get(LeavePolicyLine, data.leave_policy_line_id)
    if line is None or not line.is_active or line.compensatory_basis != "STATUTORY_WEEKLY_REST":
        raise NotFound("Statutory weekly-rest entitlement")
    if line.compensatory_expiry_months is None:
        raise ApiError("Statutory weekly rest needs an expiry counted in calendar months.")
    policy = db.get(LeavePolicy, line.leave_policy_id)
    if policy is None or not policy.is_active:
        raise ApiError("An inactive policy cannot grant compensatory leave.")
    duplicate = db.scalar(
        select(LeaveWeeklyRestGrant.id).where(
            LeaveWeeklyRestGrant.employee_id == employee.id,
            LeaveWeeklyRestGrant.original_holiday_date == data.original_holiday_date,
            LeaveWeeklyRestGrant.is_active == True,  # noqa: E712
        )
    )
    if duplicate is not None:
        raise AlreadyExists("This weekly holiday already has a compensatory grant.")
    expires_on = add_calendar_months(data.original_holiday_date, line.compensatory_expiry_months)
    created = LeaveWeeklyRestGrant(
        employee_id=employee.id,
        leave_policy_line_id=line.id,
        original_holiday_date=data.original_holiday_date,
        granted_on=data.granted_on,
        expires_on=expires_on,
        days=data.days,
        created_by_user_id=actor.id,
    )
    db.add(created)
    db.commit()
    db.refresh(created)
    return WeeklyRestGrantItem(
        id=created.id,
        employee_id=created.employee_id,
        leave_policy_line_id=created.leave_policy_line_id,
        original_holiday_date=created.original_holiday_date,
        granted_on=created.granted_on,
        expires_on=created.expires_on,
        days=created.days,
    )


def _policy(db: Session, policy_id: int) -> LeavePolicy:
    policy = db.get(LeavePolicy, policy_id)
    if policy is None:
        raise NotFound("Leave policy")
    return policy


def _employee(db: Session, actor: CurrentUser, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None or (actor.branch_ids is not None and employee.branch_id not in actor.branch_ids):
        raise NotFound("Employee")
    return employee


def _one(db: Session, assignment_id: int) -> LeaveAssignmentItem:
    row = db.execute(
        select(LeavePolicyAssignment, Employee)
        .join(Employee, Employee.id == LeavePolicyAssignment.employee_id)
        .where(LeavePolicyAssignment.id == assignment_id)
    ).one()
    assignment, employee = row
    return LeaveAssignmentItem(
        id=assignment.id,
        leave_policy_id=assignment.leave_policy_id,
        employee_id=employee.id,
        employee_code=employee.employee_code,
        employee_name=f"{employee.first_name} {employee.last_name}".strip(),
        effective_from=assignment.effective_from,
        effective_to=assignment.effective_to,
        is_active=assignment.is_active,
    )


def _overlaps(left_from: date, left_to: date | None, right_from: date, right_to: date | None) -> bool:
    return left_from <= (right_to or _OPEN) and right_from <= (left_to or _OPEN)


def _window(year_basis: str, year: int) -> tuple[date, date]:
    if year_basis == "CALENDAR":
        return date(year, 1, 1), date(year, 12, 31)
    return date(year, 4, 1), date(year + 1, 3, 31)
