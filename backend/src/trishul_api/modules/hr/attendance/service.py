"""Compute Daily Attendance for a calendar day from live HR data sources."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from trishul_api.modules.hr.attendance.repository import (
    AttendanceRepository,
    EmployeeDaySource,
    HolidayCover,
    LeaveCover,
    PunchSource,
    ShiftAssignment,
    off_weekdays,
    resolve_shift,
)
from trishul_api.modules.hr.attendance.schemas import (
    AttendanceDisplayStatus,
    AttendanceFilterOptionsOut,
    AttendanceHistoryOut,
    AttendancePunchOut,
    AttendanceSummaryOut,
    DailyAttendancePageOut,
    DailyAttendanceQuery,
    DailyAttendanceRowOut,
    StatusTab,
)

_STATUSES: list[AttendanceDisplayStatus] = [
    "Present",
    "Late",
    "Missing Punch",
    "Absent",
    "On Leave",
    "Off Day",
    "Holiday",
]


class AttendanceService:
    def __init__(self, db: Session) -> None:
        self._repo = AttendanceRepository(db)

    def list_daily(self, query: DailyAttendanceQuery) -> DailyAttendancePageOut:
        day = query.attendance_date
        employees = self._repo.list_active_employees()
        shifts = self._repo.shifts_by_id()
        assignments = self._repo.employee_shifts_for_date(day)
        holidays = self._repo.holidays_on(day)
        leaves = self._repo.approved_leave_for_date(day)
        start, end = self._repo.day_bounds(day)
        punches = self._repo.punches_between(start, end)
        punches_by_employee: dict[int, list[PunchSource]] = defaultdict(list)
        for punch in punches:
            punches_by_employee[punch.employee_id].append(punch)

        rows = [
            self._build_row(
                employee=employee,
                day=day,
                shift=resolve_shift(assignments.get(employee.id), shifts),
                holidays=holidays,
                leave=leaves.get(employee.id),
                punches=punches_by_employee.get(employee.id, []),
                history=[],
            )
            for employee in employees
        ]

        filter_options = self._filter_options(rows)
        summary = self._summary(rows)
        filtered = self._apply_filters(rows, query)
        total = len(filtered)
        page_size = query.page_size
        page = query.page
        start_idx = (page - 1) * page_size
        page_items = filtered[start_idx : start_idx + page_size]

        if page_items:
            employee_map = {e.id: e for e in employees}
            history_by_employee = self._history_for_employees(
                employees=employee_map,
                employee_ids=[row.employee_id for row in page_items],
                before=day,
                days=7,
                shifts=shifts,
            )
            page_items = [
                row.model_copy(update={"history": history_by_employee.get(row.employee_id, [])})
                for row in page_items
            ]

        return DailyAttendancePageOut(
            date=day,
            summary=summary,
            filter_options=filter_options,
            items=page_items,
            total=total,
            page=page,
            page_size=page_size,
        )

    def _build_row(
        self,
        *,
        employee: EmployeeDaySource,
        day: date,
        shift: ShiftAssignment,
        holidays: list[HolidayCover],
        leave: LeaveCover | None,
        punches: list[PunchSource],
        history: list[AttendanceHistoryOut],
    ) -> DailyAttendanceRowOut:
        name = " ".join(part for part in (employee.first_name, employee.last_name) if part).strip()
        if not name:
            name = employee.employee_code
        department = employee.department_name or "—"
        location = employee.branch_name or "—"
        employee_type = employee.employee_type or "Permanent"
        manager = employee.reporting_manager_name or "—"

        punch_outs = [self._punch_out(p) for p in punches]
        first_in, last_out, first_in_late, working_hours, status, remarks = self._evaluate(
            day=day,
            employee=employee,
            shift=shift,
            holidays=holidays,
            leave=leave,
            punches=punches,
        )

        return DailyAttendanceRowOut(
            id=employee.id,
            employee_id=employee.id,
            employee_code=employee.employee_code,
            employee_name=name,
            department=department,
            location=location,
            shift=shift.shift_name,
            employee_type=employee_type,
            reporting_manager=manager,
            first_in=first_in,
            last_out=last_out,
            first_in_late=first_in_late,
            working_hours=working_hours,
            status=status,
            remarks=remarks,
            punches=punch_outs,
            history=history,
        )

    def _evaluate(
        self,
        *,
        day: date,
        employee: EmployeeDaySource,
        shift: ShiftAssignment,
        holidays: list[HolidayCover],
        leave: LeaveCover | None,
        punches: list[PunchSource],
    ) -> tuple[datetime | None, datetime | None, bool, str | None, AttendanceDisplayStatus, str]:
        first_in, last_out, first_in_late, working_hours, punch_status, punch_remarks = self._from_punches(
            day, shift, punches
        )

        holiday = next(
            (
                h
                for h in holidays
                if self._repo.holiday_applies(h, employee.branch_id, employee.branch_state_id)
            ),
            None,
        )
        is_off = day.weekday() in off_weekdays(shift.weekly_off_days)

        # Priority: holiday / weekly off / approved leave, unless punches prove presence.
        if holiday is not None and not punches:
            return None, None, False, None, "Holiday", holiday.name
        if is_off and not punches:
            return None, None, False, None, "Off Day", "Weekly off"
        if leave is not None and not punches:
            note = "Half-day leave" if leave.is_half_day else "Approved leave"
            return None, None, False, None, "On Leave", note
        if leave is not None and punches and leave.is_half_day:
            # Half-day leave with punches still shows punch-derived presence.
            if punch_status in ("Present", "Late", "Missing Punch"):
                return first_in, last_out, first_in_late, working_hours, punch_status, "Half-day leave"
            return first_in, last_out, first_in_late, working_hours, "On Leave", "Half-day leave"
        if leave is not None and punches:
            # Full-day approved leave wins over incidental punches.
            return first_in, last_out, first_in_late, working_hours, "On Leave", "Approved leave"
        if holiday is not None and punches:
            return first_in, last_out, first_in_late, working_hours, punch_status, holiday.name
        if is_off and punches:
            return first_in, last_out, first_in_late, working_hours, punch_status, "Worked on weekly off"

        return first_in, last_out, first_in_late, working_hours, punch_status, punch_remarks

    def _from_punches(
        self,
        day: date,
        shift: ShiftAssignment,
        punches: list[PunchSource],
    ) -> tuple[datetime | None, datetime | None, bool, str | None, AttendanceDisplayStatus, str]:
        if not punches:
            return None, None, False, None, "Absent", ""

        ordered = sorted(punches, key=lambda p: (p.punched_at, p.punch_type or ""))
        ins = [p for p in ordered if (p.punch_type or "").upper() == "IN"]
        outs = [p for p in ordered if (p.punch_type or "").upper() == "OUT"]
        if not ins and not outs:
            # Untyped punches: treat earliest as in, latest as out.
            first_in = ordered[0].punched_at
            last_out = ordered[-1].punched_at if len(ordered) > 1 else None
        else:
            first_in = ins[0].punched_at if ins else ordered[0].punched_at
            last_out = outs[-1].punched_at if outs else None

        grace_deadline = datetime.combine(day, shift.start_time) + timedelta(minutes=shift.grace_minutes)
        first_in_late = first_in > grace_deadline
        working_hours = self._format_hours(self._worked_minutes(ordered))

        has_in = first_in is not None
        has_out = last_out is not None and last_out != first_in
        shift_ended = datetime.combine(day, shift.end_time)
        # Past days with IN and no OUT, or today after shift end → Missing Punch.
        if has_in and not has_out:
            status: AttendanceDisplayStatus = "Missing Punch"
            if day < date.today() or datetime.now() >= shift_ended:
                remarks = "Missing OUT punch"
            else:
                remarks = "Shift in progress / missing OUT"
            return first_in, None, first_in_late, working_hours, status, remarks
        if first_in_late:
            status = "Late"
            late_by = int((first_in - grace_deadline).total_seconds() // 60)
            remarks = f"Late by {late_by} min"
        else:
            status = "Present"
            remarks = ""

        return first_in, last_out, first_in_late, working_hours, status, remarks

    def _history_for_employees(
        self,
        *,
        employees: dict[int, EmployeeDaySource],
        employee_ids: list[int],
        before: date,
        days: int,
        shifts: dict,
    ) -> dict[int, list[AttendanceHistoryOut]]:
        if not employee_ids:
            return {}
        start_day = before - timedelta(days=days)
        end_day = before - timedelta(days=1)
        if end_day < start_day:
            return {}

        wanted = set(employee_ids)
        start_dt, _ = self._repo.day_bounds(start_day)
        _, end_dt = self._repo.day_bounds(end_day)
        punches = self._repo.punches_between(start_dt, end_dt)
        punches_by_day: dict[date, dict[int, list[PunchSource]]] = defaultdict(lambda: defaultdict(list))
        for punch in punches:
            if punch.employee_id not in wanted:
                continue
            punches_by_day[punch.punched_at.date()][punch.employee_id].append(punch)

        result: dict[int, list[AttendanceHistoryOut]] = {eid: [] for eid in employee_ids}
        cursor = end_day
        while cursor >= start_day:
            day_assignments = self._repo.employee_shifts_for_date(cursor)
            holidays = self._repo.holidays_on(cursor)
            leaves = self._repo.approved_leave_for_date(cursor)
            for employee_id in employee_ids:
                employee = employees.get(employee_id)
                if employee is None:
                    continue
                shift = resolve_shift(day_assignments.get(employee_id), shifts)
                first_in, last_out, _, working_hours, status, _ = self._evaluate(
                    day=cursor,
                    employee=employee,
                    shift=shift,
                    holidays=holidays,
                    leave=leaves.get(employee_id),
                    punches=punches_by_day[cursor].get(employee_id, []),
                )
                result[employee_id].append(
                    AttendanceHistoryOut(
                        date=cursor,
                        status=status,
                        first_in=first_in,
                        last_out=last_out,
                        working_hours=working_hours,
                    )
                )
            cursor -= timedelta(days=1)
        return result

    @staticmethod
    def _punch_out(punch: PunchSource) -> AttendancePunchOut:
        kind = (punch.punch_type or "").upper()
        if kind not in ("IN", "OUT"):
            kind = "IN"
        return AttendancePunchOut(
            kind=kind,  # type: ignore[arg-type]
            at=punch.punched_at,
            device=punch.device_name or "—",
        )

    @staticmethod
    def _worked_minutes(punches: list[PunchSource]) -> int:
        ordered = sorted(punches, key=lambda p: p.punched_at)
        typed = [(p.punched_at, (p.punch_type or "").upper()) for p in ordered]
        total = 0
        open_in: datetime | None = None
        for at, kind in typed:
            if kind == "IN":
                if open_in is None:
                    open_in = at
            elif kind == "OUT" and open_in is not None:
                total += max(0, int((at - open_in).total_seconds() // 60))
                open_in = None
        if total == 0 and len(ordered) >= 2:
            total = max(0, int((ordered[-1].punched_at - ordered[0].punched_at).total_seconds() // 60))
        return total

    @staticmethod
    def _format_hours(minutes: int) -> str | None:
        if minutes <= 0:
            return None
        hours, mins = divmod(minutes, 60)
        return f"{hours}h {mins:02d}m"

    @staticmethod
    def _summary(rows: Iterable[DailyAttendanceRowOut]) -> AttendanceSummaryOut:
        present = late = missing = absent = leave = off_day = holiday = 0
        total = 0
        for row in rows:
            total += 1
            if row.status == "Present":
                present += 1
            elif row.status == "Late":
                late += 1
            elif row.status == "Missing Punch":
                missing += 1
            elif row.status == "Absent":
                absent += 1
            elif row.status == "On Leave":
                leave += 1
            elif row.status == "Off Day":
                off_day += 1
            elif row.status == "Holiday":
                holiday += 1
        return AttendanceSummaryOut(
            total=total,
            present=present + late + missing,
            late=late,
            missing_punch=missing,
            absent=absent,
            on_leave=leave,
            off_day=off_day,
            holiday=holiday,
        )

    @staticmethod
    def _filter_options(rows: list[DailyAttendanceRowOut]) -> AttendanceFilterOptionsOut:
        return AttendanceFilterOptionsOut(
            departments=sorted({r.department for r in rows if r.department and r.department != "—"}),
            locations=sorted({r.location for r in rows if r.location and r.location != "—"}),
            shifts=sorted({r.shift for r in rows if r.shift}),
            employee_types=sorted({r.employee_type for r in rows if r.employee_type}),
            managers=sorted({r.reporting_manager for r in rows if r.reporting_manager and r.reporting_manager != "—"}),
            statuses=list(_STATUSES),
        )

    @staticmethod
    def _apply_filters(rows: list[DailyAttendanceRowOut], query: DailyAttendanceQuery) -> list[DailyAttendanceRowOut]:
        q = (query.search or "").strip().lower()
        result: list[DailyAttendanceRowOut] = []
        for row in rows:
            if not _matches_tab(row.status, query.status_tab):
                continue
            if query.department and row.department != query.department:
                continue
            if query.location and row.location != query.location:
                continue
            if query.shift and row.shift != query.shift:
                continue
            if query.status and row.status != query.status:
                continue
            if query.employee_type and row.employee_type != query.employee_type:
                continue
            if query.reporting_manager and row.reporting_manager != query.reporting_manager:
                continue
            if q and q not in f"{row.employee_code} {row.employee_name}".lower():
                continue
            result.append(row)
        return result


def _matches_tab(status: AttendanceDisplayStatus, tab: StatusTab) -> bool:
    if tab == "all":
        return True
    if tab == "present":
        return status in ("Present", "Late", "Missing Punch")
    if tab == "absent":
        return status == "Absent"
    if tab == "leave":
        return status == "On Leave"
    if tab == "offDay":
        return status in ("Off Day", "Holiday")
    return True
