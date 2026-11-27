"""Comp Off credits earned by authorized work on a non-working day.

Each credit expires 90 days after it is credited. Leave approval consumes the
earliest-expiring remainder first. Holiday Pay is not part of this workflow.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import or_, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import AlreadyExists, ApiError, Forbidden, NotFound
from trishul_api.db.models import (
    AppUser,
    Attendance,
    Branch,
    CompOffAuthorization,
    CompOffCredit,
    CompOffLedger,
    Employee,
    Holiday,
    LeaveBalance,
    LeaveBalanceTransaction,
    LeaveType,
    Notification,
)
from trishul_api.modules.hr.attendance.repository import off_weekdays
from trishul_api.modules.hr.leave.holiday_ops import applies_to_branch

EXPIRY_DAYS = 90
_ZERO = Decimal("0.0")
_HALF = Decimal("0.5")
_ONE = Decimal("1.0")
_STEP = Decimal("0.1")
_OPEN = ("Authorized", "Certified")


def _ledger_tables_ready(db: Session) -> bool:
    """True when credit-wise Comp Off tables from migration 0049 exist.

    Uses a SAVEPOINT probe so a missing-table error does not roll back the caller's unit of work
    (inspect/has_table on a shared SQLite connection would).
    """
    cached = db.info.get("comp_off_ledger_ready")
    if isinstance(cached, bool):
        return cached
    try:
        with db.begin_nested():
            db.execute(text("SELECT 1 AS ok FROM hr.comp_off_authorization WHERE 1 = 0"))
        db.info["comp_off_ledger_ready"] = True
        return True
    except DBAPIError:
        db.info["comp_off_ledger_ready"] = False
        return False


def _rule(message: str) -> None:
    from trishul_api.modules.hr.leave.mine_repository import LeaveRuleError

    raise LeaveRuleError(message)


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_STEP)


def _today() -> date:
    return datetime.now(UTC).date()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _financial_year(day: date) -> int:
    return day.year if day.month >= 4 else day.year - 1


def _year_bounds(year: int) -> tuple[date, date]:
    return date(year, 4, 1), date(year + 1, 3, 31)


def remaining(credit: CompOffCredit) -> Decimal:
    return _q((credit.days or _ZERO) - (credit.consumed_days or _ZERO) - (credit.expired_days or _ZERO))


def credit_days_for(hours: Decimal, half_day_hours: Decimal | None) -> Decimal:
    """One day at or above a full shift, half a day at or above the half-day line."""
    half_line = half_day_hours if half_day_hours is not None and half_day_hours > 0 else Decimal("4")
    full = (half_line * 2) if half_day_hours is not None and half_day_hours > 0 else Decimal("8")
    if hours < half_line:
        _rule("Actual working hours are below the half-day minimum, so Comp Off cannot be credited.")
    if hours < full:
        return _HALF
    return _ONE


def worked_hours_of(attendance: Attendance | None) -> Decimal:
    if attendance is None:
        _rule("Actual attendance punches were not captured for this day.")
    if attendance.worked_hours is not None and attendance.worked_hours > 0:
        return Decimal(attendance.worked_hours)
    start = attendance.check_in_at
    end = attendance.check_out_at
    if start is None or end is None or end <= start:
        _rule("Actual attendance punches were not captured for this day.")
    hours = Decimal(str(round((end - start).total_seconds() / 3600, 2)))
    if hours <= 0:
        _rule("Actual attendance punches were not captured for this day.")
    return hours


def authorize(
    db: Session,
    actor: CurrentUser,
    *,
    employee_id: int | None,
    employee_code: str | None,
    work_date: date,
    remarks: str | None,
) -> CompOffAuthorization:
    employee = _employee(db, employee_id, employee_code)
    _assert_can_authorize(actor, employee)
    kind = day_kind(db, employee, work_date)
    if kind is None:
        raise ApiError(
            "Comp Off can only be authorized for a weekly off, company holiday, or declared non-working day."
        )
    open_row = _open_authorization(db, employee.id, work_date)
    if open_row is not None:
        raise AlreadyExists("This day is already authorized for Comp Off.")
    row = CompOffAuthorization(
        employee_id=employee.id,
        work_date=work_date,
        day_kind=kind,
        status="Authorized",
        remarks=(remarks or "").strip() or None,
        authorized_by_user_id=actor.id,
        authorized_at=_now(),
        created_by_user_id=actor.id,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def require_open_authorization(db: Session, employee_id: int, work_date: date) -> CompOffAuthorization:
    row = _open_authorization(db, employee_id, work_date)
    if row is None or row.status != "Authorized":
        _rule("Your reporting manager must authorize this weekly off or holiday before Comp Off can be requested.")
    return row


def reject_holiday_pay(reason: str) -> None:
    if "holiday pay" in reason.lower():
        raise ApiError("Holiday Pay is not available. Compensatory Off is the only compensation for this work.")


def certify_holiday_work(
    db: Session,
    actor: CurrentUser,
    *,
    employee_id: int,
    work_date: date,
    attendance: Attendance | None,
    regularization_id: int,
    half_day_hours: Decimal | None,
) -> CompOffCredit | None:
    """Credit Comp Off when a manager approves authorized holiday or weekly-off work.

    Uses the credit-wise ledger when migration 0049 tables exist. Otherwise credits the
    existing CO leave balance so Holiday Work approval is not blocked by missing DDL.
    """
    if not _ledger_tables_ready(db):
        _certify_balance_only(
            db,
            actor,
            employee_id=employee_id,
            work_date=work_date,
            attendance=attendance,
            regularization_id=regularization_id,
            half_day_hours=half_day_hours,
        )
        return None

    row = _open_authorization(db, employee_id, work_date)
    if row is not None and (_credit_for_authorization(db, row.id) is not None or row.status == "Certified"):
        raise AlreadyExists("Comp Off was already credited for this authorized day.")
    if row is None:
        employee = db.get(Employee, employee_id)
        if employee is None:
            raise NotFound("Employee")
        kind = day_kind(db, employee, work_date)
        if kind is None:
            raise ApiError(
                "Comp Off can only be credited for a weekly off, company holiday, or declared non-working day."
            )
        row = CompOffAuthorization(
            employee_id=employee_id,
            work_date=work_date,
            day_kind=kind,
            status="Authorized",
            remarks="Opened by manager certification of Holiday Work.",
            authorized_by_user_id=actor.id,
            authorized_at=_now(),
            created_by_user_id=actor.id,
            is_active=True,
        )
        db.add(row)
        db.flush()
    elif row.status != "Authorized":
        raise ApiError("Comp Off cannot be credited because this day was not authorized by the reporting manager.")
    hours = worked_hours_of(attendance)
    days = credit_days_for(hours, half_day_hours)
    leave_type = _comp_off_type(db)
    credited_on = _today()
    credit = CompOffCredit(
        authorization_id=row.id,
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        work_date=work_date,
        day_kind=row.day_kind,
        credited_on=credited_on,
        expires_on=credited_on + timedelta(days=EXPIRY_DAYS),
        days=days,
        consumed_days=_ZERO,
        expired_days=_ZERO,
        status="Open",
        created_by_user_id=actor.id,
    )
    db.add(credit)
    db.flush()
    note = (
        f"Worked {work_date.strftime('%d %b %Y')} ({_kind_label(row.day_kind)}), "
        f"{hours} hours. Expires {credit.expires_on.strftime('%d %b %Y')}."
    )
    _ledger(db, credit, "Credit", days, None, note, actor.id)
    _balance_txn(db, credit, "Credit", days, note, actor.id, source_id=credit.id)
    row.status = "Certified"
    row.regularization_id = regularization_id
    row.certified_by_user_id = actor.id
    row.certified_at = _now()
    row.updated_by_user_id = actor.id
    row.updated_at = _now()
    sync_balance(db, employee_id, actor.id)
    return credit


def _certify_balance_only(
    db: Session,
    actor: CurrentUser,
    *,
    employee_id: int,
    work_date: date,
    attendance: Attendance | None,
    regularization_id: int,
    half_day_hours: Decimal | None,
) -> None:
    """Credit CO leave balance when Comp Off ledger tables are not installed yet."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise NotFound("Employee")
    kind = day_kind(db, employee, work_date)
    if kind is None:
        raise ApiError(
            "Comp Off can only be credited for a weekly off, company holiday, or declared non-working day."
        )
    hours = worked_hours_of(attendance)
    days = credit_days_for(hours, half_day_hours)
    leave_type = _comp_off_type(db)
    year = _financial_year(_today())
    prior = db.scalar(
        select(LeaveBalanceTransaction).where(
            LeaveBalanceTransaction.employee_id == employee_id,
            LeaveBalanceTransaction.leave_type_id == leave_type.id,
            LeaveBalanceTransaction.kind == "Credit",
            LeaveBalanceTransaction.source_type == "hr.attendance_regularization",
            LeaveBalanceTransaction.source_id == regularization_id,
            LeaveBalanceTransaction.is_active == True,  # noqa: E712
        )
    )
    if prior is not None:
        raise AlreadyExists("Comp Off was already credited for this Holiday Work approval.")
    credited_on = _today()
    expires_on = credited_on + timedelta(days=EXPIRY_DAYS)
    note = (
        f"Worked {work_date.strftime('%d %b %Y')} ({_kind_label(kind)}), "
        f"{hours} hours. Expires {expires_on.strftime('%d %b %Y')}."
    )
    balance = _balance_row(db, employee_id, leave_type.id, year, actor.id)
    balance.accrued = _q((balance.accrued or _ZERO) + days)
    balance.updated_by_user_id = actor.id
    from trishul_api.modules.hr.leave.balance_ops import _recompute_closing

    _recompute_closing(db, balance)
    db.add(
        LeaveBalanceTransaction(
            employee_id=employee_id,
            leave_type_id=leave_type.id,
            leave_year=year,
            leave_balance_id=balance.id,
            kind="Credit",
            days=_q(days),
            remarks=note[:300],
            source_type="hr.attendance_regularization",
            source_id=regularization_id,
            created_by_user_id=actor.id,
        )
    )
    db.flush()


