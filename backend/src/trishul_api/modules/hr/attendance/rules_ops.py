"""Shift master, org attendance rules, and employee shift assignments.

Persists to existing tables only:
  - hr.shift
  - hr.employee_shift
  - core.system_setting (key hr.attendance.rules, JSON)
  - Leave year bounds come from active leave-policy year_basis + calendar date
  - Holiday counts come from hr.holiday for the configured leave year
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import AlreadyExists, ApiError, Conflict, NotFound
from trishul_api.db.models import Branch, Department, Employee, EmployeeShift, Holiday, Shift, State, SystemSetting
from trishul_api.db.models.leave import LeavePolicy
from trishul_api.modules.hr.attendance.cache import invalidate as invalidate_attendance_cache
from trishul_api.modules.hr.attendance.schemas import (
    AttendanceHolidayItem,
    AttendanceHolidayPage,
    AttendanceRulesOut,
    AttendanceRulesWrite,
    LeaveYearBasis,
    LeaveYearOut,
    ShiftAssignmentEmployeeOption,
    ShiftAssignmentItem,
    ShiftAssignmentListQuery,
    ShiftAssignmentOptions,
    ShiftAssignmentPage,
    ShiftAssignmentWrite,
    ShiftItem,
    ShiftListQuery,
    ShiftPage,
    ShiftSummary,
    ShiftWrite,
    WeekdayCode,
)
from trishul_api.modules.hr.leave.holiday_ops import api_category

RULES_SETTING_KEY = "hr.attendance.rules"
_WEEKDAYS: tuple[WeekdayCode, ...] = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_DEFAULT_RULES: dict[str, Any] = {
    "standardWorkHours": 8.0,
    "workingDaysPerWeek": 5,
    "lateArrivalGraceMinutes": 15,
    "earlyExitGraceMinutes": 15,
    "otAfterHours": 8.0,
    "otApprovalRequired": True,
    # TTPL leave clauses reference Sunday as weekly off; Saturday is configurable per assignment.
    "weeklyOffDays": ["SUN"],
    # Stored for UI; engine uses employee_shift.weekly_off_days then this org fallback.
    "weeklyOffAppliesTo": "All Employees",
    "autoAttendanceEnabled": True,
    "manualAttendanceEnabled": True,
}


class ShiftRulesService:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------ leave year

    def leave_year(self, today: date | None = None) -> LeaveYearOut:
        day = today or date.today()
        basis = self._year_basis()
        if basis == "CALENDAR":
            year = day.year
            start, end = date(year, 1, 1), date(year, 12, 31)
            label = str(year)
        else:
            year = day.year if day.month >= 4 else day.year - 1
            start, end = date(year, 4, 1), date(year + 1, 3, 31)
            label = f"FY {year}-{str(year + 1)[2:]}"
        return LeaveYearOut(year_basis=basis, year=year, label=label, start_date=start, end_date=end)

    def _year_basis(self) -> LeaveYearBasis:
        value = self._db.scalar(
            select(LeavePolicy.year_basis)
            .where(LeavePolicy.is_active == True)  # noqa: E712
            .order_by(LeavePolicy.id)
            .limit(1)
        )
        return "CALENDAR" if (value or "").upper() == "CALENDAR" else "FINANCIAL"

    # ------------------------------------------------------------------ shifts

    def list_shifts(self, query: ShiftListQuery) -> ShiftPage:
        stmt = select(Shift)
        if query.active_only is True:
            stmt = stmt.where(Shift.is_active == True)  # noqa: E712
        elif query.active_only is False:
            stmt = stmt.where(Shift.is_active == False)  # noqa: E712
        if query.search and query.search.strip():
            term = f"%{query.search.strip()}%"
            stmt = stmt.where(or_(Shift.code.ilike(term), Shift.name.ilike(term)))
        rows = list(self._db.scalars(stmt.order_by(Shift.code)).all())
        items = [self._shift_item(row) for row in rows]
        total = len(items)
        start = (query.page - 1) * query.page_size
        page_items = items[start : start + query.page_size]
        active = sum(1 for item in items if item.is_active)
        return ShiftPage(
            items=page_items,
            summary=ShiftSummary(total=total, active=active, inactive=total - active),
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def get_shift(self, shift_id: int) -> ShiftItem:
        row = self._db.get(Shift, shift_id)
        if row is None:
            raise NotFound("Shift not found.")
        return self._shift_item(row)

    def create_shift(self, actor: CurrentUser, data: ShiftWrite) -> ShiftItem:
        code = data.code.strip().upper()
        self._ensure_shift_code_free(code, None)
        self._validate_times(data.start_time, data.end_time)
        result = self._db.execute(
            Shift.__table__.insert()
            .values(
                code=code,
                name=data.name.strip(),
                start_time=data.start_time,
                end_time=data.end_time,
                grace_minutes=data.grace_minutes,
                half_day_hours=data.half_day_hours,
                is_active=data.is_active,
                created_by_user_id=actor.id,
            )
            .returning(Shift.id)
        )
        created_id = int(result.scalar_one())
        self._db.commit()
        self._db.expire_all()
        invalidate_attendance_cache("employees:", "shifts:")
        return self.get_shift(created_id)

    def update_shift(self, actor: CurrentUser, shift_id: int, expected: bytes, data: ShiftWrite) -> ShiftItem:
        current = self._db.get(Shift, shift_id)
        if current is None:
            raise NotFound("Shift not found.")
        if current.row_version != expected:
            raise Conflict()
        code = data.code.strip().upper()
        self._ensure_shift_code_free(code, shift_id)
        self._validate_times(data.start_time, data.end_time)
        updated = self._db.execute(
            Shift.__table__.update()
            .where(Shift.id == shift_id, Shift.row_version == expected)
            .values(
                code=code,
                name=data.name.strip(),
                start_time=data.start_time,
                end_time=data.end_time,
                grace_minutes=data.grace_minutes,
                half_day_hours=data.half_day_hours,
                is_active=data.is_active,
                updated_at=datetime.now(UTC).replace(tzinfo=None),
                updated_by_user_id=actor.id,
            )
        )
        if updated.rowcount != 1:
            raise Conflict()
        self._db.commit()
        self._db.expire_all()
        invalidate_attendance_cache("employees:", "shifts:")
        return self.get_shift(shift_id)

    def delete_shift(self, shift_id: int, expected: bytes) -> None:
        """Deactivate the shift (soft delete) so attendance history stays intact."""
        current = self._db.get(Shift, shift_id)
        if current is None:
            raise NotFound("Shift not found.")
        if current.row_version != expected:
            raise Conflict()
        updated = self._db.execute(
            Shift.__table__.update()
            .where(Shift.id == shift_id, Shift.row_version == expected)
            .values(
                is_active=False,
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        if updated.rowcount != 1:
            raise Conflict()
        self._db.commit()
        self._db.expire_all()
        invalidate_attendance_cache("employees:", "shifts:")

    def _ensure_shift_code_free(self, code: str, shift_id: int | None) -> None:
        found = self._db.scalar(select(Shift.id).where(func.upper(Shift.code) == code).limit(1))
        if found is not None and found != shift_id:
            raise AlreadyExists(f"Shift code '{code}' already exists.")

    @staticmethod
    def _validate_times(start: time, end: time) -> None:
        # Overnight shifts (end <= start) are allowed; zero-length is not.
        if start == end:
            raise ApiError("Shift start and end times must differ.")

    def _shift_item(self, row: Shift) -> ShiftItem:
        return ShiftItem(
            id=int(row.id),
            code=row.code,
            name=row.name,
            start_time=row.start_time,
            end_time=row.end_time,
            work_hours=_format_hours(_work_hours(row.start_time, row.end_time)),
            grace_minutes=int(row.grace_minutes or 0),
            half_day_hours=float(row.half_day_hours) if row.half_day_hours is not None else None,
            is_active=bool(row.is_active),
            is_overnight=row.end_time <= row.start_time,
            row_version=row.row_version,
        )

    # ------------------------------------------------------------------ attendance rules

    def get_rules(self) -> AttendanceRulesOut:
        row, payload = self._load_rules_row()
        leave = self.leave_year()
        holiday_count = self._holiday_count(leave.start_date, leave.end_date)
        return AttendanceRulesOut(
            standard_work_hours=float(payload["standardWorkHours"]),
            working_days_per_week=int(payload["workingDaysPerWeek"]),
            late_arrival_grace_minutes=int(payload["lateArrivalGraceMinutes"]),
            early_exit_grace_minutes=int(payload["earlyExitGraceMinutes"]),
            ot_after_hours=float(payload["otAfterHours"]),
            ot_approval_required=bool(payload["otApprovalRequired"]),
            weekly_off_days=_normalize_weekdays(payload.get("weeklyOffDays") or []),
            weekly_off_applies_to=str(payload.get("weeklyOffAppliesTo") or "All Employees"),
            auto_attendance_enabled=bool(payload["autoAttendanceEnabled"]),
            manual_attendance_enabled=bool(payload["manualAttendanceEnabled"]),
            leave_year_label=leave.label,
            holiday_count=holiday_count,
            row_version=row.row_version if row is not None else None,
        )

    def put_rules(self, actor: CurrentUser, data: AttendanceRulesWrite, expected: bytes | None) -> AttendanceRulesOut:
        if data.working_days_per_week < 7 and not data.weekly_off_days:
            raise ApiError("Select at least one weekly off day when working fewer than seven days.")
        if data.working_days_per_week + len(set(data.weekly_off_days)) > 7:
            raise ApiError("Working days plus weekly off days cannot exceed seven.")
        payload = {
            "standardWorkHours": float(data.standard_work_hours),
            "workingDaysPerWeek": int(data.working_days_per_week),
            "lateArrivalGraceMinutes": int(data.late_arrival_grace_minutes),
            "earlyExitGraceMinutes": int(data.early_exit_grace_minutes),
            "otAfterHours": float(data.ot_after_hours),
            "otApprovalRequired": bool(data.ot_approval_required),
            "weeklyOffDays": list(data.weekly_off_days),
            "weeklyOffAppliesTo": data.weekly_off_applies_to.strip() or "All Employees",
            "autoAttendanceEnabled": bool(data.auto_attendance_enabled),
            "manualAttendanceEnabled": bool(data.manual_attendance_enabled),
        }
        row = self._db.scalar(
            select(SystemSetting).where(
                SystemSetting.setting_key == RULES_SETTING_KEY,
                SystemSetting.company_id.is_(None),
            )
        )
        body = json.dumps(payload, separators=(",", ":"))
        if row is None:
            if expected is not None:
                raise Conflict()
            self._db.execute(
                SystemSetting.__table__.insert().values(
                    company_id=None,
                    setting_key=RULES_SETTING_KEY,
                    setting_value=body,
                    data_type="JSON",
                    description="Organization attendance rules for Shift & Attendance Rules",
                    created_by_user_id=actor.id,
                    is_active=True,
                )
            )
        else:
            if expected is not None and row.row_version != expected:
                raise Conflict()
            updated = self._db.execute(
                SystemSetting.__table__.update()
                .where(
                    SystemSetting.id == row.id,
                    SystemSetting.row_version == (expected if expected is not None else row.row_version),
                )
                .values(
                    setting_value=body,
                    data_type="JSON",
                    updated_at=datetime.now(UTC).replace(tzinfo=None),
                    updated_by_user_id=actor.id,
                    is_active=True,
                )
            )
            if updated.rowcount != 1:
                raise Conflict()
        self._db.commit()
        self._db.expire_all()
        invalidate_attendance_cache()
        return self.get_rules()

    def _load_rules_row(self) -> tuple[SystemSetting | None, dict[str, Any]]:
        row = self._db.scalar(
            select(SystemSetting).where(
                SystemSetting.setting_key == RULES_SETTING_KEY,
                SystemSetting.company_id.is_(None),
                SystemSetting.is_active == True,  # noqa: E712
            )
        )
        if row is None or not row.setting_value:
            return row, dict(_DEFAULT_RULES)
        try:
            parsed = json.loads(row.setting_value)
        except json.JSONDecodeError:
            return row, dict(_DEFAULT_RULES)
        if not isinstance(parsed, dict):
            return row, dict(_DEFAULT_RULES)
        merged = dict(_DEFAULT_RULES)
        merged.update(parsed)
        return row, merged

    def _holiday_count(self, start: date, end: date) -> int:
        return int(
            self._db.scalar(
                select(func.count())
                .select_from(Holiday)
                .where(
                    Holiday.is_active == True,  # noqa: E712
                    Holiday.holiday_date >= start,
                    Holiday.holiday_date <= end,
                )
            )
            or 0
        )

    def holidays_for_leave_year(self) -> AttendanceHolidayPage:
        leave = self.leave_year()
        state_col = Holiday.__table__.c.state_id
        rows = self._db.execute(
            select(
                Holiday.id,
                Holiday.holiday_date,
                Holiday.name,
                Holiday.holiday_type,
                Holiday.branch_id,
                state_col,
                Holiday.is_active,
                Branch.name,
                State.name,
            )
            .outerjoin(Branch, Branch.id == Holiday.branch_id)
            .outerjoin(State, State.id == state_col)
            .where(
                Holiday.is_active == True,  # noqa: E712
                Holiday.holiday_date >= leave.start_date,
                Holiday.holiday_date <= leave.end_date,
            )
            .order_by(Holiday.holiday_date, Holiday.name)
        ).all()
        items = [
            AttendanceHolidayItem(
                id=int(row[0]),
                holiday_date=row[1],
                name=row[2],
                holiday_type=row[3],  # type: ignore[arg-type]
                category=api_category(str(row[3])),
                applies_to=_holiday_applies_to(row[7], row[8]),
                is_active=bool(row[6]),
            )
            for row in rows
        ]
        return AttendanceHolidayPage(leave_year=leave, items=items, total=len(items))

    # ------------------------------------------------------------------ assignments

    def assignment_options(self) -> ShiftAssignmentOptions:
        employees = self._db.execute(
            select(
                Employee.id,
                Employee.employee_code,
                Employee.first_name,
                Employee.last_name,
                Department.name,
            )
            .outerjoin(Department, Department.id == Employee.department_id)
            .where(Employee.is_active == True, Employee.status == "Active")  # noqa: E712
            .order_by(Employee.employee_code)
        ).all()
        shifts = self.list_shifts(ShiftListQuery(page=1, page_size=200, active_only=True)).items
        return ShiftAssignmentOptions(
            employees=[
                ShiftAssignmentEmployeeOption(
                    id=int(row[0]),
                    employee_code=row[1],
                    employee_name=_employee_name(row[2], row[3]),
                    department=row[4] or "—",
                )
                for row in employees
            ],
            shifts=shifts,
        )

    def list_assignments(self, query: ShiftAssignmentListQuery) -> ShiftAssignmentPage:
        today = date.today()
        stmt = (
            select(
                EmployeeShift,
                Employee.employee_code,
                Employee.first_name,
                Employee.last_name,
                Department.name,
                Shift.code,
                Shift.name,
            )
            .join(Employee, Employee.id == EmployeeShift.employee_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .join(Shift, Shift.id == EmployeeShift.shift_id)
            .where(EmployeeShift.is_active == True)  # noqa: E712
        )
        if query.employee_id is not None:
            stmt = stmt.where(EmployeeShift.employee_id == query.employee_id)
        if query.shift_id is not None:
            stmt = stmt.where(EmployeeShift.shift_id == query.shift_id)
        if query.current_only:
            stmt = stmt.where(
                EmployeeShift.from_date <= today,
                or_(EmployeeShift.to_date.is_(None), EmployeeShift.to_date >= today),
            )
        if query.search and query.search.strip():
            term = f"%{query.search.strip()}%"
            stmt = stmt.where(
                or_(
                    Employee.employee_code.ilike(term),
                    Employee.first_name.ilike(term),
                    Employee.last_name.ilike(term),
                    Shift.code.ilike(term),
                    Shift.name.ilike(term),
                )
            )
        rows = list(self._db.execute(stmt.order_by(Employee.employee_code, EmployeeShift.from_date.desc())).all())
        items = [
            self._assignment_item(
                assignment=row[0],
                employee_code=row[1],
                first_name=row[2],
                last_name=row[3],
                department=row[4],
                shift_code=row[5],
                shift_name=row[6],
                today=today,
            )
            for row in rows
        ]
        start = (query.page - 1) * query.page_size
        return ShiftAssignmentPage(
            items=items[start : start + query.page_size],
            total=len(items),
            page=query.page,
            page_size=query.page_size,
        )

    def create_assignment(self, actor: CurrentUser, data: ShiftAssignmentWrite) -> ShiftAssignmentItem:
        self._validate_assignment(data)
        # Close any open/overlapping current assignments so history is preserved.
        self._close_overlapping(actor, data.employee_id, data.from_date, data.to_date, exclude_id=None)
        if data.weekly_off_days is not None:
            weekly = _encode_weekdays(data.weekly_off_days)
        else:
            weekly = self._default_weekly_off()
        result = self._db.execute(
            EmployeeShift.__table__.insert()
            .values(
                employee_id=data.employee_id,
                shift_id=data.shift_id,
                weekly_off_days=weekly,
                from_date=data.from_date,
                to_date=data.to_date,
                is_active=data.is_active,
                created_by_user_id=actor.id,
            )
            .returning(EmployeeShift.id)
        )
        created_id = int(result.scalar_one())
        self._db.commit()
        self._db.expire_all()
        invalidate_attendance_cache("employees:", "shifts:")
        return self.get_assignment(created_id)

    def update_assignment(
        self, actor: CurrentUser, assignment_id: int, expected: bytes, data: ShiftAssignmentWrite
    ) -> ShiftAssignmentItem:
        current = self._db.get(EmployeeShift, assignment_id)
        if current is None:
            raise NotFound("Shift assignment not found.")
        if current.row_version != expected:
            raise Conflict()
        self._validate_assignment(data)
        self._close_overlapping(actor, data.employee_id, data.from_date, data.to_date, exclude_id=assignment_id)
        weekly = _encode_weekdays(data.weekly_off_days) if data.weekly_off_days is not None else current.weekly_off_days
        updated = self._db.execute(
            EmployeeShift.__table__.update()
            .where(EmployeeShift.id == assignment_id, EmployeeShift.row_version == expected)
            .values(
                employee_id=data.employee_id,
                shift_id=data.shift_id,
                weekly_off_days=weekly,
                from_date=data.from_date,
                to_date=data.to_date,
                is_active=data.is_active,
                updated_at=datetime.now(UTC).replace(tzinfo=None),
                updated_by_user_id=actor.id,
            )
        )
        if updated.rowcount != 1:
            raise Conflict()
        self._db.commit()
        self._db.expire_all()
        invalidate_attendance_cache("employees:", "shifts:")
        return self.get_assignment(assignment_id)

    def delete_assignment(self, assignment_id: int, expected: bytes) -> None:
        current = self._db.get(EmployeeShift, assignment_id)
        if current is None:
            raise NotFound("Shift assignment not found.")
        if current.row_version != expected:
            raise Conflict()
        # Soft-close: end yesterday if open-ended and currently active; otherwise deactivate.
        today = date.today()
        values: dict[str, Any] = {
            "updated_at": datetime.now(UTC).replace(tzinfo=None),
        }
        if current.to_date is None or current.to_date >= today:
            values["to_date"] = today - timedelta(days=1) if current.from_date < today else current.from_date
        values["is_active"] = False
        updated = self._db.execute(
            EmployeeShift.__table__.update()
            .where(EmployeeShift.id == assignment_id, EmployeeShift.row_version == expected)
            .values(**values)
        )
        if updated.rowcount != 1:
            raise Conflict()
        self._db.commit()
        self._db.expire_all()
        invalidate_attendance_cache("employees:", "shifts:")

    def get_assignment(self, assignment_id: int) -> ShiftAssignmentItem:
        row = self._db.execute(
            select(
                EmployeeShift,
                Employee.employee_code,
                Employee.first_name,
                Employee.last_name,
                Department.name,
                Shift.code,
                Shift.name,
            )
            .join(Employee, Employee.id == EmployeeShift.employee_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .join(Shift, Shift.id == EmployeeShift.shift_id)
            .where(EmployeeShift.id == assignment_id)
        ).one_or_none()
        if row is None:
            raise NotFound("Shift assignment not found.")
        return self._assignment_item(
            assignment=row[0],
            employee_code=row[1],
            first_name=row[2],
            last_name=row[3],
            department=row[4],
            shift_code=row[5],
            shift_name=row[6],
            today=date.today(),
        )

    def _validate_assignment(self, data: ShiftAssignmentWrite) -> None:
        employee = self._db.get(Employee, data.employee_id)
        if employee is None or not employee.is_active:
            raise ApiError("Select a valid employee.")
        shift = self._db.get(Shift, data.shift_id)
        if shift is None or not shift.is_active:
            raise ApiError("Select a valid active shift.")
        if data.to_date is not None and data.to_date < data.from_date:
            raise ApiError("Assignment end date cannot be before the start date.")

    def _close_overlapping(
        self,
        actor: CurrentUser,
        employee_id: int,
        from_date: date,
        to_date: date | None,
        *,
        exclude_id: int | None,
    ) -> None:
        stmt = select(EmployeeShift).where(
            EmployeeShift.employee_id == employee_id,
            EmployeeShift.is_active == True,  # noqa: E712
        )
        if exclude_id is not None:
            stmt = stmt.where(EmployeeShift.id != exclude_id)
        for row in self._db.scalars(stmt).all():
            if not _ranges_overlap(row.from_date, row.to_date, from_date, to_date):
                continue
            # Close the previous row the day before the new assignment starts.
            close_on = from_date - timedelta(days=1)
            if row.from_date > close_on:
                # Fully superseded — deactivate without leaving an inverted range.
                row.is_active = False
                row.to_date = row.from_date
            else:
                row.to_date = close_on
            row.updated_at = datetime.now(UTC).replace(tzinfo=None)
            row.updated_by_user_id = actor.id

    def _default_weekly_off(self) -> str:
        _, payload = self._load_rules_row()
        encoded = _encode_weekdays(_normalize_weekdays(payload.get("weeklyOffDays") or ["SUN"]))
        return encoded or "SUN"

    def _assignment_item(
        self,
        *,
        assignment: EmployeeShift,
        employee_code: str,
        first_name: str | None,
        last_name: str | None,
        department: str | None,
        shift_code: str,
        shift_name: str,
        today: date,
    ) -> ShiftAssignmentItem:
        is_current = (
            assignment.is_active
            and assignment.from_date <= today
            and (assignment.to_date is None or assignment.to_date >= today)
        )
        return ShiftAssignmentItem(
            id=int(assignment.id),
            employee_id=int(assignment.employee_id),
            employee_code=employee_code,
            employee_name=_employee_name(first_name, last_name),
            department=department or "—",
            shift_id=int(assignment.shift_id),
            shift_code=shift_code,
            shift_name=shift_name,
            weekly_off_days=_decode_weekdays(assignment.weekly_off_days),
            from_date=assignment.from_date,
            to_date=assignment.to_date,
            is_current=bool(is_current),
            is_active=bool(assignment.is_active),
            row_version=assignment.row_version,
        )


def _work_hours(start: time, end: time) -> float:
    start_m = start.hour * 60 + start.minute
    end_m = end.hour * 60 + end.minute
    if end_m <= start_m:
        end_m += 24 * 60
    return (end_m - start_m) / 60.0


def _format_hours(hours: float) -> str:
    total = round(hours * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def _employee_name(first: str | None, last: str | None) -> str:
    return " ".join(part for part in (first or "", last or "") if part).strip() or "—"


def _normalize_weekdays(values: list[Any]) -> list[WeekdayCode]:
    result: list[WeekdayCode] = []
    for value in values:
        code = str(value).strip().upper()[:3]
        if code in _WEEKDAYS and code not in result:
            result.append(code)  # type: ignore[arg-type]
    return result


def _encode_weekdays(days: list[WeekdayCode] | None) -> str | None:
    if not days:
        return None
    return ",".join(_normalize_weekdays(list(days)))


def _decode_weekdays(raw: str | None) -> list[WeekdayCode]:
    if not raw:
        return []
    parts = [part.strip().upper() for part in raw.replace(";", ",").split(",") if part.strip()]
    return _normalize_weekdays(parts)


def _ranges_overlap(a_start: date, a_end: date | None, b_start: date, b_end: date | None) -> bool:
    a_last = a_end or date.max
    b_last = b_end or date.max
    return a_start <= b_last and b_start <= a_last


def _holiday_applies_to(branch_name: str | None, state_name: str | None) -> str:
    if branch_name:
        return branch_name
    if state_name:
        return state_name
    return "All Employees"
