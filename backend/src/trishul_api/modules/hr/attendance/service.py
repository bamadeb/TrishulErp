"""Compute Daily Attendance for a calendar day from live HR data sources."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from fastapi import HTTPException

from trishul_api.auth import CurrentUser
from trishul_api.modules.hr.attendance import cache as attendance_cache
from trishul_api.db.models import AttendanceRegularization, EmployeeShift, Shift
from trishul_api.modules.hr.attendance.payload import (
    decode_reason,
    encode_reason,
    requested_status_for,
)
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
    AttendanceExceptionRowOut,
    AttendanceExceptionsPageOut,
    AttendanceExceptionsQuery,
    AttendanceFilterOptionsOut,
    AttendanceHistoryOut,
    AttendancePunchOut,
    AttendanceSummaryOut,
    DailyAttendancePageOut,
    DailyAttendanceQuery,
    DailyAttendanceRowOut,
    ExceptionFilterOptionsOut,
    ExceptionKpiOut,
    ExceptionReviewStatus,
    ExceptionType,
    MonthlyMusterPageOut,
    MonthlyMusterQuery,
    MusterDayCode,
    MusterDayColumnOut,
    MusterEmployeeRowOut,
    MusterFilterOptionsOut,
    MusterKpiOut,
    RegularizationCreateIn,
    RegularizationDecisionIn,
    RegularizationFilterOptionsOut,
    RegularizationKpiOut,
    RegularizationPageOut,
    RegularizationQuery,
    RegularizationRequestType,
    RegularizationRowOut,
    StatusTab,
)

_WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

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
        employees = self._cached_employees()
        shifts = self._cached_shifts()
        assignments = self._repo.employee_shifts_for_date(day)
        holidays = self._repo.holidays_on(day)
        leaves = self._repo.approved_leave_for_date(day)
        start, end = self._repo.day_bounds(day)
        punches = self._repo.punches_between(start, end)
        punches_by_employee: dict[int, list[PunchSource]] = defaultdict(list)
        for punch in punches:
            punches_by_employee[punch.employee_id].append(punch)

        # Build lightweight status rows for summary / filters (no punch payload).
        light_rows = [
            self._build_row(
                employee=employee,
                day=day,
                shift=resolve_shift(assignments.get(employee.id), shifts),
                holidays=holidays,
                leave=leaves.get(employee.id),
                punches=punches_by_employee.get(employee.id, []),
                include_punches=False,
                history=[],
            )
            for employee in employees
        ]

        filter_options = self._filter_options(light_rows)
        summary = self._summary(light_rows)
        filtered = self._apply_filters(light_rows, query)
        total = len(filtered)
        page_size = query.page_size
        page = query.page
        start_idx = (page - 1) * page_size
        page_slice = filtered[start_idx : start_idx + page_size]

        # Attach punches only for the visible page (drawer needs them).
        employee_map = {e.id: e for e in employees}
        page_items = [
            self._build_row(
                employee=employee_map[row.employee_id],
                day=day,
                shift=resolve_shift(assignments.get(row.employee_id), shifts),
                holidays=holidays,
                leave=leaves.get(row.employee_id),
                punches=punches_by_employee.get(row.employee_id, []),
                include_punches=query.include_punches,
                history=[],
            )
            for row in page_slice
        ]

        if query.include_history and page_items:
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

    def employee_history(self, employee_id: int, before: date, *, days: int = 7) -> list[AttendanceHistoryOut]:
        employees = {e.id: e for e in self._cached_employees()}
        employee = employees.get(employee_id)
        if employee is None:
            return []
        history = self._history_for_employees(
            employees=employees,
            employee_ids=[employee_id],
            before=before,
            days=days,
            shifts=self._cached_shifts(),
        )
        return history.get(employee_id, [])

    def list_muster(self, query: MonthlyMusterQuery) -> MonthlyMusterPageOut:
        """Build the monthly attendance matrix from the same day-evaluation rules as Daily Attendance."""
        start = date(query.year, query.month, 1)
        if query.month == 12:
            end = date(query.year, 12, 31)
        else:
            end = date(query.year, query.month + 1, 1) - timedelta(days=1)
        days_in_month = end.day
        today = date.today()

        employees = self._repo.list_employees(employment_status=query.employment_status)
        shifts = self._cached_shifts()
        overlapping = self._repo.employee_shifts_overlapping(start, end)
        holidays_by_day = self._repo.holidays_between(start, end)
        leaves_by_day = self._repo.approved_leave_covering_range(start, end)

        start_dt, _ = self._repo.day_bounds(start)
        _, end_dt = self._repo.day_bounds(end)
        punches = self._repo.punches_between(start_dt, end_dt)
        punches_by_day: dict[date, dict[int, list[PunchSource]]] = defaultdict(lambda: defaultdict(list))
        for punch in punches:
            punches_by_day[punch.punched_at.date()][punch.employee_id].append(punch)

        day_columns = [
            MusterDayColumnOut(
                day=day,
                weekday=_WEEKDAY_LABELS[date(query.year, query.month, day).weekday()],
                is_weekend=date(query.year, query.month, day).weekday() == 6,
            )
            for day in range(1, days_in_month + 1)
        ]

        rows: list[MusterEmployeeRowOut] = []
        for employee in employees:
            codes: list[MusterDayCode] = []
            minutes_total = 0
            for day_num in range(1, days_in_month + 1):
                day = date(query.year, query.month, day_num)
                day_assignments = _assignments_for_day(overlapping, day)
                shift = resolve_shift(day_assignments.get(employee.id), shifts)
                day_punches = punches_by_day[day].get(employee.id, [])

                if day > today and not day_punches:
                    # Future calendar days: keep offs/holidays/leave visible; blank workdays.
                    holiday = next(
                        (
                            h
                            for h in holidays_by_day.get(day, [])
                            if self._repo.holiday_applies(h, employee.branch_id, employee.branch_state_id)
                        ),
                        None,
                    )
                    leave = leaves_by_day.get(day, {}).get(employee.id)
                    is_off = day.weekday() in off_weekdays(shift.weekly_off_days)
                    if holiday is not None:
                        codes.append("H")
                    elif is_off:
                        codes.append("OFF")
                    elif leave is not None:
                        codes.append("PL")
                    else:
                        codes.append("OFF")
                    continue

                first_in, last_out, _, working_hours, status, _ = self._evaluate(
                    day=day,
                    employee=employee,
                    shift=shift,
                    holidays=holidays_by_day.get(day, []),
                    leave=leaves_by_day.get(day, {}).get(employee.id),
                    punches=day_punches,
                )
                del first_in, last_out
                codes.append(_status_to_muster_code(status))
                minutes_total += self._parse_hours_minutes(working_hours)

            name = " ".join(part for part in (employee.first_name, employee.last_name) if part).strip()
            if not name:
                name = employee.employee_code
            present = sum(1 for c in codes if c == "P")
            late = sum(1 for c in codes if c == "L")
            absent = sum(1 for c in codes if c == "A")
            leave = sum(1 for c in codes if c == "PL")
            wfh = sum(1 for c in codes if c == "WFH")
            rows.append(
                MusterEmployeeRowOut(
                    id=employee.id,
                    employee_id=employee.id,
                    employee_code=employee.employee_code,
                    employee_name=name,
                    department=employee.department_name or "—",
                    location=employee.branch_name or "—",
                    employment_status="Inactive" if employee.employment_status == "Inactive" else "Active",
                    days=codes,
                    present=present,
                    late=late,
                    absent=absent,
                    leave=leave,
                    wfh=wfh,
                    hours=minutes_total // 60,
                )
            )

        filter_options = MusterFilterOptionsOut(
            departments=sorted({r.department for r in rows if r.department and r.department != "—"}),
            locations=sorted({r.location for r in rows if r.location and r.location != "—"}),
        )
        filtered = self._apply_muster_filters(rows, query)
        summary = MusterKpiOut(
            total=len(filtered),
            present=sum(r.present for r in filtered),
            late=sum(r.late for r in filtered),
            absent=sum(r.absent for r in filtered),
            on_leave=sum(r.leave for r in filtered),
            wfh=sum(r.wfh for r in filtered),
        )
        total = len(filtered)
        start_idx = (query.page - 1) * query.page_size
        page_items = filtered[start_idx : start_idx + query.page_size]
        return MonthlyMusterPageOut(
            year=query.year,
            month=query.month,
            days_in_month=days_in_month,
            day_columns=day_columns,
            summary=summary,
            filter_options=filter_options,
            items=page_items,
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def list_exceptions(self, query: AttendanceExceptionsQuery) -> AttendanceExceptionsPageOut:
        """Detect attendance exceptions over a date range from punches, leave, holidays and shifts."""
        start = query.date_from
        end = query.date_to
        if end < start:
            start, end = end, start
        # Cap range to 62 days to keep scans bounded.
        if (end - start).days > 62:
            end = start + timedelta(days=62)
        today = date.today()
        if end > today:
            end = today

        employees = self._cached_employees()
        shifts = self._cached_shifts()
        overlapping = self._repo.employee_shifts_overlapping(start, end)
        holidays_by_day = self._repo.holidays_between(start, end)
        leaves_by_day = self._repo.approved_leave_covering_range(start, end)
        regularized = self._repo.regularized_employee_dates(start, end)

        start_dt, _ = self._repo.day_bounds(start)
        _, end_dt = self._repo.day_bounds(end)
        punches = self._repo.punches_between(start_dt, end_dt)
        punches_by_day: dict[date, dict[int, list[PunchSource]]] = defaultdict(lambda: defaultdict(list))
        for punch in punches:
            punches_by_day[punch.punched_at.date()][punch.employee_id].append(punch)

        rows: list[AttendanceExceptionRowOut] = []
        cursor = start
        while cursor <= end:
            day_assignments = _assignments_for_day(overlapping, cursor)
            holidays = holidays_by_day.get(cursor, [])
            leaves = leaves_by_day.get(cursor, {})
            for employee in employees:
                shift = resolve_shift(day_assignments.get(employee.id), shifts)
                day_punches = punches_by_day[cursor].get(employee.id, [])
                exception = self._detect_exception(
                    day=cursor,
                    employee=employee,
                    shift=shift,
                    holidays=holidays,
                    leave=leaves.get(employee.id),
                    punches=day_punches,
                )
                if exception is None:
                    continue
                exception_type, first_in, last_out, expected_hours, actual_hours, remark = exception
                status: ExceptionReviewStatus = (
                    "Resolved" if (employee.id, cursor) in regularized else "Pending"
                )
                name = " ".join(part for part in (employee.first_name, employee.last_name) if part).strip()
                if not name:
                    name = employee.employee_code
                rows.append(
                    AttendanceExceptionRowOut(
                        id=_exception_id(employee.id, cursor),
                        employee_id=employee.id,
                        employee_code=employee.employee_code,
                        employee_name=name,
                        department=employee.department_name or "—",
                        location=employee.branch_name or "—",
                        date=cursor,
                        shift=_shift_label(shift),
                        first_in=first_in,
                        last_out=last_out,
                        exception_type=exception_type,
                        expected_hours=expected_hours,
                        actual_hours=actual_hours,
                        status=status,
                        remark=remark,
                    )
                )
            cursor += timedelta(days=1)

        # Newest exceptions first.
        rows.sort(key=lambda r: (r.date, r.employee_code), reverse=True)

        filter_options = ExceptionFilterOptionsOut(
            departments=sorted({r.department for r in rows if r.department and r.department != "—"}),
            locations=sorted({r.location for r in rows if r.location and r.location != "—"}),
            exception_types=[
                "Missing Punch",
                "Late Arrival",
                "Early Exit",
                "Short Hours",
                "Absent",
            ],
        )
        # Filters except status tab — KPIs / tab counts stay stable while switching tabs.
        scoped = self._apply_exception_filters(rows, query, apply_status_tab=False)
        summary = self._exception_summary(scoped)
        pending_count = sum(1 for r in scoped if r.status == "Pending")
        resolved_count = sum(1 for r in scoped if r.status == "Resolved")
        filtered = self._apply_exception_filters(rows, query, apply_status_tab=True)
        total = len(filtered)
        start_idx = (query.page - 1) * query.page_size
        page_items = filtered[start_idx : start_idx + query.page_size]
        return AttendanceExceptionsPageOut(
            date_from=start,
            date_to=end,
            summary=summary,
            filter_options=filter_options,
            items=page_items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            pending_count=pending_count,
            resolved_count=resolved_count,
        )

    def resolve_exception(self, exception_id: int, remark: str | None = None) -> AttendanceExceptionRowOut:
        employee_id, day = _parse_exception_id(exception_id)
        attendance = self._repo.get_attendance(employee_id, day)
        if attendance is None:
            raise HTTPException(
                status_code=404,
                detail="No attendance record found to mark this exception resolved.",
            )
        self._repo.mark_regularized(attendance)
        # Recompute this single day for response.
        page = self.list_exceptions(
            AttendanceExceptionsQuery(
                date_from=day,
                date_to=day,
                page=1,
                page_size=200,
                status_tab="all",
            )
        )
        match = next((row for row in page.items if row.id == exception_id), None)
        if match is None:
            # Exception may disappear after regularization if rules change; return stub.
            employees = {e.id: e for e in self._cached_employees()}
            employee = employees.get(employee_id)
            name = "—"
            if employee is not None:
                name = " ".join(part for part in (employee.first_name, employee.last_name) if part).strip() or employee.employee_code
            return AttendanceExceptionRowOut(
                id=exception_id,
                employee_id=employee_id,
                employee_code=employee.employee_code if employee else "—",
                employee_name=name,
                department=employee.department_name if employee else "—",
                location=employee.branch_name if employee else "—",
                date=day,
                shift="—",
                exception_type="Absent",
                expected_hours="00:00",
                actual_hours=None,
                status="Resolved",
                remark=remark or "Marked resolved",
            )
        if remark:
            return match.model_copy(update={"remark": remark, "status": "Resolved"})
        return match.model_copy(update={"status": "Resolved"})

    def list_regularizations(self, query: RegularizationQuery) -> RegularizationPageOut:
        start, end = query.date_from, query.date_to
        if end < start:
            start, end = end, start
        rows_raw = self._repo.list_regularizations(start=start, end=end)
        items = [self._regularization_row(reg, employee, attendance) for reg, employee, attendance in rows_raw]

        filter_options = RegularizationFilterOptionsOut(
            departments=sorted({r.department for r in items if r.department and r.department != "—"}),
            locations=sorted({r.location for r in items if r.location and r.location != "—"}),
            request_types=[
                "Missed Punch",
                "Wrong Attendance",
                "Early Exit",
                "WFH Correction",
                "Late Arrival",
            ],
        )
        scoped = self._apply_regularization_filters(items, query, apply_status_tab=False)
        summary = RegularizationKpiOut(
            total=len(scoped),
            pending=sum(1 for r in scoped if r.status == "Pending"),
            approved=sum(1 for r in scoped if r.status == "Approved"),
            rejected=sum(1 for r in scoped if r.status == "Rejected"),
        )
        filtered = self._apply_regularization_filters(items, query, apply_status_tab=True)
        total = len(filtered)
        start_idx = (query.page - 1) * query.page_size
        page_items = filtered[start_idx : start_idx + query.page_size]
        return RegularizationPageOut(
            date_from=start,
            date_to=end,
            summary=summary,
            filter_options=filter_options,
            items=page_items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            pending_count=summary.pending,
            approved_count=summary.approved,
            rejected_count=summary.rejected,
        )

    def create_regularization(self, actor: CurrentUser, data: RegularizationCreateIn) -> RegularizationRowOut:
        employees = {e.id: e for e in self._cached_employees()}
        employee = employees.get(data.employee_id)
        if employee is None:
            raise HTTPException(status_code=404, detail="Employee not found.")
        day = data.attendance_date
        start_dt, end_dt = self._repo.day_bounds(day)
        punches = [p for p in self._repo.punches_between(start_dt, end_dt) if p.employee_id == data.employee_id]
        first_in = None
        last_out = None
        if punches:
            ordered = sorted(punches, key=lambda p: p.punched_at)
            ins = [p for p in ordered if (p.punch_type or "").upper() == "IN"]
            outs = [p for p in ordered if (p.punch_type or "").upper() == "OUT"]
            first_in = ins[0].punched_at if ins else ordered[0].punched_at
            last_out = outs[-1].punched_at if outs else None

        attendance = self._repo.ensure_attendance(
            employee_id=data.employee_id,
            day=day,
            check_in=first_in,
            check_out=last_out,
            actor_id=actor.id,
        )
        packed = encode_reason(
            request_type=data.request_type,
            requested_in=data.requested_in,
            requested_out=data.requested_out,
            reason=data.reason,
        )
        if data.attachment_name:
            suffix = f" [file:{data.attachment_name}]"
            packed = (packed[: 300 - len(suffix)] + suffix)[:300]

        row = AttendanceRegularization(
            attendance_id=attendance.id,
            employee_id=data.employee_id,
            requested_status=requested_status_for(data.request_type),
            reason=packed,
            status="Pending",
            created_at=datetime.utcnow(),
            created_by_user_id=actor.id,
            is_active=True,
        )
        saved = self._repo.create_regularization(row)
        return self._regularization_row(saved, employee, attendance)

    def decide_regularization(
        self,
        actor: CurrentUser,
        regularization_id: int,
        *,
        approve: bool,
        data: RegularizationDecisionIn | None,
    ) -> RegularizationRowOut:
        row = self._repo.get_regularization(regularization_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Regularization request not found.")
        if row.status != "Pending":
            raise HTTPException(status_code=409, detail="Only pending requests can be decided.")

        request_type, requested_in, requested_out, reason, _ = decode_reason(row.reason)
        remark = (data.remark if data else None) or None
        if not approve and not (remark and remark.strip()):
            raise HTTPException(status_code=400, detail="Rejection reason is required.")

        if approve:
            row.status = "Approved"
            row.reason = encode_reason(
                request_type=request_type,
                requested_in=requested_in,
                requested_out=requested_out,
                reason=reason,
            )
            attendance = self._repo.get_attendance_by_id(row.attendance_id)
            if attendance is not None:
                attendance.is_regularized = True
                if row.requested_status in (
                    "Present",
                    "Absent",
                    "Half day",
                    "Leave",
                    "Holiday",
                    "Week off",
                    "On duty",
                ):
                    attendance.status = row.requested_status
                self._repo.save_attendance(attendance)
        else:
            row.status = "Rejected"
            row.reason = encode_reason(
                request_type=request_type,
                requested_in=requested_in,
                requested_out=requested_out,
                reason=reason,
                rejection_reason=remark,
            )

        row.approver_user_id = actor.id
        row.updated_by_user_id = actor.id
        row.updated_at = datetime.utcnow()
        saved = self._repo.save_regularization(row)
        attendance = self._repo.get_attendance_by_id(saved.attendance_id)
        employees = {e.id: e for e in self._cached_employees()}
        employee = employees.get(saved.employee_id)
        if employee is None:
            raise HTTPException(status_code=404, detail="Employee not found.")
        return self._regularization_row(saved, employee, attendance)

    def _attendance_date_for(self, row: AttendanceRegularization) -> date:
        linked = self._repo.get_attendance_by_id(row.attendance_id)
        if linked is not None:
            return linked.attendance_date
        return date.today()

    def _regularization_row(
        self,
        reg: AttendanceRegularization,
        employee: EmployeeDaySource,
        attendance,
    ) -> RegularizationRowOut:
        request_type, requested_in, requested_out, reason, rejection = decode_reason(reg.reason)
        attachment = None
        if "[file:" in (reg.reason or ""):
            try:
                attachment = reg.reason.split("[file:", 1)[1].split("]", 1)[0]
            except IndexError:
                attachment = None
        name = " ".join(part for part in (employee.first_name, employee.last_name) if part).strip()
        if not name:
            name = employee.employee_code
        return RegularizationRowOut(
            id=reg.id,
            employee_id=employee.id,
            employee_code=employee.employee_code,
            employee_name=name,
            department=employee.department_name or "—",
            location=employee.branch_name or "—",
            attendance_date=attendance.attendance_date if attendance is not None else date.today(),
            request_type=request_type,
            original_in=attendance.check_in_at if attendance is not None else None,
            original_out=attendance.check_out_at if attendance is not None else None,
            requested_in=requested_in,
            requested_out=requested_out,
            reason=reason,
            submitted_on=reg.created_at,
            status=reg.status,  # type: ignore[arg-type]
            rejection_reason=rejection,
            attachment_name=attachment,
        )

    @staticmethod
    def _apply_regularization_filters(
        rows: list[RegularizationRowOut],
        query: RegularizationQuery,
        *,
        apply_status_tab: bool,
    ) -> list[RegularizationRowOut]:
        q = (query.search or "").strip().lower()
        result: list[RegularizationRowOut] = []
        for row in rows:
            if apply_status_tab:
                if query.status_tab == "pending" and row.status != "Pending":
                    continue
                if query.status_tab == "approved" and row.status != "Approved":
                    continue
                if query.status_tab == "rejected" and row.status != "Rejected":
                    continue
            if query.department and row.department != query.department:
                continue
            if query.location and row.location != query.location:
                continue
            if query.request_type and row.request_type != query.request_type:
                continue
            if q and q not in f"{row.employee_code} {row.employee_name}".lower():
                continue
            result.append(row)
        return result

    def _detect_exception(
        self,
        *,
        day: date,
        employee: EmployeeDaySource,
        shift: ShiftAssignment,
        holidays: list[HolidayCover],
        leave: LeaveCover | None,
        punches: list[PunchSource],
    ) -> tuple[ExceptionType, datetime | None, datetime | None, str, str | None, str] | None:
        first_in, last_out, first_in_late, working_hours, status, remarks = self._evaluate(
            day=day,
            employee=employee,
            shift=shift,
            holidays=holidays,
            leave=leave,
            punches=punches,
        )
        if status in ("Off Day", "Holiday", "On Leave"):
            return None

        expected_minutes = _shift_expected_minutes(shift)
        expected_hours = self._format_clock(expected_minutes)
        actual_hours = self._format_clock(self._parse_hours_minutes(working_hours)) if working_hours else None

        if status == "Absent":
            return "Absent", None, None, expected_hours, None, remarks or "No punches and no approved leave."
        if status == "Missing Punch":
            return "Missing Punch", first_in, last_out, expected_hours, actual_hours, remarks or "Missing punch."

        # Complete or late with both punches — check late / early / short.
        if status == "Late" or first_in_late:
            late_by = 0
            if first_in is not None:
                grace_deadline = datetime.combine(day, shift.start_time) + timedelta(minutes=shift.grace_minutes)
                late_by = max(0, int((first_in - grace_deadline).total_seconds() // 60))
            return (
                "Late Arrival",
                first_in,
                last_out,
                expected_hours,
                actual_hours,
                remarks or f"Arrived {late_by} minutes after grace.",
            )

        if last_out is not None:
            early_cutoff = datetime.combine(day, shift.end_time) - timedelta(minutes=max(shift.grace_minutes, 0))
            if last_out < early_cutoff:
                early_by = int((early_cutoff - last_out).total_seconds() // 60)
                return (
                    "Early Exit",
                    first_in,
                    last_out,
                    expected_hours,
                    actual_hours,
                    f"Left {early_by} minutes before shift end.",
                )

        worked = self._parse_hours_minutes(working_hours)
        short_threshold = max(30, shift.grace_minutes)
        if worked > 0 and worked < expected_minutes - short_threshold:
            short_by = expected_minutes - worked
            return (
                "Short Hours",
                first_in,
                last_out,
                expected_hours,
                actual_hours,
                f"Worked {short_by} minutes less than expected shift hours.",
            )
        return None

    def _cached_employees(self) -> list[EmployeeDaySource]:
        return attendance_cache.get_or_set("employees:active", self._repo.list_active_employees)

    def _cached_shifts(self) -> dict[int, Shift]:
        return attendance_cache.get_or_set("shifts:active", self._repo.shifts_by_id)

    def _build_row(
        self,
        *,
        employee: EmployeeDaySource,
        day: date,
        shift: ShiftAssignment,
        holidays: list[HolidayCover],
        leave: LeaveCover | None,
        punches: list[PunchSource],
        include_punches: bool,
        history: list[AttendanceHistoryOut],
    ) -> DailyAttendanceRowOut:
        name = " ".join(part for part in (employee.first_name, employee.last_name) if part).strip()
        if not name:
            name = employee.employee_code
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
            department=employee.department_name or "—",
            location=employee.branch_name or "—",
            shift=shift.shift_name,
            employee_type=employee.employee_type or "Permanent",
            reporting_manager=employee.reporting_manager_name or "—",
            first_in=first_in,
            last_out=last_out,
            first_in_late=first_in_late,
            working_hours=working_hours,
            status=status,
            remarks=remarks,
            punches=[self._punch_out(p) for p in punches] if include_punches else [],
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

        if holiday is not None and not punches:
            return None, None, False, None, "Holiday", holiday.name
        if is_off and not punches:
            return None, None, False, None, "Off Day", "Weekly off"
        if leave is not None and not punches:
            note = "Half-day leave" if leave.is_half_day else "Approved leave"
            return None, None, False, None, "On Leave", note
        if leave is not None and punches and leave.is_half_day:
            if punch_status in ("Present", "Late", "Missing Punch"):
                return first_in, last_out, first_in_late, working_hours, punch_status, "Half-day leave"
            return first_in, last_out, first_in_late, working_hours, "On Leave", "Half-day leave"
        if leave is not None and punches:
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
        shifts: dict[int, Shift],
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

        # Batch: punches + holidays + leave + shift assignments for the whole window.
        punches = self._repo.punches_between(start_dt, end_dt)
        punches_by_day: dict[date, dict[int, list[PunchSource]]] = defaultdict(lambda: defaultdict(list))
        for punch in punches:
            if punch.employee_id not in wanted:
                continue
            punches_by_day[punch.punched_at.date()][punch.employee_id].append(punch)

        holidays_by_day = self._repo.holidays_between(start_day, end_day)
        leaves_by_day = self._repo.approved_leave_covering_range(start_day, end_day)
        overlapping = self._repo.employee_shifts_overlapping(start_day, end_day)

        result: dict[int, list[AttendanceHistoryOut]] = {eid: [] for eid in employee_ids}
        cursor = end_day
        while cursor >= start_day:
            day_assignments = _assignments_for_day(overlapping, cursor)
            holidays = holidays_by_day.get(cursor, [])
            leaves = leaves_by_day.get(cursor, {})
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

    @staticmethod
    def _apply_muster_filters(
        rows: list[MusterEmployeeRowOut],
        query: MonthlyMusterQuery,
    ) -> list[MusterEmployeeRowOut]:
        q = (query.search or "").strip().lower()
        result: list[MusterEmployeeRowOut] = []
        for row in rows:
            if query.department and row.department != query.department:
                continue
            if query.location and row.location != query.location:
                continue
            if q and q not in f"{row.employee_code} {row.employee_name}".lower():
                continue
            result.append(row)
        return result

    @staticmethod
    def _parse_hours_minutes(value: str | None) -> int:
        if not value:
            return 0
        # Formats from _format_hours: "7h 15m" / "8h 00m"
        hours = 0
        mins = 0
        text = value.strip().lower()
        if "h" in text:
            left, _, rest = text.partition("h")
            try:
                hours = int(left.strip() or 0)
            except ValueError:
                hours = 0
            if "m" in rest:
                try:
                    mins = int(rest.replace("m", "").strip() or 0)
                except ValueError:
                    mins = 0
        return max(0, hours * 60 + mins)

    @staticmethod
    def _format_clock(minutes: int) -> str:
        hours, mins = divmod(max(0, minutes), 60)
        return f"{hours:02d}:{mins:02d}"

    @staticmethod
    def _exception_summary(rows: list[AttendanceExceptionRowOut]) -> ExceptionKpiOut:
        missing = late = early = short = absent = 0
        for row in rows:
            if row.exception_type == "Missing Punch":
                missing += 1
            elif row.exception_type == "Late Arrival":
                late += 1
            elif row.exception_type == "Early Exit":
                early += 1
            elif row.exception_type == "Short Hours":
                short += 1
            elif row.exception_type == "Absent":
                absent += 1
        return ExceptionKpiOut(
            total=len(rows),
            missing_punch=missing,
            late_arrival=late,
            early_exit=early,
            short_hours=short,
            absent=absent,
        )

    @staticmethod
    def _apply_exception_filters(
        rows: list[AttendanceExceptionRowOut],
        query: AttendanceExceptionsQuery,
        *,
        apply_status_tab: bool = True,
    ) -> list[AttendanceExceptionRowOut]:
        q = (query.search or "").strip().lower()
        result: list[AttendanceExceptionRowOut] = []
        for row in rows:
            if apply_status_tab:
                if query.status_tab == "pending" and row.status != "Pending":
                    continue
                if query.status_tab == "resolved" and row.status != "Resolved":
                    continue
            if query.department and row.department != query.department:
                continue
            if query.location and row.location != query.location:
                continue
            if query.exception_type and row.exception_type != query.exception_type:
                continue
            if query.status and row.status != query.status:
                continue
            if q and q not in f"{row.employee_code} {row.employee_name}".lower():
                continue
            result.append(row)
        return result


def _shift_label(shift: ShiftAssignment) -> str:
    start = shift.start_time.strftime("%H:%M")
    end = shift.end_time.strftime("%H:%M")
    return f"{shift.shift_name} ({start} - {end})"


def _shift_expected_minutes(shift: ShiftAssignment) -> int:
    start = datetime.combine(date.today(), shift.start_time)
    end = datetime.combine(date.today(), shift.end_time)
    if end <= start:
        end += timedelta(days=1)
    return max(0, int((end - start).total_seconds() // 60))


def _exception_id(employee_id: int, day: date) -> int:
    return employee_id * 1_000_000 + (day.year % 100) * 10_000 + day.month * 100 + day.day


def _parse_exception_id(exception_id: int) -> tuple[int, date]:
    employee_id, packed = divmod(exception_id, 1_000_000)
    year2, rem = divmod(packed, 10_000)
    month, day = divmod(rem, 100)
    year = 2000 + year2
    try:
        return employee_id, date(year, month, day)
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Invalid exception id.") from exc


def _status_to_muster_code(status: AttendanceDisplayStatus) -> MusterDayCode:
    if status == "Present":
        return "P"
    if status == "Late":
        return "L"
    if status == "Missing Punch":
        # Muster legend has no MP cell; treat as Present (employee was on site).
        return "P"
    if status == "Absent":
        return "A"
    if status == "On Leave":
        return "PL"
    if status == "Holiday":
        return "H"
    return "OFF"


def _assignments_for_day(overlapping: list[EmployeeShift], day: date) -> dict[int, EmployeeShift]:
    by_employee: dict[int, EmployeeShift] = {}
    for row in overlapping:
        if row.from_date > day:
            continue
        if row.to_date is not None and row.to_date < day:
            continue
        if row.employee_id not in by_employee:
            by_employee[row.employee_id] = row
    return by_employee


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