def assert_available(
    db: Session, employee_id: int, leave_type_id: int, start: date, days: Decimal, pending: Decimal
) -> None:
    leave_type = db.get(LeaveType, leave_type_id)
    if leave_type is None or leave_type.code != "CO":
        return
    expire_due(db, employee_id=employee_id, as_of=_today())
    usable = available_on(db, employee_id, start)
    if usable - pending < days:
        _rule("Insufficient Comp Off balance. Expired, pending, or short credits cannot be used.")


def consume(
    db: Session,
    *,
    employee_id: int,
    leave_type_id: int,
    leave_request_id: int,
    start: date,
    days: Decimal,
    user_id: int,
) -> None:
    leave_type = db.get(LeaveType, leave_type_id)
    if leave_type is None or leave_type.code != "CO":
        return
    expire_due(db, employee_id=employee_id, as_of=start)
    left = _q(days)
    credits = _lock_open(db, employee_id, start)
    usable = sum((remaining(row) for row in credits), _ZERO)
    if usable < left:
        _rule("Insufficient Comp Off balance. Expired, pending, or short credits cannot be used.")
    for credit in credits:
        if left <= 0:
            break
        take = min(remaining(credit), left)
        if take <= 0:
            continue
        credit.consumed_days = _q((credit.consumed_days or _ZERO) + take)
        _refresh(credit)
        credit.updated_by_user_id = user_id
        credit.updated_at = _now()
        note = f"Leave request {leave_request_id} from the credit expiring {credit.expires_on.isoformat()}."
        _ledger(db, credit, "Consumption", take, leave_request_id, note, user_id)
        _balance_txn(db, credit, "Debit", take, note, user_id, source_id=leave_request_id)
        left = _q(left - take)
    if left > 0:
        _rule("Insufficient Comp Off balance. Expired, pending, or short credits cannot be used.")
    sync_balance(db, employee_id, user_id)


