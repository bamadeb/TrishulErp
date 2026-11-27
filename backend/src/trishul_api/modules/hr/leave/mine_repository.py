"""My Leave reads and writes against the existing employee, leave and holiday tables.

Contact details, a document reference, and the half-day part are not columns on these tables.
Those values are validated where the screen sends them and are not stored.
"""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError, Forbidden, NotFound
from trishul_api.db.models import (
    ApprovalRequest,
    AppUser,
    BiometricPunchLog,
    Branch,
    Department,
    Designation,
    Employee,
    EmployeeShift,
    EmploymentHistory,
    Holiday,
    LeaveBalance,
    LeavePolicy,
    LeavePolicyAssignment,
    LeavePolicyLine,
    LeaveRequest,
    LeaveType,
    LeaveTypeSetting,
    Shift,
    StatusHistory,
)
from trishul_api.modules.hr.attendance.policy import net_worked_minutes
from trishul_api.modules.hr.leave.calculation import backdate_rejection, is_medical_emergency
from trishul_api.modules.hr.leave.holiday_ops import applies_to_branch
from trishul_api.modules.hr.leave.overlap import conflict_message
from trishul_api.modules.hr.leave.mine_schemas import (
    MineApply,
    MineApprovalStep,
    MineBalance,
    MineBalances,
    MineCompOff,
    MineDayCount,
    MineHoliday,
    MineHolidayQuery,
    MineProfile,
    MineRequestDetail,
    MineRequestItem,
    MineRequestPage,
    MineRequestQuery,
    MineStatusEvent,
)

_ZERO = Decimal("0.0")
_HALF = Decimal("0.5")
_ANNUAL = {"AL", "EL", "PL"}
_AL_NOTICE_DAYS = 15
_HALF_DAY_MINUTES = 4 * 60
_DOCUMENT = "LEAVE_REQUEST"
_WEEKDAY = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}


def _counts_intervening(code: str, name: str, *, exclude_boundary: bool | None = None) -> bool:
    """Annual leave counts holidays and weekly offs inside the selected range. Casual leave does not.

    ``exclude_boundary=True`` (CL) drops holidays/offs from the count.
    ``exclude_boundary=False`` only forces intervening days for annual-type codes; casual leave
    still excludes them even when the flag is false/default.
    """
    label = name.lower()
    casual = code.strip().upper() == "CL" or "casual" in label
    if exclude_boundary is True or casual:
        return False
    if exclude_boundary is False:
        return True
    if code.strip().upper() in _ANNUAL:
        return True
    return "annual" in label or "privilege" in label or "earned" in label


def _note(action: str, contact: str | None) -> str:
    text = (contact or "").strip()
    if not text:
        return action
    return f"{action}. Contact: {text}"[:500]


class LeaveRuleError(ApiError):
    status = 400
    title = "Leave request was not accepted"


class LeaveMineRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def profile(self, actor: CurrentUser) -> MineProfile:
        employee = self._employee(actor)
        department = self._name(Department, employee.department_id)
        designation = self._name(Designation, employee.designation_id)
        location = self._name(Branch, employee.branch_id)
        confirmed = self._confirmed_on(employee.id, date.today())
        name = " ".join(part for part in (employee.first_name, employee.last_name) if part)
        return MineProfile(
            employee_id=employee.id,
            employee_code=employee.employee_code,
            employee_name=name,
            department=department,
            designation=designation,
            location=location,
            date_of_joining=employee.date_of_joining,
            confirmation_date=confirmed,
            employment_status="Confirmed" if confirmed else employee.status,
        )

    def balances(self, actor: CurrentUser, financial_year: int) -> MineBalances:
        from trishul_api.modules.hr.leave.comp_off_ops import comp_off_totals, expire_due

        employee = self._employee(actor)
        expire_due(self._db, employee_id=employee.id, as_of=date.today())
        start, end = _year_bounds(financial_year)
        latest = self._latest_balances(employee.id, financial_year)
        pending = self._pending_days(employee.id, start, end)
        types = self._db.execute(
            select(LeaveType).where(LeaveType.is_active == True).order_by(LeaveType.code)  # noqa: E712
        ).scalars().all()
        rules = self._configured_lines(employee)
        items = []
        for leave_type in types:
            row = latest.get(leave_type.id)
            if row is None and leave_type.id not in rules:
                continue
            rule = rules.get(leave_type.id)
            credited = row.accrued if row else _ZERO
            availed = row.availed if row else _ZERO
            available = row.closing if row else _ZERO
            expired = None
            if leave_type.code == "CO":
                totals = comp_off_totals(self._db, employee.id, financial_year)
                credited = totals["earned"] or _ZERO
                availed = totals["used"] or _ZERO
                available = totals["available"] or _ZERO
                expired = totals["expired"] or _ZERO
            items.append(
                MineBalance(
                    leave_type_id=leave_type.id,
                    code=leave_type.code,
                    name=leave_type.name,
                    opening=(row.opening if row else _ZERO),
                    credited=credited,
                    availed=availed,
                    pending=pending.get(leave_type.id, _ZERO),
                    available=available,
                    expired=expired,
                    max_backdate_days=rule.max_backdate_days if rule else None,
                    backdate_requires_authorization=rule.backdate_requires_authorization if rule else False,
                )
            )
        return MineBalances(financial_year=financial_year, items=items)

    def comp_off(self, actor: CurrentUser, financial_year: int) -> MineCompOff:
        from trishul_api.modules.hr.leave.comp_off_ops import comp_off_totals, expire_due, list_lines
        from trishul_api.modules.hr.leave.mine_schemas import MineCompOffLine

        employee = self._employee(actor)
        expire_due(self._db, employee_id=employee.id, as_of=date.today())
        totals = comp_off_totals(self._db, employee.id, financial_year)
        lines = [MineCompOffLine.model_validate(row) for row in list_lines(self._db, employee.id, financial_year)]
        expiring = totals["expiring"]
        return MineCompOff(
            earned=totals["earned"] or _ZERO,
            available=totals["available"] or _ZERO,
            used=totals["used"] or _ZERO,
            expiring=None if not expiring else expiring,
            expiry_tracked=True,
            lines=lines,
        )

    def holidays(self, actor: CurrentUser, query: MineHolidayQuery) -> list[MineHoliday]:
        employee = self._employee(actor)
        start, end = _year_bounds(query.financial_year)
        state_id = self._db.scalar(select(Branch.state_id).where(Branch.id == employee.branch_id))
        stmt = (
            select(Holiday)
            .where(
                Holiday.is_active == True,  # noqa: E712
                Holiday.holiday_date >= start,
                Holiday.holiday_date <= end,
                applies_to_branch(employee.branch_id, state_id),
            )
            .order_by(Holiday.holiday_date, Holiday.id)
        )
        rows = self._db.execute(stmt).scalars().all()
        if query.month is not None:
            year = query.year or (query.financial_year if query.month >= 4 else query.financial_year + 1)
            rows = [row for row in rows if row.holiday_date.month == query.month and row.holiday_date.year == year]
        return [
            MineHoliday(holiday_date=row.holiday_date, name=row.name, holiday_type=row.holiday_type) for row in rows
        ]

    def requests(self, actor: CurrentUser, query: MineRequestQuery) -> MineRequestPage:
        employee = self._employee(actor)
        rows = [row for row in self._own_requests(employee.id, query.financial_year) if _matches(row, query)]
        start = (query.page - 1) * query.page_size
        page = rows[start : start + query.page_size]
        steps = self._ensure_steps(page)
        people = self._approver_people({step.approver_user_id for group in steps.values() for step in group})
        return MineRequestPage(
            items=[self._item(row, steps.get(row.id, []), people) for row in page],
            total=len(rows),
            page=query.page,
            page_size=query.page_size,
        )

    def request(self, actor: CurrentUser, request_id: int) -> MineRequestDetail:
        employee = self._employee(actor)
        row = self._own_request(employee.id, request_id)
        return self._detail(row)

    def apply(self, actor: CurrentUser, data: MineApply) -> MineRequestDetail:
        employee = self._employee(actor, lock=True)
        self._active(employee)
        self._require_reporting_manager(employee)
        days = self._validated_days(actor, employee, data, current_id=None)
        row = LeaveRequest(
            employee_id=employee.id,
            leave_type_id=data.leave_type_id,
            from_date=data.from_date,
            to_date=data.to_date,
            is_half_day=data.is_half_day,
            days=days,
            reason=data.reason,
            status="Pending",
            created_at=datetime.now(UTC).replace(tzinfo=None),
            created_by_user_id=actor.id,
            is_active=True,
        )
        self._db.add(row)
        self._db.flush()
        self._history(row.id, None, "Pending", _note("Applied", data.contact), actor.id)
        self._snapshot_approvers(employee, row.id, actor.id)
        self._db.commit()
        self._db.refresh(row)
        return self._detail(row)

    def update(self, actor: CurrentUser, request_id: int, data: MineApply) -> MineRequestDetail:
        employee = self._employee(actor, lock=True)
        self._active(employee)
        row = self._own_request(employee.id, request_id)
        if row.status != "Pending":
            raise LeaveRuleError("Only a pending request can be changed.")
        days = self._validated_days(actor, employee, data, current_id=row.id)
        row.leave_type_id = data.leave_type_id
        row.from_date = data.from_date
        row.to_date = data.to_date
        row.is_half_day = data.is_half_day
        row.days = days
        row.reason = data.reason
        row.updated_by_user_id = actor.id
        self._history(row.id, "Pending", "Pending", _note("Updated", data.contact), actor.id)
        self._db.commit()
        self._db.refresh(row)
        return self._detail(row)

    def count_days(self, actor: CurrentUser, data: MineDayCount) -> Decimal:
        """The same weekend, holiday and half-day rules used when a request is saved."""
        employee = self._employee(actor)
        if data.to_date < data.from_date:
            raise LeaveRuleError("Invalid date range.")
        self._assert_backdate(actor, employee, data.leave_type_id, data.from_date, data.to_date)
        if data.is_half_day and (data.from_date != data.to_date or data.half_day_part is None):
            raise LeaveRuleError("A half day applies to a single date.")
        if not data.is_half_day and data.half_day_part is not None:
            raise LeaveRuleError("Invalid half-day request.")
        leave_type = self._db.get(LeaveType, data.leave_type_id)
        if leave_type is None or not leave_type.is_active:
            raise LeaveRuleError("Leave type inactive.")
        setting = self._db.get(LeaveTypeSetting, leave_type.id)
        if data.is_half_day and setting is not None and not setting.half_day_allowed:
            raise LeaveRuleError("This leave type does not allow a half day.")
        line = None
        try:
            policy = self._policy(employee, data.from_date)
            line = self._policy_line(policy.id, leave_type.id)
        except LeaveRuleError:
            line = None
        days = self._days(
            employee,
            data.from_date,
            data.to_date,
            data.is_half_day,
            leave_type.code,
            leave_type.name,
            exclude_boundary=None if line is None else line.exclude_boundary_holidays,
        )
        if setting is not None and setting.max_consecutive_days is not None and days > setting.max_consecutive_days:
            raise LeaveRuleError(f"This leave type allows at most {setting.max_consecutive_days} consecutive days.")
        preview = MineApply(
            leave_type_id=data.leave_type_id,
            from_date=data.from_date,
            to_date=data.to_date,
            is_half_day=data.is_half_day,
            half_day_part=data.half_day_part,
            reason="Preview",
        )
        skip_id = data.exclude_request_id
        if skip_id is not None:
            # Only the authenticated employee's own request may be excluded.
            self._own_request(employee.id, skip_id)
        self._assert_no_conflict(employee.id, preview, current_id=skip_id)
        return days

    def cancel(self, actor: CurrentUser, request_id: int) -> MineRequestDetail:
        employee = self._employee(actor, lock=True)
        row = self._own_request(employee.id, request_id)
        if row.status in ("Rejected", "Cancelled"):
            raise LeaveRuleError(f"A {row.status.lower()} request cannot be cancelled.")
        if row.status == "Approved" and not actor.can("hr.leave.manage"):
            raise Forbidden("Approved leave can only be cancelled by HR.")
        previous = row.status
        row.updated_by_user_id = actor.id
        if previous == "Approved":
            leave_type = self._db.get(LeaveType, row.leave_type_id)
            if leave_type is not None and leave_type.code == "CO":
                from trishul_api.modules.hr.leave.comp_off_ops import restore

                restore(
                    self._db,
                    employee_id=employee.id,
                    leave_type_id=row.leave_type_id,
                    leave_request_id=row.id,
                    user_id=actor.id,
                )
            else:
                self._restore(employee.id, row)
        row.status = "Cancelled"
        self.settle_approval(row.id, actor, "Cancelled", "Cancelled")
        self._history(row.id, previous, "Cancelled", "Cancelled", actor.id)
        self._db.commit()
        self._db.refresh(row)
        return self._detail(row)

    def _employee(self, actor: CurrentUser, *, lock: bool = False) -> Employee:
        if actor.employee_id is None:
            raise NotFound("Employee not found.")
        stmt = select(Employee).where(Employee.id == actor.employee_id)
        if lock and self._db.get_bind().dialect.name != "sqlite":
            stmt = stmt.with_for_update()
        employee = self._db.execute(stmt).scalar_one_or_none()
        if employee is None:
            raise NotFound("Employee not found.")
        return employee

    def _active(self, employee: Employee) -> None:
        if not employee.is_active or employee.status != "Active":
            raise LeaveRuleError("Employee not found.")

    def _validated_days(
        self,
        actor: CurrentUser,
        employee: Employee,
        data: MineApply,
        current_id: int | None,
        *,
        for_decision: bool = False,
    ) -> Decimal:
        if data.to_date < data.from_date:
            raise LeaveRuleError("Invalid date range.")
        if not for_decision:
            self._assert_backdate(
                actor, employee, data.leave_type_id, data.from_date, data.to_date, reason=data.reason
            )
        if data.is_half_day and (data.from_date != data.to_date or data.half_day_part is None):
            raise LeaveRuleError("Invalid half-day request.")
        if not data.is_half_day and data.half_day_part is not None:
            raise LeaveRuleError("Invalid half-day request.")
        leave_type = self._db.get(LeaveType, data.leave_type_id)
        if leave_type is None or not leave_type.is_active:
            raise LeaveRuleError("Leave type inactive.")
        setting = self._db.get(LeaveTypeSetting, leave_type.id)
        if data.is_half_day and setting is not None and not setting.half_day_allowed:
            raise LeaveRuleError("Invalid half-day request.")
        if setting is not None and setting.attachment_required:
            raise LeaveRuleError(
                "This leave type requires a supporting document. Leave requests cannot store a document yet."
            )
        policy = self._policy(employee, data.from_date)
        line = self._policy_line(policy.id, leave_type.id)
        if line is None:
            raise LeaveRuleError("This leave type is not included in the assigned leave policy.")
        if line.document_required:
            raise LeaveRuleError(
                "This leave type requires a supporting document. Leave requests cannot store a document yet."
            )
        served = _service_months(employee.date_of_joining, data.from_date)
        if line.minimum_service_months and served < line.minimum_service_months:
            raise LeaveRuleError("The minimum continuous service for this leave has not been completed.")
        if self._confirmed_on(employee.id, data.from_date) is None and not policy.applies_during_probation:
            raise LeaveRuleError("Employee not confirmed.")
        if not for_decision:
            medical = is_medical_emergency(data.reason)
            self._assert_al_notice(leave_type.code, data.from_date, medical=medical)
            self._assert_al_boundaries(employee, leave_type.code, data.from_date, data.to_date, line)
            if data.is_half_day:
                self._assert_half_day_duty(employee, data.from_date, data.half_day_part)
        days = self._days(
            employee,
            data.from_date,
            data.to_date,
            data.is_half_day,
            leave_type.code,
            leave_type.name,
            exclude_boundary=line.exclude_boundary_holidays,
        )
        if setting is not None and setting.max_consecutive_days is not None and days > setting.max_consecutive_days:
            raise LeaveRuleError(f"This leave type allows at most {setting.max_consecutive_days} consecutive days.")
        self._assert_no_conflict(employee.id, data, current_id)
        if leave_type.code == "CO":
            from trishul_api.modules.hr.leave.comp_off_ops import assert_available

            pending = self._pending_days(employee.id, *_year_bounds(_financial_year(data.from_date)), skip_id=current_id)
            assert_available(
                self._db, employee.id, leave_type.id, data.from_date, days, pending.get(leave_type.id, _ZERO)
            )
        elif leave_type.is_paid and not policy.negative_balance_allowed:
            self._enough(employee.id, leave_type.id, data.from_date, days, current_id)
        return days

    def _assert_backdate(
        self,
        actor: CurrentUser,
        employee: Employee,
        leave_type_id: int,
        start: date,
        end: date,
        reason: str | None = None,
    ) -> None:
        line = self._configured_lines(employee).get(leave_type_id)
        if line is None:
            return
        today = date.today()
        if is_medical_emergency(reason) and start <= today:
            previous = self._previous_working_day(employee, today)
            if previous is not None and start >= previous and end <= today:
                return
            if previous is not None and start < previous:
                raise LeaveRuleError(
                    f"Medical emergency leave can be applied from the previous working day ({previous.strftime('%d-%b-%Y')})."
                )
        message = backdate_rejection(
            today=today,
            start=start,
            end=end,
            max_backdate_days=line.max_backdate_days,
            requires_authorization=line.backdate_requires_authorization,
            hr_authorized=actor.can("hr.leave.manage"),
        )
        if message:
            raise LeaveRuleError(message)

    def _configured_lines(self, employee: Employee) -> dict[int, LeavePolicyLine]:
        policy = self._configured_policy(employee)
        if policy is None:
            return {}
        rows = self._db.scalars(
            select(LeavePolicyLine).where(
                LeavePolicyLine.leave_policy_id == policy.id,
                LeavePolicyLine.is_active == True,  # noqa: E712
            )
        ).all()
        return {row.leave_type_id: row for row in rows}

    def _configured_policy(self, employee: Employee) -> LeavePolicy | None:
        try:
            return self._policy(employee, date.today())
        except LeaveRuleError:
            assigned = self._db.scalars(
                select(LeavePolicy)
                .join(LeavePolicyAssignment, LeavePolicyAssignment.leave_policy_id == LeavePolicy.id)
                .where(
                    LeavePolicyAssignment.employee_id == employee.id,
                    LeavePolicyAssignment.is_active == True,  # noqa: E712
                    LeavePolicy.is_active == True,  # noqa: E712
                )
                .order_by(LeavePolicy.effective_from.desc(), LeavePolicy.id.desc())
            ).first()
            return assigned

    def _policy(self, employee: Employee, on: date) -> LeavePolicy:
        rows = self._db.execute(
            select(LeavePolicy).where(
                LeavePolicy.is_active == True,  # noqa: E712
                LeavePolicy.effective_from <= on,
                or_(LeavePolicy.effective_to.is_(None), LeavePolicy.effective_to >= on),
            )
        ).scalars().all()
        assigned = set(
            self._db.scalars(
                select(LeavePolicyAssignment.leave_policy_id).where(
                    LeavePolicyAssignment.employee_id == employee.id,
                    LeavePolicyAssignment.is_active == True,  # noqa: E712
                    LeavePolicyAssignment.effective_from <= on,
                    or_(LeavePolicyAssignment.effective_to.is_(None), LeavePolicyAssignment.effective_to >= on),
                )
            ).all()
        )
        branch_state = self._db.scalar(select(Branch.state_id).where(Branch.id == employee.branch_id))
        ranked = [row for row in rows if row.id in assigned or _policy_fits(row, employee, branch_state)]
        if not ranked:
            raise LeaveRuleError("Leave policy not assigned.")
        return max(ranked, key=lambda row: (_policy_score(row), row.effective_from, row.id))

    def _policy_line(self, policy_id: int, leave_type_id: int) -> LeavePolicyLine | None:
        return self._db.scalar(
            select(LeavePolicyLine).where(
                LeavePolicyLine.leave_policy_id == policy_id,
                LeavePolicyLine.leave_type_id == leave_type_id,
                LeavePolicyLine.is_active == True,  # noqa: E712
            )
        )

    def _days(
        self,
        employee: Employee,
        start: date,
        end: date,
        half: bool,
        leave_code: str = "",
        leave_name: str = "",
        *,
        exclude_boundary: bool | None = None,
    ) -> Decimal:
        off = self._weekly_off(employee.id, start)
        holidays = self._holiday_dates(employee.branch_id, start, end)
        if half:
            if start.weekday() in off or start in holidays:
                raise LeaveRuleError("Invalid half-day request.")
            return _HALF
        annual = _counts_intervening(leave_code, leave_name, exclude_boundary=exclude_boundary)
        cursor = start
        count = 0
        while cursor <= end:
            if annual or (cursor.weekday() not in off and cursor not in holidays):
                count += 1
            cursor += timedelta(days=1)
        if count == 0:
            raise LeaveRuleError("The selected dates are weekly offs or holidays.")
        return Decimal(count).quantize(Decimal("0.1"))

    def _assert_al_notice(self, leave_code: str, start: date, *, medical: bool) -> None:
        if leave_code.strip().upper() != "AL" or medical:
            return
        earliest = date.today() + timedelta(days=_AL_NOTICE_DAYS)
        if start < earliest:
            raise LeaveRuleError(
                f"Annual Leave normally requires {_AL_NOTICE_DAYS} days' prior application "
                f"(earliest {earliest.strftime('%d-%b-%Y')}), except medical emergency."
            )

    def _assert_al_boundaries(
        self, employee: Employee, leave_code: str, start: date, end: date, line: LeavePolicyLine
    ) -> None:
        """AL cannot be prefixed or suffixed to a holiday or weekly off."""
        if leave_code.strip().upper() not in _ANNUAL:
            return
        if line.exclude_boundary_holidays:
            return
        before = start - timedelta(days=1)
        after = end + timedelta(days=1)
        off = self._weekly_off(employee.id, start)
        holidays = self._holiday_dates(employee.branch_id, before, after)
        if before.weekday() in off or before in holidays:
            raise LeaveRuleError("Annual Leave cannot be prefixed to a holiday or weekly off.")
        if after.weekday() in off or after in holidays:
            raise LeaveRuleError("Annual Leave cannot be suffixed to a holiday or weekly off.")

    def _assert_half_day_duty(self, employee: Employee, on: date, part: str | None) -> None:
        """Past/today half-day leave requires at least four hours of duty on the remaining half."""
        if on > date.today():
            return
        punches = self._db.execute(
            select(BiometricPunchLog.punched_at, BiometricPunchLog.punch_type)
            .where(
                BiometricPunchLog.employee_id == employee.id,
                BiometricPunchLog.is_active == True,  # noqa: E712
                BiometricPunchLog.punched_at >= datetime.combine(on, time.min),
                BiometricPunchLog.punched_at <= datetime.combine(on, time.max),
            )
            .order_by(BiometricPunchLog.punched_at, BiometricPunchLog.id)
        ).all()
        pairs = [(row[0], row[1] or "IN") for row in punches]
        shift = self._db.execute(
            select(EmployeeShift, Shift)
            .join(Shift, Shift.id == EmployeeShift.shift_id)
            .where(
                EmployeeShift.employee_id == employee.id,
                EmployeeShift.is_active == True,  # noqa: E712
                EmployeeShift.from_date <= on,
                or_(EmployeeShift.to_date.is_(None), EmployeeShift.to_date >= on),
            )
            .order_by(EmployeeShift.from_date.desc(), EmployeeShift.id.desc())
            .limit(1)
        ).first()
        start_t = shift[1].start_time if shift is not None else time(9, 30)
        end_t = shift[1].end_time if shift is not None else time(18, 30)
        worked = net_worked_minutes(pairs, on, shift_start=start_t, shift_end=end_t)
        if worked < _HALF_DAY_MINUTES:
            label = part or "half day"
            raise LeaveRuleError(
                f"Half-day leave ({label}) requires at least four hours of duty before or after leave. "
                f"Recorded duty on {on.strftime('%d-%b-%Y')} is {worked // 60}h {worked % 60:02d}m."
            )

    def _previous_working_day(self, employee: Employee, on: date) -> date | None:
        off = self._weekly_off(employee.id, on)
        cursor = on - timedelta(days=1)
        for _ in range(14):
            holidays = self._holiday_dates(employee.branch_id, cursor, cursor)
            if cursor.weekday() not in off and cursor not in holidays:
                return cursor
            cursor -= timedelta(days=1)
        return None

    def _assert_no_conflict(self, employee_id: int, data: MineApply, current_id: int | None) -> None:
        """Block Pending/Approved overlaps; Rejected/Cancelled do not block reapplication."""
        rows = list(
            self._db.execute(
                select(LeaveRequest).where(
                    LeaveRequest.employee_id == employee_id,
                    LeaveRequest.is_active == True,  # noqa: E712
                    LeaveRequest.status.in_(("Pending", "Approved")),
                    LeaveRequest.from_date <= data.to_date,
                    LeaveRequest.to_date >= data.from_date,
                )
            ).scalars().all()
        )
        type_ids = {row.leave_type_id for row in rows}
        type_ids.add(data.leave_type_id)
        names = {
            row.id: row.name
            for row in self._db.scalars(select(LeaveType).where(LeaveType.id.in_(type_ids))).all()
        } if type_ids else {}
        message = conflict_message(
            leave_type_id=data.leave_type_id,
            from_date=data.from_date,
            to_date=data.to_date,
            is_half_day=data.is_half_day,
            existing=rows,
            skip_id=current_id,
            type_names=names,
        )
        if message:
            raise LeaveRuleError(message)

    def _enough(self, employee_id: int, leave_type_id: int, start: date, days: Decimal, current_id: int | None) -> None:
        year = _financial_year(start)
        latest = self._latest_balances(employee_id, year).get(leave_type_id)
        available = latest.closing if latest else _ZERO
        pending = self._pending_days(employee_id, *_year_bounds(year), skip_id=current_id).get(leave_type_id, _ZERO)
        if available - pending < days:
            raise LeaveRuleError("Insufficient balance.")

    def _restore(self, employee_id: int, row: LeaveRequest) -> None:
        year = _financial_year(row.from_date)
        balance = self._latest_balances(employee_id, year).get(row.leave_type_id)
        if balance is None:
            raise LeaveRuleError("No leave balance row exists to restore for this approved request.")
        removed = min(balance.availed or _ZERO, row.days)
        balance.availed = (balance.availed or _ZERO) - removed
        balance.closing = (balance.closing or _ZERO) + removed
        balance.updated_by_user_id = row.updated_by_user_id

    def _latest_balances(self, employee_id: int, year: int) -> dict[int, LeaveBalance]:
        rows = self._db.execute(
            select(LeaveBalance)
            .where(
                LeaveBalance.employee_id == employee_id,
                LeaveBalance.leave_year == year,
                LeaveBalance.is_active == True,  # noqa: E712
            )
            .order_by(LeaveBalance.id)
        ).scalars().all()
        return {row.leave_type_id: row for row in rows}

    def _pending_days(
        self, employee_id: int, start: date, end: date, skip_id: int | None = None
    ) -> dict[int, Decimal]:
        rows = self._db.execute(
            select(LeaveRequest.leave_type_id, LeaveRequest.days, LeaveRequest.id).where(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.is_active == True,  # noqa: E712
                LeaveRequest.status == "Pending",
                LeaveRequest.from_date >= start,
                LeaveRequest.from_date <= end,
            )
        ).all()
        totals: dict[int, Decimal] = {}
        for leave_type_id, days, row_id in rows:
            if row_id == skip_id:
                continue
            totals[leave_type_id] = totals.get(leave_type_id, _ZERO) + days
        return totals

    def _weekly_off(self, employee_id: int, on: date) -> set[int]:
        text = self._db.execute(
            select(EmployeeShift.weekly_off_days)
            .where(
                EmployeeShift.employee_id == employee_id,
                EmployeeShift.is_active == True,  # noqa: E712
                EmployeeShift.from_date <= on,
                or_(EmployeeShift.to_date.is_(None), EmployeeShift.to_date >= on),
            )
            .order_by(EmployeeShift.from_date.desc(), EmployeeShift.id.desc())
            .limit(1)
        ).scalar()
        return _off_days(text)

    def _holiday_dates(self, branch_id: int, start: date, end: date) -> set[date]:
        state_id = self._db.scalar(select(Branch.state_id).where(Branch.id == branch_id))
        rows = self._db.execute(
            select(Holiday.holiday_date).where(
                Holiday.is_active == True,  # noqa: E712
                Holiday.holiday_type != "Optional",
                Holiday.holiday_date >= start,
                Holiday.holiday_date <= end,
                applies_to_branch(branch_id, state_id),
            )
        ).all()
        return {row[0] for row in rows}

    def _confirmed_on(self, employee_id: int, on: date) -> date | None:
        return self._db.execute(
            select(func.max(EmploymentHistory.effective_date)).where(
                EmploymentHistory.employee_id == employee_id,
                EmploymentHistory.event_type == "Confirmed",
                EmploymentHistory.is_active == True,  # noqa: E712
                EmploymentHistory.effective_date <= on,
            )
        ).scalar()

    def _own_requests(self, employee_id: int, financial_year: int) -> list[LeaveRequest]:
        start, end = _year_bounds(financial_year)
        return list(
            self._db.execute(
                select(LeaveRequest)
                .where(
                    LeaveRequest.employee_id == employee_id,
                    LeaveRequest.is_active == True,  # noqa: E712
                    LeaveRequest.from_date >= start,
                    LeaveRequest.from_date <= end,
                )
                .order_by(LeaveRequest.id.desc())
            ).scalars().all()
        )

    def _own_request(self, employee_id: int, request_id: int) -> LeaveRequest:
        row = self._db.get(LeaveRequest, request_id)
        if row is None or not row.is_active or row.employee_id != employee_id:
            raise NotFound("Leave request not found.")
        return row

    def _history(self, request_id: int, previous: str | None, status: str, remarks: str, user_id: int) -> None:
        self._db.add(
            StatusHistory(
                entity_type="hr.leave_request",
                entity_id=request_id,
                from_status=previous,
                to_status=status,
                changed_by_user_id=user_id,
                changed_at=datetime.now(UTC).replace(tzinfo=None),
                remarks=remarks,
            )
        )

    def _item(
        self,
        row: LeaveRequest,
        steps: list[ApprovalRequest] | None = None,
        people: dict[int, tuple[str, str]] | None = None,
    ) -> MineRequestItem:
        leave_type = self._db.get(LeaveType, row.leave_type_id)
        label = f"{leave_type.name} ({leave_type.code})" if leave_type else "Leave"
        pending_name, pending_role, needs_hr, level = _pending_with(row, steps or [], people or {})
        return MineRequestItem(
            request_id=row.id,
            display_id=f"LV-{row.id:04d}",
            leave_type_id=row.leave_type_id,
            leave_type=label,
            from_date=row.from_date,
            to_date=row.to_date,
            days=row.days,
            reason=row.reason,
            applied_at=row.created_at,
            status=row.status,
            is_half_day=row.is_half_day,
            approver_user_id=row.approver_user_id,
            acted_at=row.acted_at,
            current_approval_level=level,
            pending_with_name=pending_name,
            pending_with_role=pending_role,
            needs_hr_attention=needs_hr,
        )

    def _detail(self, row: LeaveRequest) -> MineRequestDetail:
        events = self._db.execute(
            select(StatusHistory)
            .where(StatusHistory.entity_type == "hr.leave_request", StatusHistory.entity_id == row.id)
            .order_by(StatusHistory.changed_at, StatusHistory.id)
        ).scalars().all()
        history = [
            MineStatusEvent(
                from_status=event.from_status,
                to_status=event.to_status,
                changed_at=event.changed_at,
                remarks=event.remarks,
            )
            for event in events
        ]
        if row.acted_at is not None and row.status in ("Approved", "Rejected") and not any(
            event.to_status == row.status for event in history
        ):
            history.append(
                MineStatusEvent(
                    from_status="Pending",
                    to_status=row.status,
                    changed_at=row.acted_at,
                    remarks=None,
                )
            )
        steps = self._ensure_steps([row]).get(row.id, [])
        people = self._approver_people({step.approver_user_id for step in steps})
        return MineRequestDetail(
            **self._item(row, steps, people).model_dump(),
            history=history,
            approval_steps=_timeline(row, steps, people),
        )

    def open_approval(self, request_id: int) -> ApprovalRequest | None:
        return next((step for step in self._steps(request_id) if step.status == "Pending"), None)

    def has_approval(self, request_id: int) -> bool:
        return bool(self._steps(request_id))

    def advance_approval(self, request_id: int, actor: CurrentUser, remarks: str) -> bool:
        """Mark the Reporting Manager step approved.

        TTPL leave policy: the Reporting Manager is the final approver. Any later pending
        levels from an older multi-level snapshot are cancelled so the request finalizes
        immediately. Always returns False (no further leave levels remain).
        """
        steps = self._steps(request_id)
        current = next((step for step in steps if step.status == "Pending"), None)
        if current is None:
            return False
        now = datetime.now(UTC).replace(tzinfo=None)
        current.status = "Approved"
        if current.approver_user_id is None:
            current.approver_user_id = actor.id
        current.acted_at = now
        current.remarks = remarks[:500]
        current.updated_by_user_id = actor.id
        self._history(
            request_id, "Pending", "Pending", "Approved by Reporting Manager.", actor.id
        )
        for step in steps:
            if step.id == current.id or step.status != "Pending":
                continue
            step.status = "Cancelled"
            step.acted_at = now
            step.remarks = "Superseded: Reporting Manager is the final leave approver."
            step.updated_by_user_id = actor.id
        return False

    def settle_approval(self, request_id: int, actor: CurrentUser, status: str, remarks: str) -> None:
        """Close the open level and cancel every later level. No stored steps is a no-op."""
        now = datetime.now(UTC).replace(tzinfo=None)
        closed_current = False
        for step in self._steps(request_id):
            if step.status != "Pending":
                continue
            step.acted_at = now
            step.updated_by_user_id = actor.id
            if not closed_current:
                step.status = status
                step.remarks = remarks[:500]
                if step.approver_user_id is None and status == "Rejected":
                    step.approver_user_id = actor.id
                closed_current = True
            else:
                step.status = "Cancelled"

    def _ensure_steps(self, rows: list[LeaveRequest]) -> dict[int, list[ApprovalRequest]]:
        """Read the approvers stored on each request. A pending request with none is stored once."""
        steps = self._steps_for([row.id for row in rows])
        changed = False
        for row in rows:
            if row.status != "Pending":
                continue
            existing = steps.get(row.id, [])
            if existing:
                if self._prune_extra_leave_levels(existing):
                    changed = True
                continue
            employee = self._db.get(Employee, row.employee_id)
            user_id = self._requester_id(row, employee)
            if employee is None or user_id is None:
                continue
            if self._snapshot_approvers(employee, row.id, user_id):
                changed = True
        if changed:
            self._db.commit()
            steps = self._steps_for([row.id for row in rows])
        return steps

    def _prune_extra_leave_levels(self, steps: list[ApprovalRequest]) -> bool:
        """Cancel pending Level 2+ leave steps left from the old multi-level chain."""
        now = datetime.now(UTC).replace(tzinfo=None)
        changed = False
        for step in steps:
            if step.approval_level <= 1 or step.status != "Pending":
                continue
            step.status = "Cancelled"
            step.acted_at = now
            step.remarks = "Superseded: Reporting Manager is the final leave approver."
            changed = True
        return changed

    def _require_reporting_manager(self, employee: Employee) -> None:
        manager_id = employee.reporting_manager_id
        if manager_id is None or manager_id == employee.id:
            raise LeaveRuleError("Leave cannot be submitted without a Reporting Manager.")
        manager = self._db.get(Employee, manager_id)
        if manager is None or not manager.is_active:
            raise LeaveRuleError("Leave cannot be submitted without a Reporting Manager.")

    def _requester_id(self, row: LeaveRequest, employee: Employee | None) -> int | None:
        if row.created_by_user_id is not None:
            return row.created_by_user_id
        if employee is None:
            return None
        return self._db.scalar(
            select(AppUser.id)
            .where(AppUser.employee_id == employee.id, AppUser.is_active == True)  # noqa: E712
            .order_by(AppUser.id)
        )

    def _snapshot_approvers(self, employee: Employee, request_id: int, user_id: int) -> bool:
        """Store the Reporting Manager as the sole leave approver (TTPL policy)."""
        manager_id = employee.reporting_manager_id
        if manager_id is None or manager_id == employee.id:
            raise LeaveRuleError("Leave cannot be submitted without a Reporting Manager.")
        manager = self._db.get(Employee, manager_id)
        if manager is None or not manager.is_active:
            raise LeaveRuleError("Leave cannot be submitted without a Reporting Manager.")
        user = self._db.scalar(
            select(AppUser)
            .where(AppUser.employee_id == manager.id, AppUser.is_active == True)  # noqa: E712
            .order_by(AppUser.id)
        )
        now = datetime.now(UTC).replace(tzinfo=None)
        self._db.add(
            ApprovalRequest(
                document_type=_DOCUMENT,
                document_id=request_id,
                approval_level=1,
                requested_by_user_id=user_id,
                requested_at=now,
                approver_user_id=user.id if user is not None else None,
                status="Pending",
                created_at=now,
                created_by_user_id=user_id,
                is_active=True,
            )
        )
        return True

    def _steps(self, request_id: int) -> list[ApprovalRequest]:
        return self._steps_for([request_id]).get(request_id, [])

    def _steps_for(self, request_ids: list[int]) -> dict[int, list[ApprovalRequest]]:
        if not request_ids:
            return {}
        rows = self._db.scalars(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.document_type == _DOCUMENT,
                ApprovalRequest.document_id.in_(request_ids),
                ApprovalRequest.is_active == True,  # noqa: E712
            )
            .order_by(ApprovalRequest.approval_level, ApprovalRequest.id)
        ).all()
        grouped: dict[int, list[ApprovalRequest]] = {}
        for step in rows:
            grouped.setdefault(step.document_id, []).append(step)
        return grouped

    def _approver_people(self, user_ids: set[int | None]) -> dict[int, tuple[str, str]]:
        ids = {user_id for user_id in user_ids if user_id is not None}
        if not ids:
            return {}
        rows = self._db.execute(
            select(AppUser, Employee, Designation.name)
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .outerjoin(Designation, Designation.id == Employee.designation_id)
            .where(AppUser.id.in_(ids))
        ).all()
        people: dict[int, tuple[str, str]] = {}
        for user, employee, designation in rows:
            if employee is None:
                name = user.username
            else:
                name = " ".join(part for part in (employee.first_name, employee.last_name) if part) or user.username
            people[user.id] = (name, designation or "Reporting manager")
        return people

    def _name(self, model: type[Department] | type[Designation] | type[Branch], row_id: int | None) -> str | None:
        if row_id is None:
            return None
        row = self._db.get(model, row_id)
        return row.name if row is not None else None


