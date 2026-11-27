"""Reads employees, punches, leave, holidays and shift assignments for daily attendance."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from trishul_api.modules.hr.attendance.payload import decode_reason
from trishul_api.modules.hr.attendance.policy import ATTENDANCE_PUNCH_STATUS, OfficialVisit
from trishul_api.db.models import (
    Attendance,
    AttendancePunch,
    AttendanceRegularization,
    TrkTrip,
    BiometricDevice,
    BiometricPunchLog,
    Branch,
    Department,
    Designation,
    Employee,
    EmployeeShift,
    Holiday,
    LeaveRequest,
    Shift,
    WorkLocation,
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
    half_day_hours: float | None = None


@dataclass(frozen=True, slots=True)
class PunchLocation:
    """Where a mobile face punch was made (biometric punches have none: the device is the place)."""

    latitude: float
    longitude: float
    accuracy_m: float | None
    place: str | None
    """The nearest work location of the employee's policy, if any."""
    inside_office: bool | None
    distance_m: float | None
    fake_gps: bool


@dataclass(frozen=True, slots=True)
class PunchSource:
    employee_id: int
    punched_at: datetime
    punch_type: str | None
    device_name: str | None
    location: PunchLocation | None = None


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

    def punches_between(
        self,
        start: datetime,
        end: datetime,
        *,
        employee_ids: Collection[int] | None = None,
    ) -> list[PunchSource]:
        """Load punches in [start, end]. Optionally restrict to specific employees (ESS mine)."""
        stmt = (
            select(
                BiometricPunchLog.employee_id,
                BiometricPunchLog.punched_at,
                BiometricPunchLog.punch_type,
                BiometricDevice.name,
            )
            .outerjoin(BiometricDevice, BiometricDevice.id == BiometricPunchLog.device_id)
            .where(BiometricPunchLog.is_active == True)  # noqa: E712
            .where(BiometricPunchLog.employee_id.is_not(None))
            # Demo/sample punches must never affect production attendance.
            .where(BiometricPunchLog.source != "Demo")
            .where(BiometricPunchLog.punched_at >= start)
            .where(BiometricPunchLog.punched_at <= end)
        )
        if employee_ids is not None:
            wanted = list(employee_ids)
            if not wanted:
                return []
            stmt = stmt.where(BiometricPunchLog.employee_id.in_(wanted))
        rows = self._db.execute(
            stmt.order_by(BiometricPunchLog.punched_at, BiometricPunchLog.id)
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
            select(
                AttendancePunch.employee_id,
                AttendancePunch.effective_at,
                AttendancePunch.punch_type,
                AttendancePunch.latitude,
                AttendancePunch.longitude,
                AttendancePunch.gps_accuracy_m,
                WorkLocation.name,
                AttendancePunch.inside_geofence,
                AttendancePunch.distance_m,
                AttendancePunch.is_mock_location,
            )
            .outerjoin(WorkLocation, WorkLocation.id == AttendancePunch.work_location_id)
            .where(AttendancePunch.is_active == True)  # noqa: E712
            # Present only. Rejected and Pending punches stay in the table and are not attendance.
            .where(AttendancePunch.status == ATTENDANCE_PUNCH_STATUS)
            .where(AttendancePunch.effective_at >= start - _IST_OFFSET)
            .where(AttendancePunch.effective_at <= end - _IST_OFFSET)
        ).all()
        return [
            PunchSource(
                employee_id=int(row[0]),
                punched_at=row[1] + _IST_OFFSET,
                punch_type=str(row[2]).upper(),
                device_name="Mobile app (face)",
                location=PunchLocation(
                    latitude=float(row[3]),
                    longitude=float(row[4]),
                    accuracy_m=float(row[5]) if row[5] is not None else None,
                    place=row[6],
                    inside_office=row[7],
                    distance_m=float(row[8]) if row[8] is not None else None,
                    fake_gps=bool(row[9]),
                )
                if row[3] is not None and row[4] is not None
                else None,
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

    def regularized_statuses(self, start: date, end: date) -> dict[tuple[int, date], str]:
        """Stored hr.attendance.status for days HR already resolved."""
        rows = self._db.execute(
            select(Attendance.employee_id, Attendance.attendance_date, Attendance.status)
            .where(Attendance.is_active == True)  # noqa: E712
            .where(Attendance.is_regularized == True)  # noqa: E712
            .where(Attendance.attendance_date >= start)
            .where(Attendance.attendance_date <= end)
        ).all()
        return {(int(employee_id), day): str(status) for employee_id, day, status in rows}

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

    def reporting_manager_id(self, employee_id: int) -> int | None:
        return self._db.scalar(select(Employee.reporting_manager_id).where(Employee.id == employee_id))

    def app_user_id_for_employee(self, employee_id: int) -> int | None:
        from trishul_api.db.models import AppUser

        return self._db.scalar(
            select(AppUser.id)
            .where(AppUser.employee_id == employee_id)
            .where(AppUser.is_active == True)  # noqa: E712
            .order_by(AppUser.id)
        )

    def designation_names(self, employee_ids: Collection[int]) -> dict[int, str]:
        wanted = list(employee_ids)
        if not wanted:
            return {}
        rows = self._db.execute(
            select(Employee.id, Designation.name)
            .outerjoin(Designation, Designation.id == Employee.designation_id)
            .where(Employee.id.in_(wanted))
        ).all()
        return {int(row[0]): (row[1] or "—") for row in rows}

    def list_regularizations(
        self,
        *,
        start: date,
        end: date,
        employee_id: int | None = None,
        manager_employee_id: int | None = None,
    ) -> list[tuple[AttendanceRegularization, EmployeeDaySource, Attendance | None]]:
        """Active regularization requests with employee master + linked attendance."""
        manager = aliased(Employee)
        emp_name = func.nullif(
            func.ltrim(func.rtrim(func.concat(manager.first_name, " ", func.coalesce(manager.last_name, "")))),
            "",
        )
        stmt = (
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
        )
        if employee_id is not None:
            stmt = stmt.where(AttendanceRegularization.employee_id == employee_id)
        if manager_employee_id is not None:
            stmt = stmt.where(Employee.reporting_manager_id == manager_employee_id)
        rows = self._db.execute(
            stmt.order_by(Attendance.attendance_date.desc(), AttendanceRegularization.id.desc())
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

    def upsert_computed_day(
        self,
        *,
        employee_id: int,
        day: date,
        shift_id: int | None,
        check_in: datetime | None,
        check_out: datetime | None,
        worked_hours: Decimal | None,
        status: str,
        source: str,
        actor_id: int | None,
    ) -> bool:
        """Insert or update a computed day. Skips rows already regularized. Does not commit."""
        existing = self.get_attendance(employee_id, day)
        if existing is not None:
            if existing.is_regularized:
                return False
            existing.shift_id = shift_id
            existing.check_in_at = check_in
            existing.check_out_at = check_out
            existing.worked_hours = worked_hours
            existing.status = status  # type: ignore[assignment]
            existing.source = source  # type: ignore[assignment]
            existing.updated_at = datetime.utcnow()
            existing.updated_by_user_id = actor_id
            existing.is_active = True
            self._db.add(existing)
            return True
        row = Attendance(
            employee_id=employee_id,
            attendance_date=day,
            shift_id=shift_id,
            check_in_at=check_in,
            check_out_at=check_out,
            source=source,  # type: ignore[arg-type]
            worked_hours=worked_hours,
            status=status,  # type: ignore[arg-type]
            is_regularized=False,
            created_at=datetime.utcnow(),
            created_by_user_id=actor_id,
            is_active=True,
        )
        self._db.add(row)
        return True

    def flush(self) -> None:
        self._db.flush()

    def official_visits_on(self, day: date) -> dict[int, list[OfficialVisit]]:
        """Departure and return from the app trip register and approved regularizations.

        Trip timestamps are UTC. Regularization times are the clock times HR entered.
        """
        visits: dict[int, list[OfficialVisit]] = {}
        start = datetime.combine(day, time.min) - _IST_OFFSET
        end = datetime.combine(day, time.max) - _IST_OFFSET
        trips = self._db.execute(
            select(TrkTrip.employee_id, TrkTrip.start_at, TrkTrip.end_at)
            .where(TrkTrip.is_active == True)  # noqa: E712
            .where(TrkTrip.start_at >= start)
            .where(TrkTrip.start_at <= end)
        ).all()
        for employee_id, started, ended in trips:
            departed = started + _IST_OFFSET
            returned = ended + _IST_OFFSET if ended is not None else None
            visits.setdefault(int(employee_id), []).append(OfficialVisit(departed, returned))

        self._add_regularization_visits(visits, self.list_regularizations(start=day, end=day))
        return visits

    def official_visits_between(
        self, start: date, end: date
    ) -> dict[date, dict[int, list[OfficialVisit]]]:
        """One trip query and one regularization query for the whole range.

        Same rules as ``official_visits_on``, grouped by attendance date so a month
        view does not repeat those queries for every day.
        """
        by_day: dict[date, dict[int, list[OfficialVisit]]] = {}
        window_start = datetime.combine(start, time.min) - _IST_OFFSET
        window_end = datetime.combine(end, time.max) - _IST_OFFSET
        trips = self._db.execute(
            select(TrkTrip.employee_id, TrkTrip.start_at, TrkTrip.end_at)
            .where(TrkTrip.is_active == True)  # noqa: E712
            .where(TrkTrip.start_at >= window_start)
            .where(TrkTrip.start_at <= window_end)
        ).all()
        for employee_id, started, ended in trips:
            if started is None or employee_id is None:
                continue
            departed = started + _IST_OFFSET
            returned = ended + _IST_OFFSET if ended is not None else None
            day_visits = by_day.setdefault(departed.date(), {})
            day_visits.setdefault(int(employee_id), []).append(OfficialVisit(departed, returned))
        flat: dict[int, list[OfficialVisit]] = {}
        self._add_regularization_visits(flat, self.list_regularizations(start=start, end=end), by_day)
        return by_day

    @staticmethod
    def _add_regularization_visits(
        visits: dict[int, list[OfficialVisit]],
        regs: list[tuple[AttendanceRegularization, EmployeeDaySource, Attendance | None]],
        by_day: dict[date, dict[int, list[OfficialVisit]]] | None = None,
    ) -> None:
        for reg, employee, attendance in regs:
            if reg.status != "Approved" or attendance is None:
                continue
            day = attendance.attendance_date
            _kind, requested_in, requested_out, _reason, _rejection = decode_reason(reg.reason)
            left = _clock(day, requested_out)
            back = _clock(day, requested_in)
            if left is None or back is None or back <= left:
                continue
            # A mid-day window is an official outing. A full-day correction is not.
            if left.time() <= time(9, 30) and back.time() >= time(17, 30):
                continue
            target = visits if by_day is None else by_day.setdefault(day, {})
            target.setdefault(employee.id, []).append(OfficialVisit(left, back))


def _clock(day: date, value: str | None) -> datetime | None:
    if not value:
        return None
    text = " ".join(str(value).upper().replace(".", "").split())
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.combine(day, datetime.strptime(text, fmt).time())
        except ValueError:
            continue
    return None


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
    """Use the employee's shift, or the office day 09:30–17:30 for every branch."""
    if assignment is not None:
        shift = shifts.get(assignment.shift_id)
        if shift is not None:
            half = float(shift.half_day_hours) if shift.half_day_hours is not None else None
            return ShiftAssignment(
                shift_id=shift.id,
                shift_name=shift.name,
                start_time=shift.start_time,
                end_time=shift.end_time,
                grace_minutes=int(shift.grace_minutes or 0),
                weekly_off_days=assignment.weekly_off_days,
                half_day_hours=half,
            )
        return ShiftAssignment(
            shift_id=assignment.shift_id,
            shift_name="General",
            start_time=time(9, 30),
            end_time=time(17, 30),
            grace_minutes=15,
            weekly_off_days=assignment.weekly_off_days,
            half_day_hours=3.75,
        )
    return ShiftAssignment(
        shift_id=None,
        shift_name="General",
        start_time=time(9, 30),
        end_time=time(17, 30),
        grace_minutes=15,
        weekly_off_days="SUN",
        half_day_hours=3.75,
    )