def restore(db: Session, *, employee_id: int, leave_type_id: int, leave_request_id: int, user_id: int) -> None:
    leave_type = db.get(LeaveType, leave_type_id)
    if leave_type is None or leave_type.code != "CO":
        return
    rows = db.scalars(
        select(CompOffLedger).where(
            CompOffLedger.employee_id == employee_id,
            CompOffLedger.leave_request_id == leave_request_id,
            CompOffLedger.kind == "Consumption",
            CompOffLedger.is_active == True,  # noqa: E712
        )
    ).all()
    if not rows:
        return
    for entry in rows:
        credit = db.get(CompOffCredit, entry.credit_id)
        if credit is None:
            continue
        already = db.scalar(
            select(CompOffLedger.id).where(
                CompOffLedger.credit_id == credit.id,
                CompOffLedger.leave_request_id == leave_request_id,
                CompOffLedger.kind == "Reversal",
                CompOffLedger.is_active == True,  # noqa: E712
            )
        )
        if already is not None:
            continue
        credit.consumed_days = _q(max(_ZERO, (credit.consumed_days or _ZERO) - entry.days))
        _refresh(credit)
        credit.updated_by_user_id = user_id
        credit.updated_at = _now()
        note = f"Cancellation restored leave request {leave_request_id}."
        _ledger(db, credit, "Reversal", entry.days, leave_request_id, note, user_id)
        _balance_txn(db, credit, "Reversal", entry.days, note, user_id, source_id=leave_request_id)
    sync_balance(db, employee_id, user_id)


