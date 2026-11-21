"""Reads employees, punches, leave, holidays and shift assignments for daily attendance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from trishul_api.db.models import (
    BiometricDevice,
    BiometricPunchLog,
    Branch,
    Department,
    Employee,
    EmployeeShift,
    Holiday,
    LeaveRequest,
    Shift,
)

_WEEKDAY = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}


@dataclass(frozen=True, slots=True)
class EmployeeDaySource:
    id: int
    employee_code: str
    first_name: str | None
    last_name: str | None
    employee_type: str | None
    department_name: str | None
    branch_id: int | None
    branch_name: str | None
    branch_state_id: int | None
    reporting_manager_name: str | None


@dataclass(frozen=True, slots=True)
class ShiftAssignment:
    shift_id: int | None
    shift_name: str
    start_time: time
    end_time: time
    grace_minutes: int
    weekly_off_days: str | None


@dataclass(frozen=True, slots=True)
class PunchSource:
    employee_id: int
    punched_at: datetime
    punch_type: str | None
    device_name: str | None


@dataclass(frozen=True, slots=True)
class LeaveCover:
    employee_id: int
    is_half_day: bool


@dataclass(frozen=True, slots=True)
class HolidayCover:
    holiday_date: date
    name: str
    holiday_type: str
    branch_id: int | None
    state_id: int | None


class AttendanceRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_active_employees(self) -> list[EmployeeDaySource]:
        manager = aliased(Employee)
        emp_name = func.nullif(
            func.ltrim(func.rtrim(func.concat(manager.first_name, " ", func.coalesce(manager.last_name, "")))),
            "",
        )
        rows = self._db.execute(
            select(
                Employee.id,
                Employee.employee_code,
                Employee.first_name,
                Employee.last_name,
                Employee.employee_type,
                Department.name,
                Employee.branch_id,
                Branch.name,
                Branch.state_id,
                emp_name,
            )
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(Branch, Branch.id == Employee.branch_id)
            .outerjoin(manager, manager.id == Employee.reporting_manager_id)
            .where(Employee.is_active == True)  # noqa: E712
            .where(or_(Employee.status == "Active", Employee.status.is_(None)))
            .order_by(Employee.employee_code)
        ).all()
        return [
            EmployeeDaySource(
                id=row[0],
                employee_code=row[1],
                first_name=row[2],
                last_name=row[3],
                employee_type=row[4],
                department_name=row[5],
                branch_id=row[6],
                branch_name=row[7],
                branch_state_id=row[8],
                reporting_manager_name=row[9],
            )
            for row in rows
        ]

    def shifts_by_id(self) -> dict[int, Shift]:
        return {
            row.id: row
            for row in self._db.scalars(select(Shift).where(Shift.is_active == True)).all()  # noqa: E712
        }

    def employee_shifts_for_date(self, day: date) -> dict[int, EmployeeShift]:
        """Latest effective assignment per employee for the given date."""
        rows = self._db.scalars(
            select(EmployeeShift)
            .where(EmployeeShift.is_active == True)  # noqa: E712
            .where(EmployeeShift.from_date <= day)
            .where(or_(EmployeeShift.to_date.is_(None), EmployeeShift.to_date >= day))
            .order_by(EmployeeShift.from_date.desc(), EmployeeShift.id.desc())
        ).all()
        by_employee: dict[int, EmployeeShift] = {}
        for row in rows:
            if row.employee_id not in by_employee:
                by_employee[row.employee_id] = row
        return by_employee

    def punches_between(self, start: datetime, end: datetime) -> list[PunchSource]:
        rows = self._db.execute(
            select(
                BiometricPunchLog.employee_id,
                BiometricPunchLog.punched_at,
                BiometricPunchLog.punch_type,
                BiometricDevice.name,
            )
            .outerjoin(BiometricDevice, BiometricDevice.id == BiometricPunchLog.device_id)
            .where(BiometricPunchLog.is_active == True)  # noqa: E712
            .where(BiometricPunchLog.employee_id.is_not(None))
            .where(BiometricPunchLog.punched_at >= start)
            .where(BiometricPunchLog.punched_at <= end)
            .order_by(BiometricPunchLog.punched_at, BiometricPunchLog.id)
        ).all()
        return [
            PunchSource(
                employee_id=int(row[0]),
                punched_at=row[1],
                punch_type=row[2],
                device_name=row[3],
            )
            for row in rows
            if row[0] is not None
        ]

    def approved_leave_for_date(self, day: date) -> dict[int, LeaveCover]:
        rows = self._db.execute(
            select(LeaveRequest.employee_id, LeaveRequest.is_half_day)
            .where(LeaveRequest.is_active == True)  # noqa: E712
            .where(LeaveRequest.status == "Approved")
            .where(LeaveRequest.from_date <= day)
            .where(LeaveRequest.to_date >= day)
        ).all()
        return {int(row[0]): LeaveCover(employee_id=int(row[0]), is_half_day=bool(row[1])) for row in rows}

    def holidays_on(self, day: date) -> list[HolidayCover]:
        state_col = Holiday.__table__.c.state_id
        rows = self._db.execute(
            select(Holiday.holiday_date, Holiday.name, Holiday.holiday_type, Holiday.branch_id, state_col)
            .where(Holiday.is_active == True)  # noqa: E712
            .where(Holiday.holiday_date == day)
            .where(Holiday.holiday_type != "Optional")
        ).all()
        return [
            HolidayCover(
                holiday_date=row[0],
                name=row[1],
                holiday_type=row[2],
                branch_id=row[3],
                state_id=row[4],
            )
            for row in rows
        ]

    def holiday_applies(self, holiday: HolidayCover, branch_id: int | None, state_id: int | None) -> bool:
        if holiday.branch_id is not None:
            return holiday.branch_id == branch_id
        if holiday.state_id is None:
            return True
        return state_id == holiday.state_id

    def day_bounds(self, day: date) -> tuple[datetime, datetime]:
        start = datetime.combine(day, time.min)
        end = datetime.combine(day, time.max.replace(microsecond=0))
        return start, end


def off_weekdays(text: str | None) -> set[int]:
    if not text:
        return {6}
    days = {_WEEKDAY[part.strip().upper()] for part in text.split(",") if part.strip().upper() in _WEEKDAY}
    return days or {6}


def resolve_shift(
    assignment: EmployeeShift | None,
    shifts: dict[int, Shift],
) -> ShiftAssignment:
    """Use configured shift when present; otherwise General 09:00–18:00 with 10 minutes grace."""
    if assignment is not None:
        shift = shifts.get(assignment.shift_id)
        if shift is not None:
            return ShiftAssignment(
                shift_id=shift.id,
                shift_name=shift.name,
                start_time=shift.start_time,
                end_time=shift.end_time,
                grace_minutes=int(shift.grace_minutes or 0),
                weekly_off_days=assignment.weekly_off_days,
            )
        return ShiftAssignment(
            shift_id=assignment.shift_id,
            shift_name="General",
            start_time=time(9, 0),
            end_time=time(18, 0),
            grace_minutes=10,
            weekly_off_days=assignment.weekly_off_days,
        )
    return ShiftAssignment(
        shift_id=None,
        shift_name="General",
        start_time=time(9, 0),
        end_time=time(18, 0),
        grace_minutes=10,
        weekly_off_days="SUN",
    )
