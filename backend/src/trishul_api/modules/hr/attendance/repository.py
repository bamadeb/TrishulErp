"""Reads employees, punches, leave, holidays and shift assignments for daily attendance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from trishul_api.db.models import (
    Attendance,
    AttendancePunch,
    AttendanceRegularization,
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
_IST_OFFSET = timedelta(hours=5, minutes=30)


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
    employment_status: str = "Active"


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
        return self.list_employees(employment_status="Active")

    def list_employees(self, *, employment_status: str | None = "Active") -> list[EmployeeDaySource]:
        """Employee master rows for attendance screens.

        employment_status:
          - "Active" / "Inactive": filter by core.employee.status (inactive also allows is_active=0)
          - None: include Active and Inactive
        """
        manager = aliased(Employee)
        emp_name = func.nullif(
            func.ltrim(func.rtrim(func.concat(manager.first_name, " ", func.coalesce(manager.last_name, "")))),
            "",
        )
        stmt = (
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
                Employee.status,
                Employee.is_active,
            )
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(Branch, Branch.id == Employee.branch_id)
            .outerjoin(manager, manager.id == Employee.reporting_manager_id)
            .order_by(Employee.employee_code)
        )
        if employment_status == "Active":
            stmt = stmt.where(Employee.is_active == True).where(  # noqa: E712
                or_(Employee.status == "Active", Employee.status.is_(None))
            )
        elif employment_status == "Inactive":
            stmt = stmt.where(
                or_(Employee.is_active == False, Employee.status == "Inactive")  # noqa: E712
            )
        else:
            stmt = stmt.where(
                or_(
                    Employee.is_active == True,  # noqa: E712
                    Employee.status.in_(("Active", "Inactive")),
                    Employee.status.is_(None),
                )
            )
        rows = self._db.execute(stmt).all()
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
                employment_status=_employment_status(row[10], row[11]),
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
        biometric = [
            PunchSource(
                employee_id=int(row[0]),
                punched_at=row[1],
                punch_type=row[2],
                device_name=row[3],
            )
            for row in rows
            if row[0] is not None
        ]
        return sorted(biometric + self._face_punches_between(start, end), key=lambda p: p.punched_at)

    def _face_punches_between(self, start: datetime, end: datetime) -> list[PunchSource]:
        """Accepted mobile face punches (hr.attendance_punch, status Present) in the same terms as biometric
        punches: punched_at is Indian clock time, as the shift and day comparisons here expect, while
        attendance_punch.effective_at holds UTC."""
        rows = self._db.execute(
            select(AttendancePunch.employee_id, AttendancePunch.effective_at, AttendancePunch.punch_type)
            .where(AttendancePunch.is_active == True)  # noqa: E712
            .where(AttendancePunch.status == "Present")
            .where(AttendancePunch.effective_at >= start - _IST_OFFSET)
            .where(AttendancePunch.effective_at <= end - _IST_OFFSET)
        ).all()
        return [
            PunchSource(
                employee_id=int(row[0]),
                punched_at=row[1] + _IST_OFFSET,
                punch_type=str(row[2]).upper(),
                device_name="Mobile app (face)",
            )
            for row in rows
        ]

    def approved_leave_for_date(self, day: date) -> dict[int, LeaveCover]:
        return self.approved_leave_covering_range(day, day).get(day, {})

    def approved_leave_covering_range(self, start: date, end: date) -> dict[date, dict[int, LeaveCover]]:
        """One query for all approved leave overlapping [start, end], indexed by each covered day."""
        rows = self._db.execute(
            select(
                LeaveRequest.employee_id,
                LeaveRequest.is_half_day,
                LeaveRequest.from_date,
                LeaveRequest.to_date,
            )
            .where(LeaveRequest.is_active == True)  # noqa: E712
            .where(LeaveRequest.status == "Approved")
            .where(LeaveRequest.from_date <= end)
            .where(LeaveRequest.to_date >= start)
        ).all()
        by_day: dict[date, dict[int, LeaveCover]] = {}
        cursor = start
        while cursor <= end:
            by_day[cursor] = {}
            cursor = date.fromordinal(cursor.toordinal() + 1)
        for employee_id, is_half_day, from_date, to_date in rows:
            cover = LeaveCover(employee_id=int(employee_id), is_half_day=bool(is_half_day))
            day = max(start, from_date)
            last = min(end, to_date)
            while day <= last:
                by_day.setdefault(day, {})[cover.employee_id] = cover
                day = date.fromordinal(day.toordinal() + 1)
        return by_day

    def holidays_on(self, day: date) -> list[HolidayCover]:
        return self.holidays_between(day, day).get(day, [])

    def holidays_between(self, start: date, end: date) -> dict[date, list[HolidayCover]]:
        """One query for non-optional holidays in [start, end]."""
        state_col = Holiday.__table__.c.state_id
        rows = self._db.execute(
            select(Holiday.holiday_date, Holiday.name, Holiday.holiday_type, Holiday.branch_id, state_col)
            .where(Holiday.is_active == True)  # noqa: E712
            .where(Holiday.holiday_date >= start)
            .where(Holiday.holiday_date <= end)
            .where(Holiday.holiday_type != "Optional")
        ).all()
        by_day: dict[date, list[HolidayCover]] = {}
        for row in rows:
            item = HolidayCover(
                holiday_date=row[0],
                name=row[1],
                holiday_type=row[2],
                branch_id=row[3],
                state_id=row[4],
            )
            by_day.setdefault(item.holiday_date, []).append(item)
        return by_day

    def employee_shifts_overlapping(self, start: date, end: date) -> list[EmployeeShift]:
        """All active assignments that could apply on any day in [start, end]."""
        return list(
            self._db.scalars(
                select(EmployeeShift)
                .where(EmployeeShift.is_active == True)  # noqa: E712
                .where(EmployeeShift.from_date <= end)
                .where(or_(EmployeeShift.to_date.is_(None), EmployeeShift.to_date >= start))
                .order_by(EmployeeShift.from_date.desc(), EmployeeShift.id.desc())
            ).all()
        )

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

    def regularized_employee_dates(self, start: date, end: date) -> set[tuple[int, date]]:
        """Employee/date pairs marked regularized on hr.attendance (Resolved exceptions)."""
        rows = self._db.execute(
            select(Attendance.employee_id, Attendance.attendance_date)
            .where(Attendance.is_active == True)  # noqa: E712
            .where(Attendance.is_regularized == True)  # noqa: E712
            .where(Attendance.attendance_date >= start)
            .where(Attendance.attendance_date <= end)
        ).all()
        return {(int(employee_id), day) for employee_id, day in rows}

    def get_attendance(self, employee_id: int, day: date) -> Attendance | None:
        return self._db.scalar(
            select(Attendance)
            .where(Attendance.is_active == True)  # noqa: E712
            .where(Attendance.employee_id == employee_id)
            .where(Attendance.attendance_date == day)
            .order_by(Attendance.id.desc())
            .limit(1)
        )

    def get_attendance_by_id(self, attendance_id: int) -> Attendance | None:
        return self._db.scalar(
            select(Attendance)
            .where(Attendance.id == attendance_id)
            .where(Attendance.is_active == True)  # noqa: E712
        )

    def mark_regularized(self, row: Attendance) -> Attendance:
        row.is_regularized = True
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def list_regularizations(
        self,
        *,
        start: date,
        end: date,
    ) -> list[tuple[AttendanceRegularization, EmployeeDaySource, Attendance | None]]:
        """Active regularization requests with employee master + linked attendance."""
        manager = aliased(Employee)
        emp_name = func.nullif(
            func.ltrim(func.rtrim(func.concat(manager.first_name, " ", func.coalesce(manager.last_name, "")))),
            "",
        )
        rows = self._db.execute(
            select(
                AttendanceRegularization,
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
                Employee.status,
                Employee.is_active,
                Attendance,
            )
            .join(Employee, Employee.id == AttendanceRegularization.employee_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(Branch, Branch.id == Employee.branch_id)
            .outerjoin(manager, manager.id == Employee.reporting_manager_id)
            .join(Attendance, Attendance.id == AttendanceRegularization.attendance_id)
            .where(AttendanceRegularization.is_active == True)  # noqa: E712
            .where(Attendance.attendance_date >= start)
            .where(Attendance.attendance_date <= end)
            .order_by(Attendance.attendance_date.desc(), AttendanceRegularization.id.desc())
        ).all()
        result: list[tuple[AttendanceRegularization, EmployeeDaySource, Attendance | None]] = []
        for row in rows:
            reg: AttendanceRegularization = row[0]
            employee = EmployeeDaySource(
                id=row[1],
                employee_code=row[2],
                first_name=row[3],
                last_name=row[4],
                employee_type=row[5],
                department_name=row[6],
                branch_id=row[7],
                branch_name=row[8],
                branch_state_id=row[9],
                reporting_manager_name=row[10],
                employment_status=_employment_status(row[11], row[12]),
            )
            attendance: Attendance | None = row[13]
            result.append((reg, employee, attendance))
        return result

    def get_regularization(self, regularization_id: int) -> AttendanceRegularization | None:
        return self._db.scalar(
            select(AttendanceRegularization)
            .where(AttendanceRegularization.id == regularization_id)
            .where(AttendanceRegularization.is_active == True)  # noqa: E712
        )

    def ensure_attendance(
        self,
        *,
        employee_id: int,
        day: date,
        check_in: datetime | None,
        check_out: datetime | None,
        actor_id: int | None,
    ) -> Attendance:
        existing = self.get_attendance(employee_id, day)
        if existing is not None:
            return existing
        row = Attendance(
            employee_id=employee_id,
            attendance_date=day,
            shift_id=None,
            check_in_at=check_in,
            check_out_at=check_out,
            source="Manual",
            worked_hours=None,
            status="Present",
            is_regularized=False,
            created_at=datetime.utcnow(),
            created_by_user_id=actor_id,
            is_active=True,
        )
        self._db.add(row)
        self._db.flush()
        return row

    def create_regularization(self, row: AttendanceRegularization) -> AttendanceRegularization:
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def save_regularization(self, row: AttendanceRegularization) -> AttendanceRegularization:
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def save_attendance(self, row: Attendance) -> Attendance:
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row


def _employment_status(status: str | None, is_active: bool | None) -> str:
    if status == "Inactive" or is_active is False:
        return "Inactive"
    return "Active"


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