def adjust(
    db: Session, actor: CurrentUser, employee: Employee, leave_type: LeaveType, days: Decimal, reason: str
) -> None:
    if leave_type.code != "CO":
        return
    expire_due(db, employee_id=employee.id, as_of=_today())
    if days > 0:
        credited_on = _today()
        credit = CompOffCredit(
            authorization_id=None,
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            work_date=credited_on,
            day_kind="ADJUSTMENT",
            credited_on=credited_on,
            expires_on=credited_on + timedelta(days=EXPIRY_DAYS),
            days=_q(days),
            consumed_days=_ZERO,
            expired_days=_ZERO,
            status="Open",
            created_by_user_id=actor.id,
        )
        db.add(credit)
        db.flush()
        note = f"Adjustment: {reason}"
        _ledger(db, credit, "Adjustment", _q(days), None, note, actor.id)
        _balance_txn(db, credit, "Credit", _q(days), note, actor.id, source_id=credit.id)
    else:
        _reduce(db, employee.id, _q(abs(days)), actor.id, reason)
    sync_balance(db, employee.id, actor.id)


def expire_due(db: Session, *, employee_id: int | None, as_of: date) -> int:
    """Lapse unused Comp Off whose expiry date has been reached. Returns the number of credits lapsed."""
    if not _ledger_tables_ready(db):
        return 0
    stmt = select(CompOffCredit).where(
        CompOffCredit.is_active == True,  # noqa: E712
        CompOffCredit.status == "Open",
        CompOffCredit.expires_on <= as_of,
    )
    if employee_id is not None:
        stmt = stmt.where(CompOffCredit.employee_id == employee_id)
    credits = list(db.scalars(stmt.order_by(CompOffCredit.expires_on, CompOffCredit.id)).all())
    lapsed: dict[int, list[CompOffCredit]] = {}
    count = 0
    for credit in credits:
        left = remaining(credit)
        if left <= 0:
            _refresh(credit)
            continue
        credit.expired_days = _q((credit.expired_days or _ZERO) + left)
        credit.status = "Expired"
        credit.updated_at = _now()
        note = f"Unused Comp Off lapsed on {credit.expires_on.isoformat()}, 90 days after {credit.credited_on.isoformat()}."
        _ledger(db, credit, "Expiry", left, None, note, None)
        _balance_txn(db, credit, "Expiry", left, note, None, source_id=credit.id)
        lapsed.setdefault(credit.employee_id, []).append(credit)
        count += 1
    for person_id, rows in lapsed.items():
        sync_balance(db, person_id, None)
        _notify_expiry(db, person_id, rows)
    if count:
        db.commit()
    return count


def available_on(db: Session, employee_id: int, on: date) -> Decimal:
    credits = _credits(db, employee_id)
    if credits:
        total = _ZERO
        for credit in credits:
            if credit.expires_on <= on or remaining(credit) <= 0:
                continue
            total += remaining(credit)
        return _q(total)
    # Holiday Work may have credited CO on leave_balance before ledger rows existed.
    return _balance_available(db, employee_id, _financial_year(on))


def next_expiry(db: Session, employee_id: int, on: date) -> date | None:
    credits = _credits(db, employee_id)
    if credits:
        dates = [
            credit.expires_on
            for credit in credits
            if credit.expires_on > on and remaining(credit) > 0
        ]
        return min(dates) if dates else None
    dates = [
        line["expires"]
        for line in _balance_lines(db, employee_id, _financial_year(on))
        if isinstance(line.get("expires"), date)
        and line["expires"] > on
        and line.get("status") == "Available"
    ]
    return min(dates) if dates else None


def sync_balance(db: Session, employee_id: int, user_id: int | None) -> None:
    """Keep the CO leave-balance row aligned with the credit ledger for each financial year touched."""
    leave_type = db.scalar(
        select(LeaveType).where(LeaveType.code == "CO", LeaveType.is_active == True)  # noqa: E712
    )
    if leave_type is None:
        return
    credits = _credits(db, employee_id)
    years = {_financial_year(credit.credited_on) for credit in credits}
    years.add(_financial_year(_today()))
    for year in years:
        start, end = _year_bounds(year)
        opening = sum(
            (
                remaining(credit)
                for credit in credits
                if credit.credited_on < start and credit.expires_on > _today()
            ),
            _ZERO,
        )
        in_year = [credit for credit in credits if start <= credit.credited_on <= end]
        balance = _balance_row(db, employee_id, leave_type.id, year, user_id or 0)
        balance.opening = _q(opening)
        balance.accrued = _q(sum((credit.days for credit in in_year), _ZERO))
        balance.availed = _q(sum((credit.consumed_days or _ZERO for credit in in_year), _ZERO))
        if user_id is not None:
            balance.updated_by_user_id = user_id
        from trishul_api.modules.hr.leave.balance_ops import _recompute_closing

        _recompute_closing(db, balance)


