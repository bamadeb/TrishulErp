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
from trishul_api.db.models import AppUser, Department, Employee, Notification, SystemSetting
from trishul_api.modules.hr.attendance.schemas import (
    AttendanceExceptionsQuery,
    FinalizationAssigneeOut,
    FinalizationChecklistItemOut,
    FinalizationFollowupWrite,
    FinalizationGroupBy,
    FinalizationGroupRowOut,
    FinalizationKpiOut,
    FinalizationLockOut,
    FinalizationPageOut,
    FinalizationQuery,
    FinalizationRemindResult,
    FinalizationRemindWrite,
    FinalizationReminderOut,
    FinalizationRowStatus,
    FinalizationSummaryOut,
    FinalizationTargetOut,
    FollowupStatus,
    MonthlyMusterQuery,
    MusterEmployeeRowOut,
    RegularizationQuery,
)
SETTING_PREFIX = "hr.attendance.finalization."
_SETTING_PREFIX = SETTING_PREFIX
_FOLLOWUP_ENTITY = "hr.attendance.followup"
_REMINDER_ENTITY = "hr.attendance.reminder"
_CHECKLIST_IDS = frozenset({"processed", "exceptions", "regularization", "ready", "pending"})
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
        exception_people = self._pending_exception_people(start, end)
        regularization_people = self._pending_regularization_people(start, end)
        pending_exception_ids = set(exception_people)
        pending_reg_ids = set(regularization_people)

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
        contacts = self._contacts()
        department_groups = (
            groups
            if query.group_by == "department"
            else self._group_rows(
                employees,
                pending_exception_ids,
                pending_reg_ids,
                group_by="department",
            )
        )
        checklist = self._attach_followups(
            checklist,
            year=year,
            month=month,
            targets={
                "exceptions": self._exception_targets(exception_people, contacts),
                "regularization": self._regularization_targets(regularization_people, contacts),
                "ready": self._department_targets(department_groups, contacts),
                "pending": self._missing_targets(
                    employees, pending_exception_ids, pending_reg_ids, contacts
                ),
                "processed": [],
            },
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
            assignees=self._assignees(contacts),
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

    def _pending_exception_people(self, start: date, end: date) -> dict[int, dict[str, Any]]:
        people: dict[int, dict[str, Any]] = {}
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
                slot = people.setdefault(
                    row.employee_id,
                    {
                        "code": row.employee_code,
                        "name": row.employee_name,
                        "count": 0,
                        "types": set(),
                    },
                )
                slot["count"] += 1
                slot["types"].add(row.exception_type)
            if page * 200 >= result.total or not result.items:
                break
            page += 1
            if page > 50:
                break
        return people

    def _pending_regularization_people(self, start: date, end: date) -> dict[int, dict[str, Any]]:
        people: dict[int, dict[str, Any]] = {}
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
                slot = people.setdefault(
                    row.employee_id,
                    {"code": row.employee_code, "name": row.employee_name, "count": 0},
                )
                slot["count"] += 1
            if page * 200 >= result.total or not result.items:
                break
            page += 1
            if page > 50:
                break
        return people

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
                route="/hr/attendance/monthly-muster",
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
                route="/hr/attendance/exceptions",
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
                route="/hr/attendance/regularization",
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
                route="/hr/attendance/monthly-muster",
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
                route="/hr/attendance/monthly-muster",
            ),
        ]

    def save_followup(self, actor: CurrentUser, body: FinalizationFollowupWrite) -> FinalizationChecklistItemOut:
        if body.checklist_id not in _CHECKLIST_IDS:
            raise ApiError("Unknown checklist item.")
        if body.owner_user_id is not None:
            owner = self._db.get(AppUser, body.owner_user_id)
            if owner is None or not owner.is_active:
                raise ApiError("Choose an active user as the task owner.")
        row = self._task_row(body.year, body.month, body.checklist_id)
        payload = {
            "checklistId": body.checklist_id,
            "dueDate": body.due_date.isoformat() if body.due_date else None,
            "comment": body.comment.strip(),
            "savedByUserId": actor.id,
        }
        if row is None:
            self._db.add(
                Notification(
                    channel="Email",
                    recipient_user_id=body.owner_user_id,
                    entity_type=_FOLLOWUP_ENTITY,
                    entity_id=_month_key(body.year, body.month),
                    payload=json.dumps(payload, separators=(",", ":")),
                    status="Queued",
                )
            )
        else:
            row.recipient_user_id = body.owner_user_id
            row.payload = json.dumps(payload, separators=(",", ":"))
            row.status = "Queued"
        self._db.commit()
        page = self.overview(FinalizationQuery(year=body.year, month=body.month, group_by="department"))
        item = next(entry for entry in page.checklist if entry.id == body.checklist_id)
        return item

    def remind(self, body: FinalizationRemindWrite) -> FinalizationRemindResult:
        page = self.overview(FinalizationQuery(year=body.year, month=body.month, group_by="department"))
        if body.checklist_id and body.checklist_id not in _CHECKLIST_IDS:
            raise ApiError("Unknown checklist item.")
        chosen = [
            item
            for item in page.checklist
            if body.checklist_id is None or item.id == body.checklist_id
        ]
        sent = skipped = failed = 0
        today = datetime.now(UTC).date()
        existing = self._reminder_rows(body.year, body.month)
        seen = {
            (self._payload(row).get("checklistId"), row.recipient_user_id, _sent_day(row.sent_at))
            for row in existing
        }
        for item in chosen:
            if item.done:
                continue
            recipients = self._reminder_recipients(item)
            if not recipients:
                failed += 1
                self._db.add(
                    self._reminder_notification(
                        body.year,
                        body.month,
                        item.id,
                        None,
                        "No owner",
                        "Failed",
                        f"No owner or recipient is available for {item.label}.",
                        item.detail,
                    )
                )
                continue
            for user_id, name, email in recipients:
                key = (item.id, user_id, today)
                if key in seen:
                    skipped += 1
                    continue
                seen.add(key)
                if not email:
                    failed += 1
                    status = "Failed"
                    error = f"{name} has no email address."
                else:
                    # core.notification is the delivery log. This server has no mail transport.
                    failed += 1
                    status = "Failed"
                    error = "Email transport is not configured. The reminder was recorded and was not sent."
                self._db.add(
                    self._reminder_notification(
                        body.year,
                        body.month,
                        item.id,
                        user_id,
                        name,
                        status,
                        error,
                        _reminder_text(item.label, item.detail, page.summary.month_label),
                    )
                )
        self._db.commit()
        return FinalizationRemindResult(
            sent=sent,
            skipped=skipped,
            failed=failed,
            message=_remind_message(sent, skipped, failed),
        )

    def _contacts(self) -> dict[str, Any]:
        employees: dict[int, dict[str, Any]] = {}
        for row in self._db.execute(
            select(
                Employee.id,
                Employee.employee_code,
                Employee.first_name,
                Employee.last_name,
                Employee.email,
                Employee.reporting_manager_id,
            ).where(Employee.is_active == True)  # noqa: E712
        ).all():
            name = " ".join(part for part in (row[2], row[3]) if part).strip() or row[1]
            employees[int(row[0])] = {
                "code": row[1],
                "name": name,
                "email": row[4],
                "manager_id": int(row[5]) if row[5] is not None else None,
            }
        users_by_employee: dict[int, dict[str, Any]] = {}
        users_by_id: dict[int, dict[str, Any]] = {}
        for row in self._db.execute(
            select(AppUser.id, AppUser.employee_id, AppUser.email, AppUser.username, AppUser.is_active)
        ).all():
            if not row[4]:
                continue
            slot = {
                "user_id": int(row[0]),
                "employee_id": int(row[1]) if row[1] is not None else None,
                "email": row[2],
                "username": row[3],
            }
            users_by_id[slot["user_id"]] = slot
            if slot["employee_id"] is not None:
                users_by_employee[slot["employee_id"]] = slot
        heads = {
            str(name): int(head_id)
            for name, head_id in self._db.execute(
                select(Department.name, Department.head_employee_id).where(
                    Department.is_active == True,  # noqa: E712
                    Department.head_employee_id.is_not(None),
                )
            ).all()
            if head_id is not None
        }
        return {
            "employees": employees,
            "users_by_employee": users_by_employee,
            "users_by_id": users_by_id,
            "heads": heads,
        }

    def _assignees(self, contacts: dict[str, Any]) -> list[FinalizationAssigneeOut]:
        employees: dict[int, dict[str, Any]] = contacts["employees"]
        items: list[FinalizationAssigneeOut] = []
        for user in contacts["users_by_id"].values():
            employee = employees.get(user["employee_id"]) if user["employee_id"] else None
            name = employee["name"] if employee else user["username"]
            items.append(FinalizationAssigneeOut(user_id=user["user_id"], name=name))
        items.sort(key=lambda item: item.name.lower())
        return items

    def _target(
        self,
        contacts: dict[str, Any],
        employee_id: int,
        code: str,
        name: str,
        detail: str,
        *,
        recipient_employee_id: int | None = None,
    ) -> FinalizationTargetOut:
        recipient_id = recipient_employee_id if recipient_employee_id is not None else employee_id
        user = contacts["users_by_employee"].get(recipient_id)
        recipient_name = ""
        if user is not None:
            employee = contacts["employees"].get(recipient_id)
            recipient_name = employee["name"] if employee else user["username"]
        return FinalizationTargetOut(
            employee_id=employee_id,
            employee_code=code,
            employee_name=name,
            detail=detail,
            recipient_user_id=user["user_id"] if user else None,
            recipient_name=recipient_name,
        )

    def _exception_targets(
        self, people: dict[int, dict[str, Any]], contacts: dict[str, Any]
    ) -> list[FinalizationTargetOut]:
        targets: list[FinalizationTargetOut] = []
        for employee_id, person in sorted(people.items(), key=lambda item: item[1]["name"]):
            kinds = ", ".join(sorted(person["types"]))
            manager_id = (contacts["employees"].get(employee_id) or {}).get("manager_id")
            targets.append(
                self._target(
                    contacts,
                    employee_id,
                    person["code"],
                    person["name"],
                    f"{person['count']} pending ({kinds})",
                    recipient_employee_id=manager_id or employee_id,
                )
            )
            if len(targets) >= 25:
                break
        return targets

    def _regularization_targets(
        self, people: dict[int, dict[str, Any]], contacts: dict[str, Any]
    ) -> list[FinalizationTargetOut]:
        targets: list[FinalizationTargetOut] = []
        for employee_id, person in sorted(people.items(), key=lambda item: item[1]["name"]):
            manager_id = (contacts["employees"].get(employee_id) or {}).get("manager_id")
            targets.append(
                self._target(
                    contacts,
                    employee_id,
                    person["code"],
                    person["name"],
                    f"{person['count']} pending request(s) for the reporting manager",
                    recipient_employee_id=manager_id,
                )
            )
            if len(targets) >= 25:
                break
        return targets

    def _department_targets(
        self, groups: list[FinalizationGroupRowOut], contacts: dict[str, Any]
    ) -> list[FinalizationTargetOut]:
        targets: list[FinalizationTargetOut] = []
        for group in groups:
            if group.status == "Ready":
                continue
            head_id = contacts["heads"].get(group.name)
            head = contacts["employees"].get(head_id) if head_id else None
            if head is None:
                targets.append(
                    FinalizationTargetOut(
                        employee_id=0,
                        employee_code="",
                        employee_name=group.name,
                        detail=f"{group.status}, {group.readiness}% ready. No department head is assigned.",
                    )
                )
            else:
                targets.append(
                    self._target(
                        contacts,
                        head_id,
                        head["code"],
                        head["name"],
                        f"{group.name}: {group.status}, {group.readiness}% ready",
                        recipient_employee_id=head_id,
                    )
                )
        return targets

    def _missing_targets(
        self,
        employees: list[MusterEmployeeRowOut],
        pending_exception_ids: set[int],
        pending_reg_ids: set[int],
        contacts: dict[str, Any],
    ) -> list[FinalizationTargetOut]:
        targets: list[FinalizationTargetOut] = []
        for member in employees:
            reasons: list[str] = []
            if member.employee_id in pending_exception_ids:
                reasons.append("pending exception")
            if member.employee_id in pending_reg_ids:
                reasons.append("pending regularization")
            if not reasons and member.absent > 0 and member.absent >= max(member.present, 1):
                reasons.append(f"{member.absent} absent day(s) and no completed attendance")
            if not reasons:
                continue
            manager_id = (contacts["employees"].get(member.employee_id) or {}).get("manager_id")
            targets.append(
                self._target(
                    contacts,
                    member.employee_id,
                    member.employee_code,
                    member.employee_name,
                    "; ".join(reasons),
                    recipient_employee_id=manager_id or member.employee_id,
                )
            )
            if len(targets) >= 25:
                break
        return targets

    def _attach_followups(
        self,
        checklist: list[FinalizationChecklistItemOut],
        *,
        year: int,
        month: int,
        targets: dict[str, list[FinalizationTargetOut]],
    ) -> list[FinalizationChecklistItemOut]:
        tasks = {
            str(self._payload(row).get("checklistId")): row
            for row in self._rows(_FOLLOWUP_ENTITY, year, month)
        }
        reminders = self._reminder_rows(year, month)
        contacts = self._contacts()
        enriched: list[FinalizationChecklistItemOut] = []
        for item in checklist:
            task = tasks.get(item.id)
            payload = self._payload(task) if task is not None else {}
            due = _parse_date(payload.get("dueDate"))
            owner_id = task.recipient_user_id if task is not None else None
            owner = contacts["users_by_id"].get(owner_id) if owner_id else None
            owner_name = ""
            if owner is not None:
                employee = contacts["employees"].get(owner["employee_id"]) if owner["employee_id"] else None
                owner_name = employee["name"] if employee else owner["username"]
            history = [
                FinalizationReminderOut(
                    id=row.id,
                    sent_at=_as_utc(row.sent_at),
                    recipient_name=str(self._payload(row).get("recipientName") or "Recipient"),
                    status=row.status,
                    error_message=row.error_message,
                    message=str(self._payload(row).get("message") or ""),
                )
                for row in reminders
                if self._payload(row).get("checklistId") == item.id
            ]
            history.sort(key=lambda entry: entry.id, reverse=True)
            item.targets = targets.get(item.id, [])
            item.reminders = history[:8]
            item.owner_user_id = owner_id
            item.owner_name = owner_name
            item.due_date = due
            item.comment = str(payload.get("comment") or "")
            item.status = _followup_status(item.done, due, owner_id is not None, bool(history))
            enriched.append(item)
        return enriched

    def _rows(self, entity_type: str, year: int, month: int) -> list[Notification]:
        return list(
            self._db.scalars(
                select(Notification).where(
                    Notification.entity_type == entity_type,
                    Notification.entity_id == _month_key(year, month),
                )
            ).all()
        )

    def _task_row(self, year: int, month: int, checklist_id: str) -> Notification | None:
        for row in self._rows(_FOLLOWUP_ENTITY, year, month):
            if self._payload(row).get("checklistId") == checklist_id:
                return row
        return None

    def _reminder_rows(self, year: int, month: int) -> list[Notification]:
        return self._rows(_REMINDER_ENTITY, year, month)

    def _reminder_recipients(
        self, item: FinalizationChecklistItemOut
    ) -> list[tuple[int, str, str | None]]:
        if item.owner_user_id is not None:
            user = self._db.get(AppUser, item.owner_user_id)
            if user is None or not user.is_active:
                return []
            return [(user.id, user.username, user.email)]
        found: dict[int, str] = {}
        for target in item.targets:
            if target.recipient_user_id is not None and target.recipient_name:
                found[target.recipient_user_id] = target.recipient_name
        if not found:
            return []
        users = {
            row.id: row
            for row in self._db.scalars(select(AppUser).where(AppUser.id.in_(found))).all()
        }
        return [
            (user_id, found[user_id], users[user_id].email if user_id in users else None)
            for user_id in found
            if user_id in users and users[user_id].is_active
        ]

    def _reminder_notification(
        self,
        year: int,
        month: int,
        checklist_id: str,
        user_id: int | None,
        name: str,
        status: str,
        error: str | None,
        message: str,
    ) -> Notification:
        return Notification(
            channel="Email",
            recipient_user_id=user_id,
            entity_type=_REMINDER_ENTITY,
            entity_id=_month_key(year, month),
            payload=json.dumps(
                {"checklistId": checklist_id, "recipientName": name, "message": message},
                separators=(",", ":"),
            ),
            status=status,
            sent_at=datetime.now(UTC).replace(tzinfo=None),
            error_message=(error or None),
        )

    @staticmethod
    def _payload(row: Notification | None) -> dict[str, Any]:
        if row is None or not row.payload:
            return {}
        try:
            data = json.loads(row.payload)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

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


def _month_key(year: int, month: int) -> int:
    return year * 100 + month


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _sent_day(value: datetime | None) -> date | None:
    stamped = _as_utc(value)
    return stamped.date() if stamped else None


def _followup_status(done: bool, due: date | None, has_owner: bool, reminded: bool) -> FollowupStatus:
    if done:
        return "Completed"
    if due is not None and due < date.today():
        return "Overdue"
    if has_owner or reminded:
        return "In Progress"
    return "Pending"


def _reminder_text(label: str, detail: str, month_label: str) -> str:
    return f"Attendance follow-up for {month_label}: {label}. {detail}".strip()


def _remind_message(sent: int, skipped: int, failed: int) -> str:
    return (
        f"{sent} reminder(s) sent, {skipped} duplicate(s) skipped, {failed} failed. "
        "Failed reminders stay in the notification history."
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
