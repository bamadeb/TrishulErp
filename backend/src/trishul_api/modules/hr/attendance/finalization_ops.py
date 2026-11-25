"""Monthly attendance finalization overview and lock.

Computes department/location readiness from the same muster, exception and
regularization sources as the other attendance screens. The lock is stored in
``core.system_setting`` (key ``hr.attendance.finalization.YYYY-MM``) so no new
table is required and payroll keeps using ``hr.payroll_run`` independently.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError, Conflict
from trishul_api.db.models import SystemSetting
from trishul_api.modules.hr.attendance.schemas import (
    AttendanceExceptionsQuery,
    FinalizationChecklistItemOut,
    FinalizationGroupBy,
    FinalizationGroupRowOut,
    FinalizationKpiOut,
    FinalizationLockOut,
    FinalizationPageOut,
    FinalizationQuery,
    FinalizationRowStatus,
    FinalizationSummaryOut,
    MonthlyMusterQuery,
    MusterEmployeeRowOut,
    RegularizationQuery,
)
SETTING_PREFIX = "hr.attendance.finalization."
_SETTING_PREFIX = SETTING_PREFIX
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


class FinalizationService:
    def __init__(self, db: Session) -> None:
        # Lazy import avoids circular dependency with attendance.service
        # (service imports require_day_writable from this module).
        from trishul_api.modules.hr.attendance.service import AttendanceService

        self._db = db
        self._attendance = AttendanceService(db)

    def overview(self, query: FinalizationQuery) -> FinalizationPageOut:
        year, month = query.year, query.month
        start, end = _month_bounds(year, month)
        label = f"{_MONTH_LABELS[month - 1]} {year}"

        employees = self._all_muster_employees(year, month)
        pending_exception_ids = self._pending_exception_employee_ids(start, end)
        pending_reg_ids = self._pending_regularization_employee_ids(start, end)

        groups = self._group_rows(
            employees,
            pending_exception_ids,
            pending_reg_ids,
            group_by=query.group_by,
        )

        total = len(employees)
        with_exceptions = len(pending_exception_ids & {row.employee_id for row in employees})
        pending_reg = len(pending_reg_ids & {row.employee_id for row in employees})
        ready_ids = {
            row.employee_id
            for row in employees
            if row.employee_id not in pending_exception_ids and row.employee_id not in pending_reg_ids
        }
        attendance_ready = len(ready_ids)

        lock = self._load_lock(year, month)
        is_finalized = lock is not None
        finalized_count = total if is_finalized else 0

        summary = FinalizationSummaryOut(
            year=year,
            month=month,
            month_label=label,
            total_employees=total,
            attendance_ready=attendance_ready,
            attendance_ready_pct=_pct(attendance_ready, total),
            with_exceptions=with_exceptions,
            with_exceptions_pct=_pct(with_exceptions, total),
            pending_regularization=pending_reg,
            pending_regularization_pct=_pct(pending_reg, total),
            is_finalized=is_finalized,
            finalized_at=_parse_dt(lock.get("finalizedAt")) if lock else None,
            finalized_by_user_id=int(lock["finalizedByUserId"]) if lock and lock.get("finalizedByUserId") else None,
        )
        checklist = self._checklist(
            employees=employees,
            pending_exception_ids=pending_exception_ids,
            pending_reg_ids=pending_reg_ids,
            groups=groups,
            end=end,
        )
        can_finalize = (not is_finalized) and all(item.done for item in checklist) and total > 0

        return FinalizationPageOut(
            year=year,
            month=month,
            group_by=query.group_by,
            kpi=FinalizationKpiOut(
                total_employees=total,
                attendance_ready=attendance_ready,
                with_exceptions=with_exceptions,
                pending_regularization=pending_reg,
                finalized=finalized_count,
            ),
            summary=summary,
            checklist=checklist,
            groups=groups,
            can_finalize=can_finalize,
            is_finalized=is_finalized,
        )

    def finalize(self, actor: CurrentUser, year: int, month: int) -> FinalizationLockOut:
        page = self.overview(FinalizationQuery(year=year, month=month, group_by="department"))
        label = page.summary.month_label
        if page.is_finalized:
            raise ApiError(f"Attendance for {label} is already finalized.")
        if page.summary.total_employees == 0:
            raise ApiError("There are no active employees to finalize for this month.")
        incomplete = [item.label for item in page.checklist if not item.done]
        if incomplete:
            raise ApiError(
                "Cannot finalize until the checklist is complete: " + "; ".join(incomplete)
            )

        payload = {
            "year": year,
            "month": month,
            "finalizedAt": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "finalizedByUserId": actor.id,
            "employeeCount": page.summary.total_employees,
            "attendanceReady": page.summary.attendance_ready,
            "withExceptions": page.summary.with_exceptions,
            "pendingRegularization": page.summary.pending_regularization,
        }
        # Persist computed days into hr.attendance so payroll LOP reads real statuses.
        persisted = self._attendance.materialize_month(actor, year, month)
        payload["persistedDays"] = persisted
        self._save_lock(actor, year, month, payload)
        self._db.commit()
        self._db.expire_all()
        return FinalizationLockOut(
            year=year,
            month=month,
            month_label=label,
            is_finalized=True,
            finalized_at=_parse_dt(payload["finalizedAt"]),
            finalized_by_user_id=actor.id,
            employee_count=page.summary.total_employees,
            persisted_days=persisted,
            message=(
                f"Attendance for {label} is finalized and locked "
                f"({persisted} day record(s) saved for payroll)."
            ),
        )

    def _all_muster_employees(self, year: int, month: int) -> list[MusterEmployeeRowOut]:
        items: list[MusterEmployeeRowOut] = []
        page = 1
        while True:
            result = self._attendance.list_muster(
                MonthlyMusterQuery(
                    year=year,
                    month=month,
                    page=page,
                    page_size=200,
                    employment_status="Active",
                )
            )
            items.extend(result.items)
            if len(items) >= result.total or not result.items:
                break
            page += 1
            if page > 50:
                break
        return items

    def _pending_exception_employee_ids(self, start: date, end: date) -> set[int]:
        ids: set[int] = set()
        page = 1
        while True:
            result = self._attendance.list_exceptions(
                AttendanceExceptionsQuery(
                    date_from=start,
                    date_to=end,
                    page=page,
                    page_size=200,
                    status_tab="pending",
                )
            )
            for row in result.items:
                ids.add(row.employee_id)
            if page * 200 >= result.total or not result.items:
                break
            page += 1
            if page > 50:
                break
        return ids

    def _pending_regularization_employee_ids(self, start: date, end: date) -> set[int]:
        ids: set[int] = set()
        page = 1
        while True:
            result = self._attendance.list_regularizations(
                RegularizationQuery(
                    date_from=start,
                    date_to=end,
                    page=page,
                    page_size=200,
                    status_tab="pending",
                )
            )
            for row in result.items:
                ids.add(row.employee_id)
            if page * 200 >= result.total or not result.items:
                break
            page += 1
            if page > 50:
                break
        return ids

    def _group_rows(
        self,
        employees: list[MusterEmployeeRowOut],
        pending_exception_ids: set[int],
        pending_reg_ids: set[int],
        *,
        group_by: FinalizationGroupBy,
    ) -> list[FinalizationGroupRowOut]:
        buckets: dict[str, list[MusterEmployeeRowOut]] = defaultdict(list)
        for row in employees:
            key = row.department if group_by == "department" else row.location
            buckets[key or "—"].append(row)

        groups: list[FinalizationGroupRowOut] = []
        for index, name in enumerate(sorted(buckets), start=1):
            members = buckets[name]
            present = absent = leave = exceptions = pending_reg = 0
            ready = 0
            for member in members:
                has_exc = member.employee_id in pending_exception_ids
                has_reg = member.employee_id in pending_reg_ids
                if has_exc:
                    exceptions += 1
                if has_reg:
                    pending_reg += 1
                if has_exc:
                    pass  # counted under exceptions; still classify attendance below for totals
                if member.leave > member.absent and member.leave > 0:
                    leave += 1
                elif member.absent > 0 and member.absent >= max(member.present, 1):
                    absent += 1
                else:
                    present += 1
                if not has_exc and not has_reg:
                    ready += 1

            total = len(members)
            readiness = round((ready / total) * 100) if total else 0
            status = _group_status(readiness, exceptions, pending_reg)
            groups.append(
                FinalizationGroupRowOut(
                    id=index,
                    name=name,
                    employees=total,
                    present=present,
                    absent=absent,
                    leave=leave,
                    exceptions=exceptions,
                    pending_regularization=pending_reg,
                    readiness=readiness,
                    status=status,
                )
            )
        return groups

    def _checklist(
        self,
        *,
        employees: list[MusterEmployeeRowOut],
        pending_exception_ids: set[int],
        pending_reg_ids: set[int],
        groups: list[FinalizationGroupRowOut],
        end: date,
    ) -> list[FinalizationChecklistItemOut]:
        today = date.today()
        through = min(end, today)
        processed = True
        detail_processed = "All active employees are included in the monthly muster."
        if through >= date(through.year, through.month, 1) and employees:
            # A working day in the past with zero attendance codes beyond OFF/H for everyone
            # still counts as processed because muster always emits a code per day.
            detail_processed = f"Muster covers {len(employees)} active employee(s) through {through.isoformat()}."
        elif not employees:
            processed = False
            detail_processed = "No active employees found for this month."

        exceptions_done = len(pending_exception_ids) == 0
        regs_done = len(pending_reg_ids) == 0
        all_ready = bool(groups) and all(g.status == "Ready" for g in groups)
        no_pending = bool(groups) and all(g.status != "Pending" for g in groups)

        return [
            FinalizationChecklistItemOut(
                id="processed",
                label="Attendance processed for all employees",
                done=processed,
                detail=detail_processed,
            ),
            FinalizationChecklistItemOut(
                id="exceptions",
                label="Exceptions reviewed",
                done=exceptions_done,
                detail=(
                    "No pending exceptions."
                    if exceptions_done
                    else f"{len(pending_exception_ids)} employee(s) still have pending exceptions."
                ),
            ),
            FinalizationChecklistItemOut(
                id="regularization",
                label="Regularization requests approved",
                done=regs_done,
                detail=(
                    "No pending regularization requests."
                    if regs_done
                    else f"{len(pending_reg_ids)} employee(s) still have pending requests."
                ),
            ),
            FinalizationChecklistItemOut(
                id="ready",
                label="All departments marked as Ready",
                done=all_ready,
                detail=(
                    "Every group is Ready."
                    if all_ready
                    else f"{sum(1 for g in groups if g.status != 'Ready')} group(s) still need review."
                ),
            ),
            FinalizationChecklistItemOut(
                id="pending",
                label="No pending attendance data",
                done=no_pending,
                detail=(
                    "No group is in Pending status."
                    if no_pending
                    else f"{sum(1 for g in groups if g.status == 'Pending')} group(s) are Pending."
                ),
            ),
        ]

    def _setting_key(self, year: int, month: int) -> str:
        return f"{_SETTING_PREFIX}{year:04d}-{month:02d}"

    def _load_lock(self, year: int, month: int) -> dict[str, Any] | None:
        row = self._db.scalar(
            select(SystemSetting).where(
                SystemSetting.setting_key == self._setting_key(year, month),
                SystemSetting.company_id.is_(None),
                SystemSetting.is_active == True,  # noqa: E712
            )
        )
        if row is None or not row.setting_value:
            return None
        try:
            data = json.loads(row.setting_value)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) and data.get("finalizedAt") else None

    def _save_lock(self, actor: CurrentUser, year: int, month: int, payload: dict[str, Any]) -> None:
        key = self._setting_key(year, month)
        body = json.dumps(payload, separators=(",", ":"))
        row = self._db.scalar(
            select(SystemSetting).where(
                SystemSetting.setting_key == key,
                SystemSetting.company_id.is_(None),
            )
        )
        if row is None:
            self._db.execute(
                SystemSetting.__table__.insert().values(
                    company_id=None,
                    setting_key=key,
                    setting_value=body,
                    data_type="JSON",
                    description=f"Attendance finalization lock for {year}-{month:02d}",
                    created_by_user_id=actor.id,
                    is_active=True,
                )
            )
            return
        updated = self._db.execute(
            SystemSetting.__table__.update()
            .where(SystemSetting.id == row.id)
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


def load_finalization_lock(db: Session, year: int, month: int) -> dict[str, Any] | None:
    """Shared lock reader for payroll gate and attendance screens."""
    return FinalizationService(db)._load_lock(year, month)


def is_month_finalized(db: Session, year: int, month: int) -> bool:
    return load_finalization_lock(db, year, month) is not None


def require_month_finalized(db: Session, year: int, month: int) -> None:
    if is_month_finalized(db, year, month):
        return
    label = f"{_MONTH_LABELS[month - 1]} {year}"
    raise ApiError(
        f"Attendance for {label} is not finalized. "
        "Complete Attendance Finalization before running payroll."
    )


def require_day_writable(db: Session, day: date) -> None:
    """Block attendance mutations for a finalized calendar month."""
    if not is_month_finalized(db, day.year, day.month):
        return
    label = f"{_MONTH_LABELS[day.month - 1]} {day.year}"
    raise ApiError(
        f"Attendance for {label} is finalized and locked. "
        "Regularization, exception resolution, and other attendance changes are not allowed."
    )


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    from datetime import timedelta

    start = date(year, month, 1)
    end = date(year, 12, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def _pct(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 1000) / 10


def _group_status(readiness: int, exceptions: int, pending_reg: int) -> FinalizationRowStatus:
    if pending_reg > 0 or readiness < 80:
        return "Pending"
    if exceptions > 0 or readiness < 90:
        return "Review"
    return "Ready"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