def list_lines(db: Session, employee_id: int, financial_year: int) -> list[dict[str, object]]:
    start, end = _year_bounds(financial_year)
    credits = _credits(db, employee_id)
    if credits:
        rows = [
            credit
            for credit in credits
            if start <= credit.credited_on <= end or (credit.expires_on > _today() and remaining(credit) > 0)
        ]
        return [_line(credit) for credit in rows]
    return _balance_lines(db, employee_id, financial_year)


def comp_off_totals(db: Session, employee_id: int, financial_year: int) -> dict[str, Decimal | None]:
    start, end = _year_bounds(financial_year)
    all_credits = _credits(db, employee_id)
    if all_credits:
        credits = [
            credit
            for credit in all_credits
            if start <= credit.credited_on <= end or remaining(credit) > 0
        ]
        earned = _q(sum((credit.days for credit in credits if start <= credit.credited_on <= end), _ZERO))
        used = _q(
            sum((credit.consumed_days or _ZERO for credit in credits if start <= credit.credited_on <= end), _ZERO)
        )
        expired = _q(
            sum((credit.expired_days or _ZERO for credit in credits if start <= credit.credited_on <= end), _ZERO)
        )
        horizon = _today() + timedelta(days=30)
        expiring = _q(
            sum(
                (
                    remaining(credit)
                    for credit in all_credits
                    if remaining(credit) > 0 and _today() < credit.expires_on <= horizon
                ),
                _ZERO,
            )
        )
        return {
            "earned": earned,
            "used": used,
            "expired": expired,
            "available": available_on(db, employee_id, _today()),
            "expiring": expiring,
        }
    return _balance_totals(db, employee_id, financial_year)


def list_authorizations(
    db: Session, actor: CurrentUser, *, employee_id: int | None, scope: str
) -> list[CompOffAuthorization]:
    stmt = select(CompOffAuthorization).where(CompOffAuthorization.is_active == True)  # noqa: E712
    if scope == "mine":
        if actor.employee_id is None:
            return []
        stmt = stmt.where(CompOffAuthorization.employee_id == actor.employee_id)
    elif employee_id is not None:
        employee = db.get(Employee, employee_id)
        if employee is None or not _can_see(actor, employee):
            raise NotFound("Employee")
        stmt = stmt.where(CompOffAuthorization.employee_id == employee_id)
    elif actor.can("hr.leave.manage", "core.employee.manage"):
        pass
    elif actor.employee_id is not None:
        reports = select(Employee.id).where(Employee.reporting_manager_id == actor.employee_id)
        stmt = stmt.where(
            or_(CompOffAuthorization.employee_id == actor.employee_id, CompOffAuthorization.employee_id.in_(reports))
        )
    else:
        return []
    return list(db.scalars(stmt.order_by(CompOffAuthorization.work_date.desc(), CompOffAuthorization.id.desc())).all())


def direct_reports(db: Session, actor: CurrentUser) -> list[Employee]:
    if actor.employee_id is None:
        return []
    return list(
        db.scalars(
            select(Employee)
            .where(
                Employee.reporting_manager_id == actor.employee_id,
                Employee.is_active == True,  # noqa: E712
                Employee.status == "Active",
            )
            .order_by(Employee.employee_code)
        ).all()
    )


def ledger_entries(db: Session, actor: CurrentUser, employee_id: int) -> list[CompOffLedger]:
    employee = db.get(Employee, employee_id)
    if employee is None or not _can_see(actor, employee):
        raise NotFound("Employee")
    return list(
        db.scalars(
            select(CompOffLedger)
            .where(CompOffLedger.employee_id == employee_id, CompOffLedger.is_active == True)  # noqa: E712
            .order_by(CompOffLedger.id)
        ).all()
    )


def day_kind(db: Session, employee: Employee, work_date: date) -> str | None:
    holiday = _holiday(db, employee, work_date)
    if holiday is not None and holiday.holiday_type != "Optional":
        label = f"{holiday.holiday_type} {holiday.name}".lower()
        return "COMPANY_HOLIDAY" if "company" in label else "NON_WORKING"
    if holiday is not None and "company" in f"{holiday.holiday_type} {holiday.name}".lower():
        return "COMPANY_HOLIDAY"
    weekly = _weekly_off_days(db, employee.id, work_date)
    if work_date.weekday() in weekly:
        return "WEEKLY_OFF"
    return None