def _year_bounds(financial_year: int) -> tuple[date, date]:
    return date(financial_year, 4, 1), date(financial_year + 1, 3, 31)


def _financial_year(day: date) -> int:
    return day.year if day.month >= 4 else day.year - 1


def _off_days(text: str | None) -> set[int]:
    if not text:
        return {6}
    days = {_WEEKDAY[part.strip().upper()] for part in text.split(",") if part.strip().upper() in _WEEKDAY}
    return days or {6}


def _service_months(joining: date | None, on: date) -> int:
    if joining is None or on < joining:
        return 0
    months = (on.year - joining.year) * 12 + on.month - joining.month
    if on.day < joining.day:
        months -= 1
    return months


def _policy_fits(policy: LeavePolicy, employee: Employee, branch_state_id: int | None) -> bool:
    if policy.assignment_mode == "EXPLICIT":
        return False
    if policy.employee_type is not None and policy.employee_type != employee.employee_type:
        return False
    if policy.department_id is not None and policy.department_id != employee.department_id:
        return False
    if policy.branch_id is not None and policy.branch_id != employee.branch_id:
        return False
    return policy.state_id is None or policy.state_id == branch_state_id


def _policy_score(policy: LeavePolicy) -> int:
    return int(policy.employee_type is not None) + int(policy.department_id is not None) * 2 + int(
        policy.branch_id is not None
    ) * 4


