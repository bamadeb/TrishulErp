"""Compute Daily Attendance for a calendar day from live HR data sources."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable
import json

from sqlalchemy.orm import Session

from fastapi import HTTPException

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError
from trishul_api.modules.hr.attendance import cache as attendance_cache
from trishul_api.db.models import (
    Attendance,
    AttendanceAudit,
    AttendanceRegularization,
    AuditLog,
    EmployeeShift,
    Shift,
)
from trishul_api.modules.hr.attendance.finalization_ops import require_day_writable
from trishul_api.modules.hr.attendance.policy import (
    GRACE_DAYS_PER_MONTH,
    OfficialVisit,
    classify_arrival,
    expected_net_minutes,
    grace_days_before,
    leaves_early,
    net_worked_minutes,
)
from trishul_api.modules.hr.attendance.payload import (
    decode_reason,
    encode_reason,
    requested_status_for,
)
from trishul_api.modules.hr.attendance.rules_ops import ShiftRulesService, _DEFAULT_RULES
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
    AttendanceDashboardOut,
    AttendanceDisplayStatus,
    AttendanceExceptionRowOut,
    AttendanceExceptionsPageOut,
    AttendanceExceptionsQuery,
    AttendanceFilterOptionsOut,
    AttendanceHistoryOut,
    AttendancePunchLocationOut,
    AttendancePunchOut,
    AttendanceReportsSummaryOut,
    AttendanceSummaryOut,
    DailyAttendancePageOut,
    DailyAttendanceQuery,
    DailyAttendanceRowOut,
    DashboardDepartmentRowOut,
    DashboardLocationRowOut,
    DashboardExceptionItemOut,
    DashboardKpiOut,
    DashboardOverviewSliceOut,
    DashboardQuickActionOut,
    DashboardTrendPointOut,
    ExceptionFilterOptionsOut,
    ExceptionKpiOut,
    ExceptionReviewStatus,
    ExceptionType,
    MineAttendanceDayOut,
    MineAttendancePageOut,
    MineAttendanceSummaryOut,
    ResolvedAttendanceStatus,
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

_MONTH_LABELS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

# Display status → hr.attendance.status (payroll LOP reads Absent / Half day).
# TTPL HR Policy: grace of 15 minutes if crossed → half-day salary deduction.
# Missing Punch is intentionally omitted — policy treats non-punching as misconduct
# for HR review, not silent full-day LOP.
_PERSIST_STATUS: dict[AttendanceDisplayStatus, str] = {
    "Present": "Present",
    "Late": "Half day",
    "Absent": "Absent",
    "On Leave": "Leave",
    "Off Day": "Week off",
    "Holiday": "Holiday",
}

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

    def resolve_exception(
        self,
        exception_id: int,
        actor: CurrentUser | None = None,
        remark: str | None = None,
        resolved_status: ResolvedAttendanceStatus | None = None,
    ) -> AttendanceExceptionRowOut:
        employee_id, day = _parse_exception_id(exception_id)
        require_day_writable(self._repo._db, day)

        # Detect current exception type before mutating.
        page_before = self.list_exceptions(
            AttendanceExceptionsQuery(
                date_from=day,
                date_to=day,
                page=1,
                page_size=200,
                status_tab="all",
            )
        )
        current = next((row for row in page_before.items if row.id == exception_id), None)
        exception_type = current.exception_type if current else "Absent"

        # Missing Punch / Absent have no silent LOP policy — operator must choose status.
        if exception_type in ("Missing Punch", "Absent") and resolved_status is None:
            raise ApiError(
                f"{exception_type} has no automatic LOP policy configured. "
                "Provide resolvedStatus (Present, Half day, Absent, or On duty), "
                "or submit/approve a regularization with the correct times."
            )

        target_status: str
        if resolved_status is not None:
            target_status = resolved_status
        elif exception_type == "Late Arrival":
            # TTPL: grace crossed → half-day salary deduction (unless HR overrides).
            target_status = "Half day"
        elif exception_type in ("Early Exit", "Short Hours"):
            target_status = "Present"
        else:
            target_status = "Absent"

        attendance = self._repo.get_attendance(employee_id, day)
        old_values = _attendance_snapshot(attendance)
        if attendance is None:
            # Materialize may skip Missing Punch (no silent LOP); fall back to ensure row.
            self.materialize_employee_day(employee_id, day, actor_id=actor.id if actor else None)
            attendance = self._repo.get_attendance(employee_id, day)
        if attendance is None:
            attendance = self._repo.ensure_attendance(
                employee_id=employee_id,
                day=day,
                check_in=current.first_in if current else None,
                check_out=current.last_out if current else None,
                actor_id=actor.id if actor else None,
            )

        attendance.status = target_status  # type: ignore[assignment]
        attendance.is_regularized = True
        attendance.updated_at = datetime.utcnow()
        attendance.updated_by_user_id = actor.id if actor else None
        self._repo.save_attendance(attendance)
        attendance_cache.invalidate("attendance:")
        self._audit(
            actor_id=actor.id if actor else None,
            entity_type="hr.attendance",
            entity_id=int(attendance.id),
            action="Update",
            old_values=old_values,
            new_values={
                **_attendance_snapshot(attendance),
                "exceptionId": exception_id,
                "exceptionType": exception_type,
                "remark": remark,
            },
        )

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
        employees = {e.id: e for e in self._cached_employees()}
        employee = employees.get(employee_id)
        name = "—"
        if employee is not None:
            name = (
                " ".join(part for part in (employee.first_name, employee.last_name) if part).strip()
                or employee.employee_code
            )
        if match is None:
            return AttendanceExceptionRowOut(
                id=exception_id,
                employee_id=employee_id,
                employee_code=employee.employee_code if employee else "—",
                employee_name=name,
                department=employee.department_name if employee else "—",
                location=employee.branch_name if employee else "—",
                date=day,
                shift="—",
                exception_type=exception_type,  # type: ignore[arg-type]
                expected_hours="00:00",
                actual_hours=None,
                status="Resolved",
                remark=remark or f"Resolved as {target_status}",
            )
        return match.model_copy(
            update={"remark": remark or f"Resolved as {target_status}", "status": "Resolved"}
        )

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

    def create_regularization(
        self,
        actor: CurrentUser,
        data: RegularizationCreateIn,
        *,
        force_employee_id: int | None = None,
    ) -> RegularizationRowOut:
        # ESS path binds to authenticated employee; HR-on-behalf requires manage.
        if force_employee_id is not None:
            employee_id = force_employee_id
        else:
            if not actor.can("core.employee.manage"):
                raise ApiError(
                    "Only authorized HR/Admin users may create regularization requests "
                    "for other employees. Use My Attendance for your own requests."
                )
            employee_id = data.employee_id
        day = data.attendance_date
        require_day_writable(self._repo._db, day)

        employees = {e.id: e for e in self._cached_employees()}
        employee = employees.get(employee_id)
        if employee is None:
            all_emps = self._repo.list_employees(employment_status=None)
            employee = next((e for e in all_emps if e.id == employee_id), None)
        if employee is None:
            raise HTTPException(status_code=404, detail="Employee not found.")

        # Block duplicate pending requests for same employee/date.
        existing_regs = self._repo.list_regularizations(start=day, end=day)
        for reg, _emp, _att in existing_regs:
            if reg.employee_id == employee_id and reg.status == "Pending":
                raise ApiError(
                    "A pending regularization request already exists for this employee and date."
                )

        start_dt, end_dt = self._repo.day_bounds(day)
        punches = [p for p in self._repo.punches_between(start_dt, end_dt) if p.employee_id == employee_id]
        first_in = None
        last_out = None
        if punches:
            ordered = sorted(punches, key=lambda p: p.punched_at)
            ins = [p for p in ordered if (p.punch_type or "").upper() == "IN"]
            outs = [p for p in ordered if (p.punch_type or "").upper() == "OUT"]
            first_in = ins[0].punched_at if ins else ordered[0].punched_at
            last_out = outs[-1].punched_at if outs else None

        attendance = self._repo.ensure_attendance(
            employee_id=employee_id,
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
            employee_id=employee_id,
            requested_status=requested_status_for(data.request_type),
            reason=packed,
            status="Pending",
            created_at=datetime.utcnow(),
            created_by_user_id=actor.id,
            is_active=True,
        )
        saved = self._repo.create_regularization(row)
        self._audit(
            actor_id=actor.id,
            entity_type="hr.attendance_regularization",
            entity_id=int(saved.id),
            action="Insert",
            old_values=None,
            new_values={
                "employeeId": employee_id,
                "attendanceDate": day.isoformat(),
                "requestType": data.request_type,
                "status": "Pending",
            },
        )
        attendance_cache.invalidate("attendance:")
        return self._regularization_row(saved, employee, attendance)

    def create_mine_regularization(
        self, actor: CurrentUser, data: RegularizationCreateIn
    ) -> RegularizationRowOut:
        if actor.employee_id is None:
            raise ApiError("Your user account is not linked to an employee profile.")
        return self.create_regularization(actor, data, force_employee_id=actor.employee_id)

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

        attendance = self._repo.get_attendance_by_id(row.attendance_id)
        day = attendance.attendance_date if attendance is not None else date.today()
        require_day_writable(self._repo._db, day)

        request_type, requested_in, requested_out, reason, _ = decode_reason(row.reason)
        remark = (data.remark if data else None) or None
        if not approve and not (remark and remark.strip()):
            raise HTTPException(status_code=400, detail="Rejection reason is required.")

        old_att = _attendance_snapshot(attendance)
        old_reg = {"status": row.status, "id": row.id}

        if approve:
            row.status = "Approved"
            row.reason = encode_reason(
                request_type=request_type,
                requested_in=requested_in,
                requested_out=requested_out,
                reason=reason,
            )
            if attendance is not None:
                check_in = _combine_day_time(day, requested_in) or attendance.check_in_at
                check_out = _combine_day_time(day, requested_out) or attendance.check_out_at
                if check_out is not None and check_in is not None and check_out < check_in:
                    check_out = check_out + timedelta(days=1)
                attendance.check_in_at = check_in
                attendance.check_out_at = check_out
                if check_in is not None and check_out is not None:
                    minutes = max(0, int((check_out - check_in).total_seconds() // 60))
                    attendance.worked_hours = (Decimal(minutes) / Decimal(60)).quantize(Decimal("0.01"))
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
                # Apply half-day threshold from shift/org rules when approval keeps Present.
                if attendance.status == "Present" and attendance.worked_hours is not None:
                    shifts = self._cached_shifts()
                    assignment = self._repo.employee_shifts_for_date(day).get(row.employee_id)
                    effective = self._effective_shift(resolve_shift(assignment, shifts))
                    if (
                        effective.half_day_hours is not None
                        and float(attendance.worked_hours) > 0
                        and float(attendance.worked_hours) <= float(effective.half_day_hours)
                    ):
                        attendance.status = "Half day"  # type: ignore[assignment]
                attendance.is_regularized = True
                attendance.source = "Manual"  # type: ignore[assignment]
                attendance.updated_at = datetime.utcnow()
                attendance.updated_by_user_id = actor.id
                self._repo.save_attendance(attendance)
                attendance_cache.invalidate("attendance:")
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
        self._audit(
            actor_id=actor.id,
            entity_type="hr.attendance_regularization",
            entity_id=int(saved.id),
            action="Update",
            old_values={**old_reg, "attendance": old_att},
            new_values={
                "status": saved.status,
                "requestType": request_type,
                "requestedIn": requested_in,
                "requestedOut": requested_out,
                "attendance": _attendance_snapshot(attendance),
                "remark": remark,
            },
        )
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

        if last_out is not None and leaves_early(last_out, day, self._official_visits(employee.id, day)):
            early_by = int((datetime.combine(day, shift.end_time) - last_out).total_seconds() // 60)
            return (
                "Early Exit",
                first_in,
                last_out,
                expected_hours,
                actual_hours,
                f"Left {max(early_by, 0)} minutes before 5:30 PM.",
            )

        worked = self._parse_hours_minutes(working_hours)
        # Prefer shift half-day threshold; fall back to grace-based short-hours band.
        half = shift.half_day_hours
        if half is not None and worked > 0 and (worked / 60.0) <= float(half):
            return (
                "Short Hours",
                first_in,
                last_out,
                expected_hours,
                actual_hours,
                f"Worked at or below half-day threshold ({half}h).",
            )
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

    def _org_rules(self) -> dict[str, Any]:
        def _load() -> dict[str, Any]:
            db = getattr(self._repo, "_db", None)
            if db is None:
                return dict(_DEFAULT_RULES)
            _row, payload = ShiftRulesService(db)._load_rules_row()
            return dict(payload)

        return attendance_cache.get_or_set("attendance:org_rules", _load, ttl_seconds=30.0)

    def _grace_used_before(self, employee_id: int, day: date) -> int:
        """Grace days already used this calendar month, from actual punches."""
        key = (day.year, day.month)
        cached = getattr(self, "_grace_month", None)
        if cached is None or cached[0] != key:
            start = date(day.year, day.month, 1)
            if day.month == 12:
                end = date(day.year, 12, 31)
            else:
                end = date(day.year, day.month + 1, 1) - timedelta(days=1)
            end = min(end, date.today())
            start_dt, _ = self._repo.day_bounds(start)
            _, end_dt = self._repo.day_bounds(end)
            punches = self._repo.punches_between(start_dt, end_dt)
            firsts: dict[int, dict[date, datetime]] = defaultdict(dict)
            for punch in punches:
                if (punch.punch_type or "").upper() != "IN":
                    continue
                current = firsts[punch.employee_id].get(punch.punched_at.date())
                if current is None or punch.punched_at < current:
                    firsts[punch.employee_id][punch.punched_at.date()] = punch.punched_at
            packed = {
                employee: [(when, at) for when, at in days.items()]
                for employee, days in firsts.items()
            }
            self._grace_month = (key, packed)
        packed = self._grace_month[1]
        return grace_days_before(packed.get(employee_id, []), day)

    def _official_visits(self, employee_id: int, day: date) -> list[OfficialVisit]:
        cached = getattr(self, "_visit_day", None)
        if cached is None or cached[0] != day:
            self._visit_day = (day, self._repo.official_visits_on(day))
        return self._visit_day[1].get(employee_id, [])

    def _audit(
        self,
        *,
        actor_id: int | None,
        entity_type: str,
        entity_id: int,
        action: str,
        old_values: dict[str, Any] | None,
        new_values: dict[str, Any] | None,
    ) -> None:
        self._repo._db.add(
            AuditLog(
                entity_type=entity_type[:50],
                entity_id=entity_id,
                action=action,  # type: ignore[arg-type]
                old_values=json.dumps(old_values, default=str) if old_values is not None else None,
                new_values=json.dumps(new_values, default=str) if new_values is not None else None,
                changed_by_user_id=actor_id,
                changed_at=datetime.utcnow(),
                source="API",  # type: ignore[arg-type]
                ip_address=None,
            )
        )
        self._repo._db.commit()

    def _effective_shift(self, shift: ShiftAssignment) -> ShiftAssignment:
        """Merge org attendance rules into the shift assignment used for evaluation.

        - Late grace: org ``lateArrivalGraceMinutes`` (rules UI), not a second silent default.
        - Weekly off: employee assignment wins; otherwise org ``weeklyOffDays``.
        - Half-day threshold: shift.half_day_hours, else half of org ``standardWorkHours``.
        """
        rules = self._org_rules()
        late_grace = int(rules.get("lateArrivalGraceMinutes", shift.grace_minutes))
        weekly = shift.weekly_off_days
        if not weekly or not str(weekly).strip():
            days = rules.get("weeklyOffDays") or ["SUN"]
            weekly = ",".join(days) if isinstance(days, list) else str(days)
        half = shift.half_day_hours
        if half is None:
            std = float(rules.get("standardWorkHours") or 8.0)
            half = std / 2.0
        return ShiftAssignment(
            shift_id=shift.shift_id,
            shift_name=shift.shift_name,
            start_time=shift.start_time,
            end_time=shift.end_time,
            grace_minutes=late_grace,
            weekly_off_days=weekly,
            half_day_hours=half,
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
        effective = self._effective_shift(shift)
        visits = self._official_visits(employee.id, day)
        grace_used = self._grace_used_before(employee.id, day)
        first_in, last_out, first_in_late, working_hours, punch_status, punch_remarks = self._from_punches(
            day, effective, punches, grace_used=grace_used, visits=visits
        )

        holiday = next(
            (
                h
                for h in holidays
                if self._repo.holiday_applies(h, employee.branch_id, employee.branch_state_id)
            ),
            None,
        )
        is_off = day.weekday() in off_weekdays(effective.weekly_off_days)

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
        *,
        grace_used: int = 0,
        visits: list[OfficialVisit] | None = None,
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

        typed = [(p.punched_at, (p.punch_type or "").upper()) for p in ordered]
        worked_minutes = net_worked_minutes(typed, day, visits)
        working_hours = self._format_hours(worked_minutes)
        arrival = classify_arrival(first_in, day, grace_used)
        first_in_late = arrival.attendance_status == "Late"

        has_out = last_out is not None and last_out != first_in
        shift_ended = datetime.combine(day, shift.end_time)
        if not has_out:
            status: AttendanceDisplayStatus = "Missing Punch"
            if day < date.today() or datetime.now() >= shift_ended:
                remarks = "Missing OUT punch"
            else:
                remarks = "Shift in progress / missing OUT"
            return first_in, None, first_in_late, working_hours, status, remarks

        remarks = arrival.remarks
        if leaves_early(last_out, day, visits):
            remarks = f"{remarks} Left before 5:30 PM.".strip()
        status = arrival.attendance_status  # type: ignore[assignment]
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
        where = punch.location
        return AttendancePunchOut(
            kind=kind,  # type: ignore[arg-type]
            at=punch.punched_at,
            device=punch.device_name or "—",
            location=AttendancePunchLocationOut(
                latitude=where.latitude,
                longitude=where.longitude,
                accuracy_m=where.accuracy_m,
                place=where.place,
                inside_office=where.inside_office,
                distance_m=where.distance_m,
                fake_gps=where.fake_gps,
            )
            if where is not None
            else None,
        )

    @staticmethod
    def _worked_minutes(punches: list[PunchSource], day: date | None = None) -> int:
        ordered = sorted(punches, key=lambda p: p.punched_at)
        typed = [(p.punched_at, (p.punch_type or "").upper()) for p in ordered]
        if not typed:
            return 0
        return net_worked_minutes(typed, day or typed[0][0].date())

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

    def materialize_employee_day(
        self, employee_id: int, day: date, *, actor_id: int | None
    ) -> bool:
        """Persist one computed day into hr.attendance (for LOP / resolve)."""
        employees = {e.id: e for e in self._cached_employees()}
        employee = employees.get(employee_id)
        if employee is None:
            return False
        shifts = self._cached_shifts()
        assignment = self._repo.employee_shifts_for_date(day).get(employee_id)
        shift = self._effective_shift(resolve_shift(assignment, shifts))
        holidays = self._repo.holidays_on(day)
        leave = self._repo.approved_leave_for_date(day).get(employee_id)
        start, end = self._repo.day_bounds(day)
        punches = [p for p in self._repo.punches_between(start, end) if p.employee_id == employee_id]
        first_in, last_out, _, working_hours, status, _ = self._evaluate(
            day=day,
            employee=employee,
            shift=shift,
            holidays=holidays,
            leave=leave,
            punches=punches,
        )
        worked = _hours_decimal(working_hours)
        persisted_status = _persist_status(
            status, leave, worked_hours=worked, half_day_hours=shift.half_day_hours
        )
        if persisted_status is None:
            # Missing Punch: no silent LOP — leave unresolved until explicit resolution.
            return False
        source = "Biometric" if punches else "Manual"
        if persisted_status == "Half day" and status == "Late":
            self._repo._db.add(
                AttendanceAudit(
                    entity="policy",
                    entity_id=employee_id,
                    action="half_day_deduction",
                    old_json=None,
                    new_json=json.dumps(
                        {
                            "date": day.isoformat(),
                            "attendanceStatus": status,
                            "payrollStatus": persisted_status,
                        }
                    ),
                    by_user_id=actor_id,
                    at=datetime.utcnow(),
                )
            )
        persisted = self._repo.upsert_computed_day(
            employee_id=employee_id,
            day=day,
            shift_id=shift.shift_id,
            check_in=first_in,
            check_out=last_out,
            worked_hours=worked,
            status=persisted_status,
            source=source,
            actor_id=actor_id,
        )
        self._repo.flush()
        return persisted

    def materialize_month(self, actor: CurrentUser, year: int, month: int) -> int:
        """Write computed daily rows into hr.attendance for payroll LOP. Skips future days."""
        start = date(year, month, 1)
        end = date(year, 12, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
        end = min(end, date.today())
        employees = self._cached_employees()
        if not employees:
            return 0
        shifts = self._cached_shifts()
        wanted = {e.id for e in employees}
        written = 0
        day = start
        while day <= end:
            assignments = self._repo.employee_shifts_for_date(day)
            holidays = self._repo.holidays_on(day)
            leaves = self._repo.approved_leave_for_date(day)
            start_dt, end_dt = self._repo.day_bounds(day)
            punches = self._repo.punches_between(start_dt, end_dt)
            by_emp: dict[int, list[PunchSource]] = defaultdict(list)
            for punch in punches:
                if punch.employee_id in wanted:
                    by_emp[punch.employee_id].append(punch)
            for employee in employees:
                shift = self._effective_shift(resolve_shift(assignments.get(employee.id), shifts))
                emp_punches = by_emp.get(employee.id, [])
                leave = leaves.get(employee.id)
                first_in, last_out, _, working_hours, status, _ = self._evaluate(
                    day=day,
                    employee=employee,
                    shift=shift,
                    holidays=holidays,
                    leave=leave,
                    punches=emp_punches,
                )
                worked = _hours_decimal(working_hours)
                persisted_status = _persist_status(
                    status, leave, worked_hours=worked, half_day_hours=shift.half_day_hours
                )
                if persisted_status is None:
                    continue
                if persisted_status == "Half day" and status == "Late":
                    self._repo._db.add(
                        AttendanceAudit(
                            entity="policy",
                            entity_id=employee.id,
                            action="half_day_deduction",
                            old_json=None,
                            new_json=json.dumps(
                                {
                                    "date": day.isoformat(),
                                    "attendanceStatus": status,
                                    "payrollStatus": persisted_status,
                                }
                            ),
                            by_user_id=actor.id,
                            at=datetime.utcnow(),
                        )
                    )
                if self._repo.upsert_computed_day(
                    employee_id=employee.id,
                    day=day,
                    shift_id=shift.shift_id,
                    check_in=first_in,
                    check_out=last_out,
                    worked_hours=worked,
                    status=persisted_status,
                    source="Biometric" if emp_punches else "Manual",
                    actor_id=actor.id,
                ):
                    written += 1
            day += timedelta(days=1)
        self._repo.flush()
        return written

    def dashboard(
        self,
        day: date,
        *,
        department: str | None = None,
        location: str | None = None,
    ) -> AttendanceDashboardOut:
        all_rows = self._all_daily_rows(day)
        department_options = sorted({r.department for r in all_rows if r.department and r.department != "—"})
        location_options = sorted({r.location for r in all_rows if r.location and r.location != "—"})
        daily_rows = [
            row
            for row in all_rows
            if (not department or row.department == department) and (not location or row.location == location)
        ]
        summary = self._summary(daily_rows)
        total = max(summary.total, 1)
        present_like = summary.present
        attendance_rate = round((present_like / total) * 1000) / 10 if summary.total else 0.0

        exceptions = self.list_exceptions(
            AttendanceExceptionsQuery(
                date_from=day,
                date_to=day,
                page=1,
                page_size=200,
                status_tab="pending",
                department=department,
                location=location,
            )
        )
        early = exceptions.summary.early_exit
        short = exceptions.summary.short_hours

        def pct(part: int) -> float:
            return round((part / total) * 1000) / 10 if summary.total else 0.0

        kpi = DashboardKpiOut(
            total=summary.total,
            present=present_like,
            present_pct=pct(present_like),
            absent=summary.absent,
            absent_pct=pct(summary.absent),
            on_leave=summary.on_leave,
            late=summary.late,
            late_pct=pct(summary.late),
            early_exit=early,
            early_exit_pct=pct(early),
            short_hours=short,
            short_hours_pct=pct(short),
        )
        overview = [
            DashboardOverviewSliceOut(label="Present", count=present_like, percent=pct(present_like), color="#22c55e"),
            DashboardOverviewSliceOut(label="Absent", count=summary.absent, percent=pct(summary.absent), color="#ef4444"),
            DashboardOverviewSliceOut(label="Late Arrival", count=summary.late, percent=pct(summary.late), color="#f59e0b"),
            DashboardOverviewSliceOut(label="Early Exit", count=early, percent=pct(early), color="#8b5cf6"),
            DashboardOverviewSliceOut(label="Short Hours", count=short, percent=pct(short), color="#0ea5e9"),
        ]

        by_dept: dict[str, list[DailyAttendanceRowOut]] = defaultdict(list)
        for row in daily_rows:
            by_dept[row.department or "—"].append(row)
        departments: list[DashboardDepartmentRowOut] = []
        for index, name in enumerate(sorted(by_dept), start=1):
            rows = by_dept[name]
            present = sum(1 for r in rows if r.status in ("Present", "Late", "Missing Punch"))
            absent = sum(1 for r in rows if r.status == "Absent")
            emp_count = len(rows)
            departments.append(
                DashboardDepartmentRowOut(
                    id=index,
                    department=name,
                    employees=emp_count,
                    present=present,
                    absent=absent,
                    attendance_pct=round((present / emp_count) * 1000) / 10 if emp_count else 0.0,
                )
            )

        by_location: dict[str, list[DailyAttendanceRowOut]] = defaultdict(list)
        for row in daily_rows:
            by_location[row.location or "—"].append(row)
        locations: list[DashboardLocationRowOut] = []
        for name in sorted(by_location):
            rows = by_location[name]
            present = sum(1 for r in rows if r.status in ("Present", "Late", "Missing Punch"))
            absent = sum(1 for r in rows if r.status == "Absent")
            emp_count = len(rows)
            locations.append(
                DashboardLocationRowOut(
                    location=name,
                    employees=emp_count,
                    present=present,
                    absent=absent,
                    attendance_pct=round((present / emp_count) * 1000) / 10 if emp_count else 0.0,
                )
            )

        def trend_summary(trend_day: date) -> AttendanceSummaryOut:
            if trend_day == day:
                return summary
            if department or location:
                rows = [
                    row
                    for row in self._all_daily_rows(trend_day)
                    if (not department or row.department == department)
                    and (not location or row.location == location)
                ]
                return self._summary(rows)
            page = self.list_daily(
                DailyAttendanceQuery(
                    attendance_date=trend_day,
                    page=1,
                    page_size=1,
                    status_tab="all",
                    include_history=False,
                    include_punches=False,
                )
            )
            return page.summary

        trend: list[DashboardTrendPointOut] = []
        for offset in range(6, -1, -1):
            trend_day = day - timedelta(days=offset)
            snap = trend_summary(trend_day)
            t = snap.total
            p = snap.present
            rate = round((p / t) * 1000) / 10 if t else 0.0
            trend.append(
                DashboardTrendPointOut(
                    label=trend_day.strftime("%d %b"),
                    percent=rate,
                    date=trend_day,
                    present=p,
                    absent=snap.absent,
                    on_leave=snap.on_leave,
                )
            )

        exception_items = [
            DashboardExceptionItemOut(
                id="missing",
                label="Missing Punch",
                count=exceptions.summary.missing_punch,
                tone="missing",
                icon="fingerprint",
                route="/hr/attendance/exceptions",
            ),
            DashboardExceptionItemOut(
                id="late",
                label="Late Arrival",
                count=exceptions.summary.late_arrival,
                tone="late",
                icon="schedule",
                route="/hr/attendance/exceptions",
            ),
            DashboardExceptionItemOut(
                id="early",
                label="Early Exit",
                count=exceptions.summary.early_exit,
                tone="early",
                icon="logout",
                route="/hr/attendance/exceptions",
            ),
            DashboardExceptionItemOut(
                id="short",
                label="Short Hours",
                count=exceptions.summary.short_hours,
                tone="short",
                icon="timer",
                route="/hr/attendance/exceptions",
            ),
        ]
        from trishul_api.modules.hr.attendance.finalization_ops import is_month_finalized

        return AttendanceDashboardOut(
            date=day,
            date_label=day.strftime("%d %b %Y") + (" (Today)" if day == date.today() else ""),
            attendance_rate=attendance_rate,
            kpi=kpi,
            overview=overview,
            trend=trend,
            departments=departments,
            locations=locations,
            department_options=department_options,
            location_options=location_options,
            exceptions=exception_items,
            exceptions_total=exceptions.pending_count,
            actions=[
                DashboardQuickActionOut(
                    id="regularize",
                    label="Regularize Attendance",
                    icon="add",
                    route="/hr/attendance/regularization",
                ),
                DashboardQuickActionOut(
                    id="rules",
                    label="Manage Shifts & Rules",
                    icon="rule",
                    route="/hr/attendance/rules",
                ),
                DashboardQuickActionOut(
                    id="finalize",
                    label="Finalize Attendance",
                    icon="event_available",
                    route="/hr/attendance/finalization",
                ),
                DashboardQuickActionOut(
                    id="reports",
                    label="Attendance Reports",
                    icon="download",
                    route="/hr/attendance/reports",
                ),
            ],
            is_month_finalized=is_month_finalized(self._repo._db, day.year, day.month),
        )

    def mine(self, actor: CurrentUser, year: int, month: int) -> MineAttendancePageOut:
        if actor.employee_id is None:
            raise ApiError("Your user account is not linked to an employee profile.")
        employees = {e.id: e for e in self._cached_employees()}
        # Include inactive employees for ESS history.
        employee = employees.get(actor.employee_id)
        if employee is None:
            all_emps = self._repo.list_employees(employment_status=None)
            employee = next((e for e in all_emps if e.id == actor.employee_id), None)
        if employee is None:
            raise ApiError("Employee profile not found.")
        start = date(year, month, 1)
        end = date(year, 12, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
        end = min(end, date.today())
        shifts = self._cached_shifts()

        # Batch month window once (same pattern as muster / history) — avoid per-day N+1.
        start_dt, _ = self._repo.day_bounds(start)
        _, end_dt = self._repo.day_bounds(end)
        punches = self._repo.punches_between(start_dt, end_dt, employee_ids={employee.id})
        punches_by_day: dict[date, list[PunchSource]] = defaultdict(list)
        for punch in punches:
            punches_by_day[punch.punched_at.date()].append(punch)
        holidays_by_day = self._repo.holidays_between(start, end)
        leaves_by_day = self._repo.approved_leave_covering_range(start, end)
        overlapping = [
            row
            for row in self._repo.employee_shifts_overlapping(start, end)
            if row.employee_id == employee.id
        ]

        items: list[MineAttendanceDayOut] = []
        present = late = absent = on_leave = off_day = holiday = missing = 0
        day = start
        while day <= end:
            day_assignments = _assignments_for_day(overlapping, day)
            shift = resolve_shift(day_assignments.get(employee.id), shifts)
            first_in, last_out, _, working_hours, status, remarks = self._evaluate(
                day=day,
                employee=employee,
                shift=shift,
                holidays=holidays_by_day.get(day, []),
                leave=leaves_by_day.get(day, {}).get(employee.id),
                punches=punches_by_day.get(day, []),
            )
            if status == "Present":
                present += 1
            elif status == "Late":
                late += 1
            elif status == "Absent":
                absent += 1
            elif status == "On Leave":
                on_leave += 1
            elif status == "Off Day":
                off_day += 1
            elif status == "Holiday":
                holiday += 1
            elif status == "Missing Punch":
                missing += 1
            items.append(
                MineAttendanceDayOut(
                    date=day,
                    status=status,
                    first_in=first_in.strftime("%H:%M") if first_in else None,
                    last_out=last_out.strftime("%H:%M") if last_out else None,
                    working_hours=working_hours,
                    shift=_shift_label(shift),
                    remarks=remarks or "",
                )
            )
            day += timedelta(days=1)
        name = " ".join(part for part in (employee.first_name, employee.last_name) if part).strip() or employee.employee_code
        from trishul_api.modules.hr.attendance.finalization_ops import is_month_finalized

        finalized = is_month_finalized(self._repo._db, year, month)
        regs_raw = self._repo.list_regularizations(start=start, end=end, employee_id=employee.id)
        mine_regs = [self._regularization_row(reg, emp, att) for reg, emp, att in regs_raw]

        return MineAttendancePageOut(
            employee_id=employee.id,
            employee_code=employee.employee_code,
            employee_name=name,
            year=year,
            month=month,
            month_label=f"{_MONTH_LABELS[month - 1]} {year}",
            summary=MineAttendanceSummaryOut(
                present=present,
                late=late,
                absent=absent,
                on_leave=on_leave,
                off_day=off_day,
                holiday=holiday,
                missing_punch=missing,
            ),
            items=list(reversed(items)),
            regularizations=mine_regs,
            is_month_finalized=finalized,
            can_regularize=not finalized,
        )

    def _all_daily_rows(self, day: date) -> list[DailyAttendanceRowOut]:
        """Load every daily row for a date (page_size capped at 200 by schema)."""
        items: list[DailyAttendanceRowOut] = []
        page = 1
        while True:
            result = self.list_daily(
                DailyAttendanceQuery(
                    attendance_date=day,
                    page=page,
                    page_size=200,
                    status_tab="all",
                    include_history=False,
                    include_punches=False,
                )
            )
            items.extend(result.items)
            if len(items) >= result.total or not result.items:
                break
            page += 1
            if page > 50:
                break
        return items

    def reports_summary(self, year: int, month: int) -> AttendanceReportsSummaryOut:
        # page_size max is 200; muster.summary is computed from the full filtered roster.
        muster = self.list_muster(
            MonthlyMusterQuery(year=year, month=month, page=1, page_size=200, employment_status="Active")
        )
        start = date(year, month, 1)
        end = date(year, 12, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
        exceptions = self.list_exceptions(
            AttendanceExceptionsQuery(date_from=start, date_to=end, page=1, page_size=1, status_tab="pending")
        )
        regs = self.list_regularizations(
            RegularizationQuery(date_from=start, date_to=end, page=1, page_size=1, status_tab="pending")
        )
        from trishul_api.modules.hr.attendance.finalization_ops import load_finalization_lock

        lock = load_finalization_lock(self._repo._db, year, month)
        return AttendanceReportsSummaryOut(
            year=year,
            month=month,
            month_label=f"{_MONTH_LABELS[month - 1]} {year}",
            total_employees=muster.summary.total,
            present=muster.summary.present,
            late=muster.summary.late,
            absent=muster.summary.absent,
            on_leave=muster.summary.on_leave,
            wfh=muster.summary.wfh,
            pending_exceptions=exceptions.pending_count,
            pending_regularizations=regs.pending_count,
            is_month_finalized=lock is not None,
            finalized_at=_parse_lock_dt(lock.get("finalizedAt") if lock else None),
        )


def _persist_status(
    status: AttendanceDisplayStatus,
    leave: LeaveCover | None,
    *,
    worked_hours: Decimal | None = None,
    half_day_hours: float | None = None,
) -> str | None:
    """Map display status → hr.attendance.status.

    Returns None for Missing Punch — TTPL policy does not auto-convert unresolved
    missing punches to Absent/LOP; HR must resolve or approve regularization.
    Late (grace allowance used, or more than 15 minutes late) persists as Half day.
    A grace day stays Present here and on the attendance screen.
    """
    if status == "Missing Punch":
        return None
    if leave is not None and leave.is_half_day and status in ("Present", "Late", "On Leave"):
        return "Half day"
    base = _PERSIST_STATUS.get(status, "Absent")
    if (
        base == "Present"
        and half_day_hours is not None
        and worked_hours is not None
        and float(worked_hours) > 0
        and float(worked_hours) <= float(half_day_hours)
    ):
        return "Half day"
    return base


def _attendance_snapshot(row: Attendance | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": int(row.id),
        "employeeId": int(row.employee_id),
        "attendanceDate": row.attendance_date.isoformat() if row.attendance_date else None,
        "status": row.status,
        "checkInAt": row.check_in_at.isoformat() if row.check_in_at else None,
        "checkOutAt": row.check_out_at.isoformat() if row.check_out_at else None,
        "workedHours": str(row.worked_hours) if row.worked_hours is not None else None,
        "isRegularized": bool(row.is_regularized),
        "source": row.source,
    }


def _combine_day_time(day: date, value: str | None) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = " ".join(text.upper().replace(".", "").split())
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I:%M:%S %p"):
        try:
            parsed = datetime.strptime(normalized, fmt).time()
            return datetime.combine(day, parsed)
        except ValueError:
            continue
    return None


def _hours_decimal(working_hours: str | None) -> Decimal | None:
    if not working_hours:
        return None
    # Formats like "8h 30m" or "08:30"
    text = working_hours.strip().lower()
    try:
        if "h" in text:
            hours_part, _, rest = text.partition("h")
            mins_part = rest.replace("m", "").strip() or "0"
            return Decimal(hours_part.strip() or "0") + (Decimal(mins_part) / Decimal(60))
        if ":" in text:
            h, m = text.split(":", 1)
            return Decimal(h) + (Decimal(m) / Decimal(60))
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _parse_lock_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _shift_label(shift: ShiftAssignment) -> str:
    start = shift.start_time.strftime("%H:%M")
    end = shift.end_time.strftime("%H:%M")
    return f"{shift.shift_name} ({start} - {end})"


def _shift_expected_minutes(shift: ShiftAssignment) -> int:
    return expected_net_minutes(shift.start_time, shift.end_time)


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