def _reduce(db: Session, employee_id: int, days: Decimal, user_id: int, reason: str) -> None:
    left = days
    credits = _lock_open(db, employee_id, _today())
    if sum((remaining(row) for row in credits), _ZERO) < left:
        _rule("The Comp Off adjustment is larger than the unused balance.")
    for credit in credits:
        if left <= 0:
            break
        take = min(remaining(credit), left)
        if take <= 0:
            continue
        credit.consumed_days = _q((credit.consumed_days or _ZERO) + take)
        _refresh(credit)
        credit.updated_by_user_id = user_id
        note = f"Adjustment: {reason}"
        _ledger(db, credit, "Adjustment", take, None, note, user_id)
        _balance_txn(db, credit, "Debit", take, note, user_id, source_id=credit.id)
        left = _q(left - take)


def _line(credit: CompOffCredit) -> dict[str, object]:
    left = remaining(credit)
    if credit.expired_days and left == 0:
        status = "Expired"
    elif left == 0:
        status = "Used"
    elif _today() < credit.expires_on <= _today() + timedelta(days=30):
        status = "Expiring"
    else:
        status = "Available"
    return {
        "earned_on": credit.credited_on,
        "days": credit.days,
        "note": f"{_kind_label(credit.day_kind)} on {credit.work_date.strftime('%d %b %Y')}",
        "expires": credit.expires_on,
        "status": status,
    }


def _kind_label(kind: str) -> str:
    return {
        "WEEKLY_OFF": "Weekly off",
        "COMPANY_HOLIDAY": "Company holiday",
        "NON_WORKING": "Declared non-working day",
        "ADJUSTMENT": "Balance adjustment",
    }.get(kind, kind)


def _refresh(credit: CompOffCredit) -> None:
    left = remaining(credit)
    if (credit.expired_days or _ZERO) > 0 and left == 0:
        credit.status = "Expired"
    elif left == 0:
        credit.status = "Exhausted"
    else:
        credit.status = "Open"


def _credits(db: Session, employee_id: int) -> list[CompOffCredit]:
    return list(
        db.scalars(
            select(CompOffCredit)
            .where(CompOffCredit.employee_id == employee_id, CompOffCredit.is_active == True)  # noqa: E712
            .order_by(CompOffCredit.expires_on, CompOffCredit.id)
        ).all()
    )


def _balance_available(db: Session, employee_id: int, financial_year: int) -> Decimal:
    """CO days still on leave_balance when no CompOffCredit ledger rows exist for this employee."""
    leave_type = db.scalar(select(LeaveType).where(LeaveType.code == "CO", LeaveType.is_active == True))  # noqa: E712
    if leave_type is None:
        return _ZERO
    closing = db.scalar(
        select(LeaveBalance.closing).where(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == leave_type.id,
            LeaveBalance.leave_year == financial_year,
            LeaveBalance.is_active == True,  # noqa: E712
        )
    )
    return _q(Decimal(closing or 0))


def _balance_totals(db: Session, employee_id: int, financial_year: int) -> dict[str, Decimal | None]:
    leave_type = db.scalar(select(LeaveType).where(LeaveType.code == "CO", LeaveType.is_active == True))  # noqa: E712
    if leave_type is None:
        return {"earned": _ZERO, "used": _ZERO, "expired": _ZERO, "available": _ZERO, "expiring": _ZERO}
    row = db.scalar(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == leave_type.id,
            LeaveBalance.leave_year == financial_year,
            LeaveBalance.is_active == True,  # noqa: E712
        )
    )
    available = _q(Decimal(row.closing if row else 0))
    earned = _q(Decimal(row.accrued if row else 0))
    used = _q(Decimal(row.availed if row else 0))
    horizon = _today() + timedelta(days=30)
    expiring = _ZERO
    for line in _balance_lines(db, employee_id, financial_year):
        expires = line.get("expires")
        if line.get("status") == "Available" and isinstance(expires, date) and _today() < expires <= horizon:
            expiring = _q(expiring + Decimal(str(line.get("days") or 0)))
    return {
        "earned": earned,
        "used": used,
        "expired": _ZERO,
        "available": available,
        "expiring": expiring,
    }