def _pending_with(
    row: LeaveRequest, steps: list[ApprovalRequest], people: dict[int, tuple[str, str]]
) -> tuple[str | None, str | None, bool, str | None]:
    if row.status != "Pending":
        return None, None, False, None
    current = next((step for step in steps if step.status == "Pending"), None)
    if current is None or current.approver_user_id is None or current.approver_user_id not in people:
        return "Awaiting Assignment", "Reporting Manager", True, "Reporting Manager"
    name, _role = people[current.approver_user_id]
    return name, "Reporting Manager", False, "Reporting Manager"


def _timeline(
    row: LeaveRequest, steps: list[ApprovalRequest], people: dict[int, tuple[str, str]]
) -> list[MineApprovalStep]:
    """TTPL leave timeline: Request Submitted → Reporting Manager → Approved/Rejected."""
    items = [
        MineApprovalStep(
            title="Request Submitted",
            approver_name=None,
            approver_role=None,
            level=None,
            status="Submitted",
            acted_at=row.created_at,
            comments=row.reason,
        )
    ]
    # Prefer the acted Level-1 / Reporting Manager step; ignore cancelled higher levels.
    manager_step = next((step for step in steps if step.approval_level == 1), None)
    if manager_step is None:
        manager_step = next((step for step in steps if step.status != "Cancelled"), None)
    if manager_step is None and row.status == "Pending":
        items.append(
            MineApprovalStep(
                title="Reporting Manager",
                approver_name=None,
                approver_role="Reporting Manager",
                level="Reporting Manager",
                status="Pending",
                acted_at=None,
                comments=None,
            )
        )
        items.append(
            MineApprovalStep(
                title="Approved / Rejected",
                approver_name=None,
                approver_role=None,
                level=None,
                status="Upcoming",
                acted_at=None,
                comments=None,
            )
        )
        return items

    if manager_step is not None:
        person = people.get(manager_step.approver_user_id) if manager_step.approver_user_id is not None else None
        if row.status == "Pending" and manager_step.status == "Pending":
            manager_status = "Pending"
        elif manager_step.status == "Approved":
            manager_status = "Approved"
        elif manager_step.status == "Rejected":
            manager_status = "Rejected"
        else:
            manager_status = manager_step.status if manager_step.status != "Cancelled" else "Pending"
        items.append(
            MineApprovalStep(
                title="Reporting Manager",
                approver_name=person[0] if person else None,
                approver_role="Reporting Manager",
                level="Reporting Manager",
                status=manager_status,
                acted_at=manager_step.acted_at,
                comments=manager_step.remarks,
            )
        )

    if row.status == "Approved":
        items.append(
            MineApprovalStep(
                title="Approved",
                approver_name=None,
                approver_role=None,
                level=None,
                status="Approved",
                acted_at=row.acted_at,
                comments=None,
            )
        )
    elif row.status == "Rejected":
        items.append(
            MineApprovalStep(
                title="Rejected",
                approver_name=None,
                approver_role=None,
                level=None,
                status="Rejected",
                acted_at=row.acted_at,
                comments=None,
            )
        )
    else:
        items.append(
            MineApprovalStep(
                title="Approved / Rejected",
                approver_name=None,
                approver_role=None,
                level=None,
                status="Upcoming",
                acted_at=None,
                comments=None,
            )
        )
    return items


def _matches(row: LeaveRequest, query: MineRequestQuery) -> bool:
    if query.leave_type_id is not None and row.leave_type_id != query.leave_type_id:
        return False
    if query.status is not None and row.status != query.status:
        return False
    if query.from_date is not None and row.from_date < query.from_date:
        return False
    if query.to_date is not None and row.from_date > query.to_date:
        return False
    if not query.search:
        return True
    term = query.search.strip().lower()
    display = f"lv-{row.id:04d}"
    return term in display or term == str(row.id) or term in (row.reason or "").lower()