def _balance_lines(db: Session, employee_id: int, financial_year: int) -> list[dict[str, object]]:
    """Build Comp Off lines from leave_balance_transaction for this employee only."""
    leave_type = db.scalar(select(LeaveType).where(LeaveType.code == "CO", LeaveType.is_active == True))  # noqa: E712
    if leave_type is None:
        return []
    rows = list(
        db.scalars(
            select(LeaveBalanceTransaction)
            .where(
                LeaveBalanceTransaction.employee_id == employee_id,
                LeaveBalanceTransaction.leave_type_id == leave_type.id,
                LeaveBalanceTransaction.leave_year == financial_year,
                LeaveBalanceTransaction.kind == "Credit",
                LeaveBalanceTransaction.is_active == True,  # noqa: E712
                LeaveBalanceTransaction.days > 0,
            )
            .order_by(LeaveBalanceTransaction.created_at.desc(), LeaveBalanceTransaction.id.desc())
        ).all()
    )
    available = _balance_available(db, employee_id, financial_year)
    lines: list[dict[str, object]] = []
    remaining_pool = available
    for row in rows:
        earned_on = row.created_at.date() if row.created_at else _today()
        expires = _expiry_from_remarks(row.remarks, earned_on)
        days = _q(Decimal(row.days or 0))
        if expires <= _today():
            status = "Expired"
        elif remaining_pool > 0:
            status = "Expiring" if expires <= _today() + timedelta(days=30) else "Available"
            remaining_pool = _q(remaining_pool - min(remaining_pool, days))
        else:
            status = "Used"
        lines.append(
            {
                "earned_on": earned_on,
                "days": days,
                "note": (row.remarks or "Compensatory off credit").strip(),
                "expires": expires,
                "status": status,
            }
        )
    return lines


def _expiry_from_remarks(remarks: str | None, earned_on: date) -> date:
    import re

    if remarks:
        match = re.search(r"Expires\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", remarks)
        if match:
            try:
                return datetime.strptime(match.group(1), "%d %b %Y").date()
            except ValueError:
                pass
    return earned_on + timedelta(days=EXPIRY_DAYS)


def _lock_open(db: Session, employee_id: int, on: date) -> list[CompOffCredit]:
    stmt = (
        select(CompOffCredit)
        .where(
            CompOffCredit.employee_id == employee_id,
            CompOffCredit.is_active == True,  # noqa: E712
            CompOffCredit.status == "Open",
            CompOffCredit.expires_on > on,
        )
        .order_by(CompOffCredit.expires_on, CompOffCredit.id)
    )
    if db.get_bind().dialect.name != "sqlite":
        stmt = stmt.with_for_update()
    return [row for row in db.scalars(stmt).all() if remaining(row) > 0]


def _ledger(
    db: Session,
    credit: CompOffCredit,
    kind: str,
    days: Decimal,
    leave_request_id: int | None,
    remarks: str,
    user_id: int | None,
) -> None:
    db.add(
        CompOffLedger(
            credit_id=credit.id,
            employee_id=credit.employee_id,
            kind=kind,
            days=_q(days),
            leave_request_id=leave_request_id,
            remarks=remarks[:300],
            created_at=_now(),
            created_by_user_id=user_id,
            is_active=True,
        )
    )


def _balance_txn(
    db: Session,
    credit: CompOffCredit,
    kind: str,
    days: Decimal,
    remarks: str,
    user_id: int | None,
    *,
    source_id: int | None,
) -> None:
    year = _financial_year(credit.credited_on)
    balance = _balance_row(db, credit.employee_id, credit.leave_type_id, year, user_id or 0)
    db.add(
        LeaveBalanceTransaction(
            employee_id=credit.employee_id,
            leave_type_id=credit.leave_type_id,
            leave_year=year,
            leave_balance_id=balance.id,
            kind=kind,
            days=_q(days),
            remarks=remarks[:300],
            source_type="hr.comp_off_credit",
            source_id=source_id,
            created_by_user_id=user_id,
        )
    )
    db.flush()


def _balance_row(db: Session, employee_id: int, leave_type_id: int, year: int, user_id: int) -> LeaveBalance:
    balance = db.scalars(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.leave_year == year,
            LeaveBalance.is_active == True,  # noqa: E712
        )
    ).first()
    if balance is not None:
        return balance
    balance = LeaveBalance(
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        leave_year=year,
        opening=_ZERO,
        accrued=_ZERO,
        availed=_ZERO,
        encashed=_ZERO,
        closing=_ZERO,
        created_by_user_id=user_id,
    )
    db.add(balance)
    db.flush()
    return balance


def _notify_expiry(db: Session, employee_id: int, credits: list[CompOffCredit]) -> None:
    user_id = db.scalar(
        select(AppUser.id)
        .where(AppUser.employee_id == employee_id, AppUser.is_active == True)  # noqa: E712
        .order_by(AppUser.id)
    )
    if user_id is None:
        return
    days = _q(sum((entry.expired_days or _ZERO for entry in credits), _ZERO))
    when = ", ".join(sorted({credit.expires_on.strftime("%d %b %Y") for credit in credits}))
    message = f"{days} Comp Off day(s) lapsed on {when} because they were unused for 90 days."
    db.add(
        Notification(
            channel="Push",
            recipient_user_id=user_id,
            entity_type="hr.comp_off_credit",
            entity_id=credits[0].id,
            payload=json.dumps({"title": "Comp Off expired", "message": message[:900]}, separators=(",", ":")),
            status="Queued",
        )
    )


def _open_authorization(db: Session, employee_id: int, work_date: date) -> CompOffAuthorization | None:
    return db.scalar(
        select(CompOffAuthorization).where(
            CompOffAuthorization.employee_id == employee_id,
            CompOffAuthorization.work_date == work_date,
            CompOffAuthorization.status.in_(_OPEN),
            CompOffAuthorization.is_active == True,  # noqa: E712
        )
    )


def _credit_for_authorization(db: Session, authorization_id: int) -> CompOffCredit | None:
    return db.scalar(
        select(CompOffCredit).where(
            CompOffCredit.authorization_id == authorization_id,
            CompOffCredit.is_active == True,  # noqa: E712
        )
    )


def _comp_off_type(db: Session) -> LeaveType:
    leave_type = db.scalar(select(LeaveType).where(LeaveType.code == "CO", LeaveType.is_active == True))  # noqa: E712
    if leave_type is None:
        raise ApiError("The Comp Off leave type (CO) is not configured.")
    return leave_type


def _employee(db: Session, employee_id: int | None, employee_code: str | None) -> Employee:
    employee: Employee | None = None
    if employee_id is not None:
        employee = db.get(Employee, employee_id)
    elif employee_code and employee_code.strip():
        employee = db.scalar(select(Employee).where(Employee.employee_code == employee_code.strip()))
    if employee is None or not employee.is_active or employee.status != "Active":
        raise NotFound("Employee")
    return employee


def _assert_can_authorize(actor: CurrentUser, employee: Employee) -> None:
    if actor.employee_id is not None and actor.employee_id == employee.id:
        raise Forbidden("You cannot authorize your own Comp Off.")
    if actor.can("hr.leave.manage", "core.employee.manage"):
        return
    if actor.employee_id is not None and employee.reporting_manager_id == actor.employee_id:
        return
    raise Forbidden("Only the reporting manager or HR can authorize Comp Off.")


def _can_see(actor: CurrentUser, employee: Employee) -> bool:
    if actor.employee_id is not None and actor.employee_id == employee.id:
        return True
    if actor.can("hr.leave.manage", "hr.leave.view", "core.employee.manage"):
        return True
    return actor.employee_id is not None and employee.reporting_manager_id == actor.employee_id


def _holiday(db: Session, employee: Employee, work_date: date) -> Holiday | None:
    state_id = None
    if employee.branch_id is not None:
        state_id = db.scalar(select(Branch.state_id).where(Branch.id == employee.branch_id))
    if employee.branch_id is None:
        return db.scalar(
            select(Holiday).where(
                Holiday.is_active == True,  # noqa: E712
                Holiday.holiday_date == work_date,
                Holiday.branch_id.is_(None),
            )
        )
    return db.scalar(
        select(Holiday).where(
            Holiday.is_active == True,  # noqa: E712
            Holiday.holiday_date == work_date,
            applies_to_branch(employee.branch_id, state_id),
        )
    )


def _weekly_off_days(db: Session, employee_id: int, work_date: date) -> set[int]:
    from trishul_api.db.models import EmployeeShift

    row = db.scalar(
        select(EmployeeShift)
        .where(
            EmployeeShift.employee_id == employee_id,
            EmployeeShift.is_active == True,  # noqa: E712
            EmployeeShift.from_date <= work_date,
            or_(EmployeeShift.to_date.is_(None), EmployeeShift.to_date >= work_date),
        )
        .order_by(EmployeeShift.from_date.desc(), EmployeeShift.id.desc())
    )
    return off_weekdays(row.weekly_off_days if row is not None else None)
