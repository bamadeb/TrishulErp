"""Idempotent demo leave balances for the existing TrishulDev employees.

Refuses every database except TrishulDev. Skips an employee, leave type and year when a
balance row already exists, so a genuine balance is never overwritten. A second run inserts
nothing. Demo rows use source_type ``demo.leave`` and reasons that start with ``DEMO:``.

    uv run --no-sync python scripts/seed_demo_leave_balances.py
    uv run --no-sync python scripts/seed_demo_leave_balances.py --rollback
"""

from __future__ import annotations

import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))

from trishul_api.auth import CurrentUser  # noqa: E402
from trishul_api.config import get_settings  # noqa: E402
from trishul_api.db.engine import create_db_engine  # noqa: E402
from trishul_api.db.models import (  # noqa: E402
    Attendance,
    Employee,
    LeaveBalance,
    LeaveBalanceTransaction,
    LeaveEntitlementRun,
    LeavePolicy,
    LeavePolicyLine,
    LeaveRequest,
    LeaveType,
)
from trishul_api.modules.hr.leave.balance_ops import balance_board, balance_detail  # noqa: E402
from trishul_api.modules.hr.leave.calculation import earned_leave_days  # noqa: E402
from trishul_api.modules.hr.leave.mine_repository import LeaveMineRepository, _service_months  # noqa: E402
from trishul_api.secrets import create_secret_provider  # noqa: E402

SOURCE = "demo.leave"
YEARS = (2026, 2027)
ATTENDANCE_YEAR = 2026
POLICY_NAME = "Odisha Private Company Leave Policy"
ZERO = Decimal("0.0")
STEP = Decimal("0.1")

# Present days in 2026, then EL opening, EL used, EL adjustment, SL used, CL used,
# Comp-Off Sundays granted, Comp-Off used, Comp-Off expired.
PROFILES: dict[str, tuple[int, int, int, int, int, int, int, int, int]] = {
    "EMP0001": (260, 4, 2, 0, 1, 2, 2, 1, 0),
    "EMP0002": (240, 0, 1, 0, 0, 1, 1, 0, 0),
    "EMP0003": (200, 0, 0, 0, 3, 0, 0, 0, 0),
    "EMP0004": (239, 0, 0, 0, 0, 4, 1, 1, 0),
    "EMP0005": (280, 2, 1, 1, 2, 1, 2, 0, 1),
    "EMP0009": (250, 0, 0, 0, 0, 0, 0, 0, 0),
    "EMP0015": (180, 0, 0, 0, 0, 3, 0, 0, 0),
    "EMP0016": (40, 0, 0, 0, 0, 0, 0, 0, 0),
    "TT000001": (320, 6, 3, 0, 1, 2, 2, 1, 0),
    "TT000002": (48, 0, 0, 0, 0, 0, 0, 0, 0),
    "TT000003": (20, 0, 0, 0, 0, 1, 0, 0, 0),
}


def main() -> None:
    rollback = "--rollback" in sys.argv
    engine = _engine()
    with Session(engine) as db:
        _require_dev(db)
        if rollback:
            removed = _rollback(db)
            db.commit()
            print("rolled back", removed)
        else:
            inserted = _seed(db)
            db.commit()
            print("inserted", inserted)
            _verify(db)
    engine.dispose()


def _engine():
    settings = get_settings()
    secrets = create_secret_provider(settings) if settings.db_secret_id else None
    return create_db_engine(settings, secrets)


def _require_dev(db: Session) -> None:
    name = db.execute(text("SELECT DB_NAME()")).scalar()
    print(f"database {name}", flush=True)
    if name != "TrishulDev":
        raise SystemExit("Refusing to change leave data because this is not TrishulDev.")


def _seed(db: Session) -> dict[str, int]:
    policy = db.scalars(select(LeavePolicy).where(LeavePolicy.name == POLICY_NAME)).one()
    lines = {
        _code(db, line.leave_type_id): line
        for line in db.scalars(
            select(LeavePolicyLine).where(
                LeavePolicyLine.leave_policy_id == policy.id,
                LeavePolicyLine.is_active == True,  # noqa: E712
            )
        ).all()
    }
    user_id = policy.created_by_user_id
    employees = list(
        db.scalars(
            select(Employee).where(Employee.is_active == True, Employee.status == "Active").order_by(Employee.employee_code)  # noqa: E712
        ).all()
    )
    weight = _present_weight(db, user_id)
    counts = {"balances": 0, "transactions": 0, "runs": 0, "attendance": 0, "requests": 0, "skipped": 0}
    print("proposed")
    for employee in employees:
        profile = PROFILES.get(employee.employee_code)
        if profile is None:
            print(f"skip {employee.employee_code} (not one of the 11 demo profiles)")
            continue
        dates = _dates(employee.date_of_joining, profile[0])
        sundays = [day for day in dates if day.weekday() == 6][: profile[6]]
        plan = _plan(employee, lines, dates, sundays, profile, weight)
        _print_plan(employee, plan)
        sunday_ids = _attendance(db, employee.id, dates, sundays, user_id, counts)
        _requests(db, employee.id, lines, plan, user_id, counts)
        for year in YEARS:
            for code in ("EL", "SL", "CL", "CO"):
                if _balance_exists(db, employee.id, lines[code].leave_type_id, year):
                    counts["skipped"] += 1
                    continue
                _store_bucket(db, employee, lines[code], year, plan[code], sunday_ids, user_id, counts)
            for code in ("EL", "SL", "CL", "CO", "WR"):
                _store_run(db, employee, lines[code], year, plan, dates, user_id, counts)
    return counts


def _plan(
    employee: Employee,
    lines: dict[str, LeavePolicyLine],
    dates: list[date],
    sundays: list[date],
    profile: tuple[int, int, int, int, int, int, int, int, int],
    weight: Decimal,
) -> dict[str, dict[str, Decimal]]:
    present = (Decimal(len(dates)) * weight).quantize(STEP)
    el_line = lines["EL"]
    el_credit = earned_leave_days(
        eligibility_days=present,
        days_worked=present,
        credit_days=el_line.credit_days or ZERO,
        per_days=el_line.qualifying_days_per_credit or 0,
        minimum_qualifying_days=el_line.minimum_qualifying_days or 0,
        joining=employee.date_of_joining,
        attendance_year=ATTENDANCE_YEAR,
        joining_rule=el_line.joining_year_rule,
    )
    opening, used, adjustment = _fit(Decimal(profile[1]), el_credit, Decimal(profile[2]), Decimal(profile[3]), ZERO)
    sl_line = lines["SL"]
    months = _service_months(employee.date_of_joining, date(2027, 1, 1))
    sl_credit = sl_line.annual_entitlement if months >= (sl_line.minimum_service_months or 0) else ZERO
    _, sl_used, _ = _fit(ZERO, sl_credit, Decimal(profile[4]), ZERO, ZERO)
    cl_credit = lines["CL"].annual_entitlement or ZERO
    _, cl_used, _ = _fit(ZERO, cl_credit, Decimal(profile[5]), ZERO, ZERO)
    co_credit = Decimal(len(sundays))
    _, co_used, _ = _fit(ZERO, co_credit, Decimal(profile[7]), ZERO, Decimal(profile[8]))
    expiry = min(Decimal(profile[8]), co_credit - co_used)
    return {
        "EL": _bucket(opening, el_credit, used, adjustment, ZERO, present),
        "SL": _bucket(ZERO, sl_credit, sl_used, ZERO, ZERO, Decimal(months)),
        "CL": _bucket(ZERO, cl_credit, cl_used, ZERO, ZERO, ZERO),
        "CO": _bucket(ZERO, co_credit, co_used, ZERO, expiry, ZERO),
    }


def _bucket(
    opening: Decimal, credit: Decimal, used: Decimal, adjustment: Decimal, expiry: Decimal, evidence: Decimal
) -> dict[str, Decimal]:
    closing = (opening + credit + adjustment - used - expiry).quantize(STEP)
    return {
        "opening": opening.quantize(STEP),
        "credit": credit.quantize(STEP),
        "used": used.quantize(STEP),
        "adjustment": adjustment.quantize(STEP),
        "expiry": expiry.quantize(STEP),
        "closing": closing,
        "evidence": evidence,
    }


def _fit(
    opening: Decimal, credit: Decimal, used: Decimal, adjustment: Decimal, expiry: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    room = opening + credit + adjustment - expiry
    if room < 0:
        return opening, ZERO, adjustment
    return opening, min(used, room), adjustment


def _print_plan(employee: Employee, plan: dict[str, dict[str, Decimal]]) -> None:
    joined = employee.date_of_joining.isoformat() if employee.date_of_joining else "none"
    parts = [f"{employee.employee_code} joined {joined}"]
    for code in ("EL", "SL", "CL", "CO"):
        row = plan[code]
        parts.append(
            f"{code} {row['opening']}+{row['credit']}+{row['adjustment']}-{row['used']}-{row['expiry']}={row['closing']}"
        )
    print(" | ".join(parts), flush=True)


def _dates(joining: date | None, count: int) -> list[date]:
    start = date(ATTENDANCE_YEAR, 1, 1)
    if joining is not None and joining.year == ATTENDANCE_YEAR and joining > start:
        start = joining
    found: list[date] = []
    day = start
    while len(found) < count and day.year == ATTENDANCE_YEAR:
        found.append(day)
        day += timedelta(days=1)
    return found


def _present_weight(db: Session, user_id: int | None) -> Decimal:
    weight = db.execute(text(
        "SELECT day_weight FROM hr.leave_attendance_class WHERE attendance_status = N'Present'"
    )).scalar()
    if weight is not None:
        return Decimal(weight)
    others = db.execute(text("SELECT COUNT(*) FROM hr.leave_attendance_class")).scalar() or 0
    if others:
        print("attendance class Present left unchanged; demo Present days count as 1.0", flush=True)
        return Decimal("1.0")
    db.execute(text("""
        INSERT INTO hr.leave_attendance_class (
            attendance_status, counts_for_eligibility, counts_as_days_worked, is_deemed_work,
            day_weight, created_by_user_id, is_active
        ) VALUES (N'Present', 1, 1, 0, 1.0, :user_id, 1)
    """), {"user_id": user_id})
    print("attendance class Present day weight 1.0", flush=True)
    return Decimal("1.0")


def _attendance(
    db: Session, employee_id: int, dates: list[date], sundays: list[date], user_id: int | None, counts: dict[str, int]
) -> dict[date, int]:
    existing = {
        row.attendance_date: row.id
        for row in db.scalars(
            select(Attendance).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date >= date(ATTENDANCE_YEAR, 1, 1),
                Attendance.attendance_date <= date(ATTENDANCE_YEAR, 12, 31),
            )
        ).all()
    }
    sunday_ids: dict[date, int] = {}
    for day in dates:
        if day in existing:
            if day in sundays:
                sunday_ids[day] = existing[day]
            continue
        row = Attendance(
            employee_id=employee_id,
            attendance_date=day,
            check_in_at=datetime.combine(day, time(9, 0)),
            check_out_at=datetime.combine(day, time(18, 0)),
            source="Manual",
            worked_hours=Decimal("8.00"),
            status="Present",
            is_regularized=False,
            created_by_user_id=user_id,
            is_active=True,
        )
        db.add(row)
        db.flush()
        counts["attendance"] += 1
        if day in sundays:
            sunday_ids[day] = row.id
    return sunday_ids


def _requests(
    db: Session, employee_id: int, lines: dict[str, LeavePolicyLine], plan: dict[str, dict[str, Decimal]], user_id: int | None, counts: dict[str, int]
) -> None:
    starts = {"EL": date(2027, 1, 4), "SL": date(2027, 1, 18), "CL": date(2027, 2, 1), "CO": date(2027, 2, 15)}
    for code, start in starts.items():
        days = plan[code]["used"]
        if days <= 0:
            continue
        reason = f"DEMO: {code} availed"
        already = db.scalar(
            select(LeaveRequest.id).where(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.leave_type_id == lines[code].leave_type_id,
                LeaveRequest.reason == reason,
            )
        )
        if already is not None:
            continue
        db.add(
            LeaveRequest(
                employee_id=employee_id,
                leave_type_id=lines[code].leave_type_id,
                from_date=start,
                to_date=start + timedelta(days=int(days) - 1),
                is_half_day=False,
                days=days,
                reason=reason,
                status="Approved",
                approver_user_id=user_id,
                acted_at=datetime(2027, 1, 2, 10, 0),
                created_by_user_id=user_id,
                is_active=True,
            )
        )
        counts["requests"] += 1
    db.flush()


def _store_bucket(
    db: Session,
    employee: Employee,
    line: LeavePolicyLine,
    year: int,
    bucket: dict[str, Decimal],
    sunday_ids: dict[date, int],
    user_id: int | None,
    counts: dict[str, int],
) -> None:
    balance = LeaveBalance(
        employee_id=employee.id,
        leave_type_id=line.leave_type_id,
        leave_year=year,
        opening=bucket["opening"],
        accrued=bucket["credit"],
        availed=bucket["used"],
        encashed=ZERO,
        closing=bucket["closing"],
        created_by_user_id=user_id,
        is_active=True,
    )
    db.add(balance)
    db.flush()
    counts["balances"] += 1
    code = _code(db, line.leave_type_id)
    if code == "CO" and sunday_ids:
        for day, attendance_id in sunday_ids.items():
            _transaction(
                db, employee.id, line.leave_type_id, year, balance.id, "Credit", Decimal("1.0"),
                f"DEMO: Company Comp-Off approved for Sunday work on {day.isoformat()}", attendance_id, user_id, counts,
            )
    else:
        _transaction(
            db, employee.id, line.leave_type_id, year, balance.id, "Credit", bucket["credit"],
            f"DEMO: {code} credit for policy year {year}", None, user_id, counts,
        )
    if bucket["used"] > 0:
        _transaction(
            db, employee.id, line.leave_type_id, year, balance.id, "Debit", bucket["used"],
            f"DEMO: {code} consumed", None, user_id, counts,
        )
    if bucket["adjustment"] != 0:
        _transaction(
            db, employee.id, line.leave_type_id, year, balance.id, "Adjustment", bucket["adjustment"],
            f"DEMO: {code} balance adjustment", None, user_id, counts,
        )
    if bucket["expiry"] > 0:
        _transaction(
            db, employee.id, line.leave_type_id, year, balance.id, "Expiry", bucket["expiry"],
            f"DEMO: {code} expired", None, user_id, counts,
        )


def _transaction(
    db: Session,
    employee_id: int,
    leave_type_id: int,
    year: int,
    balance_id: int,
    kind: str,
    days: Decimal,
    remarks: str,
    source_id: int | None,
    user_id: int | None,
    counts: dict[str, int],
) -> None:
    db.add(
        LeaveBalanceTransaction(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            leave_year=year,
            leave_balance_id=balance_id,
            kind=kind,
            days=days,
            remarks=remarks,
            source_type=SOURCE,
            source_id=source_id,
            created_by_user_id=user_id,
            is_active=True,
        )
    )
    counts["transactions"] += 1


def _store_run(
    db: Session,
    employee: Employee,
    line: LeavePolicyLine,
    year: int,
    plan: dict[str, dict[str, Decimal]],
    dates: list[date],
    user_id: int | None,
    counts: dict[str, int],
) -> None:
    exists = db.scalar(
        select(LeaveEntitlementRun.id).where(
            LeaveEntitlementRun.employee_id == employee.id,
            LeaveEntitlementRun.leave_policy_line_id == line.id,
            LeaveEntitlementRun.leave_year == year,
        )
    )
    if exists is not None:
        return
    code = _code(db, line.leave_type_id)
    bucket = plan.get(code, _bucket(ZERO, ZERO, ZERO, ZERO, ZERO, ZERO))
    db.add(
        LeaveEntitlementRun(
            employee_id=employee.id,
            leave_policy_line_id=line.id,
            leave_year=year,
            eligibility_days=Decimal(len(dates)) if code == "EL" else bucket["evidence"],
            days_worked=Decimal(len(dates)) if code == "EL" else ZERO,
            deemed_days=ZERO,
            credited_days=bucket["credit"],
            created_by_user_id=user_id,
            is_active=True,
        )
    )
    counts["runs"] += 1


def _balance_exists(db: Session, employee_id: int, leave_type_id: int, year: int) -> bool:
    return (
        db.scalar(
            select(LeaveBalance.id).where(
                LeaveBalance.employee_id == employee_id,
                LeaveBalance.leave_type_id == leave_type_id,
                LeaveBalance.leave_year == year,
            )
        )
        is not None
    )


def _code(db: Session, leave_type_id: int) -> str:
    return db.get(LeaveType, leave_type_id).code


def _verify(db: Session) -> None:
    user_id = db.scalar(select(LeavePolicy.created_by_user_id).where(LeavePolicy.name == POLICY_NAME))
    employee_id = db.execute(text("SELECT employee_id FROM core.app_user WHERE id = :id"), {"id": user_id}).scalar()
    actor = CurrentUser(
        id=user_id or 0,
        employee_id=employee_id,
        username="demo-check",
        display_name="Demo check",
        email=None,
        default_branch_id=None,
        roles=frozenset({"ADMIN"}),
        permissions=frozenset({"hr.leave.view", "hr.leave.manage"}),
        branch_ids=None,
        principal_ids=None,
    )
    policy_id = db.scalar(select(LeavePolicy.id).where(LeavePolicy.name == POLICY_NAME))
    board = balance_board(
        db, actor, year=2027, policy_id=policy_id, department_id=None, branch_id=None,
        search=None, page=1, page_size=25, sort="employeeCode",
    )
    print(
        "api 2027",
        f"employees {board.total}",
        f"assigned {board.summary.with_assigned_policy}",
        f"generated {board.summary.entitlement_generated}",
        f"review {board.summary.requires_review}",
    )
    sql_closing = db.execute(text("""
        SELECT t.code, SUM(b.closing)
        FROM hr.leave_balance b
        JOIN hr.leave_type t ON t.id = b.leave_type_id
        WHERE b.leave_year = 2027 AND t.code IN (N'EL', N'SL', N'CL', N'CO')
        GROUP BY t.code
        ORDER BY t.code
    """)).all()
    api_totals = {"EL": ZERO, "SL": ZERO, "CL": ZERO, "CO": ZERO}
    for item in board.items:
        api_totals["EL"] += item.el.balance
        api_totals["SL"] += item.sl.balance
        api_totals["CL"] += item.cl.balance
        api_totals["CO"] += item.comp_off_balance
        print(
            item.employee_code,
            f"EL {item.el.opening}/{item.el.credited}/{item.el.used}/{item.el.balance}",
            f"SL {item.sl.opening}/{item.sl.credited}/{item.sl.used}/{item.sl.balance}",
            f"CL {item.cl.opening}/{item.cl.credited}/{item.cl.used}/{item.cl.balance}",
            f"CO {item.comp_off_balance}",
        )
    print("sql closing", [(code, Decimal(total)) for code, total in sql_closing])
    print("api closing", dict(api_totals))
    sample = board.items[0]
    detail = balance_detail(db, actor, sample.employee_id, 2027)
    print(f"transactions {sample.employee_code}", len(detail.transactions), "history", len(detail.leave_history), flush=True)
    reviewed = next(item for item in board.items if item.employee_code == "EMP0005")
    reviewed_detail = balance_detail(db, actor, reviewed.employee_id, 2027)
    for row in reviewed_detail.types:
        if row.code in {"EL", "CO"}:
            print(row.code, "adjustment", row.adjustments, "expired", row.expired, "closing", row.closing, flush=True)
    if employee_id is not None:
        code = db.scalar(select(Employee.employee_code).where(Employee.id == employee_id))
        mine = LeaveMineRepository(db).balances(actor, 2026)
        print(
            "my leave",
            code,
            [(item.code, item.available) for item in mine.items if item.code in {"EL", "SL", "CL", "CO"}],
            flush=True,
        )
    else:
        print("my leave skipped: the policy user has no employee link", flush=True)


def _rollback(db: Session) -> dict[str, int]:
    removed = {
        "runs": _exec(db, """
            DELETE r FROM hr.leave_entitlement_run r
            WHERE EXISTS (
                SELECT 1 FROM hr.leave_balance_transaction t
                WHERE t.source_type = N'demo.leave' AND t.employee_id = r.employee_id AND t.leave_year = r.leave_year
            )
            AND NOT EXISTS (
                SELECT 1 FROM hr.leave_balance_transaction t
                WHERE t.employee_id = r.employee_id AND t.leave_year = r.leave_year
                  AND (t.source_type IS NULL OR t.source_type <> N'demo.leave')
            )
        """),
        "attendance": _exec(db, """
            DELETE a FROM hr.attendance a
            WHERE a.source = N'Manual'
              AND a.attendance_date >= '2026-01-01' AND a.attendance_date < '2027-01-01'
              AND EXISTS (
                SELECT 1 FROM hr.leave_balance_transaction t
                WHERE t.source_type = N'demo.leave' AND t.employee_id = a.employee_id
                  AND t.created_by_user_id = a.created_by_user_id
              )
              AND NOT EXISTS (
                SELECT 1 FROM hr.attendance other
                WHERE other.employee_id = a.employee_id
                  AND other.attendance_date >= '2026-01-01' AND other.attendance_date < '2027-01-01'
                  AND (other.source <> N'Manual' OR other.created_by_user_id IS NULL OR other.created_by_user_id <> a.created_by_user_id)
              )
        """),
        "class": _exec(db, """
            DELETE FROM hr.leave_attendance_class
            WHERE attendance_status = N'Present' AND day_weight = 1.0
              AND (SELECT COUNT(*) FROM hr.leave_attendance_class) = 1
              AND created_by_user_id IN (
                SELECT DISTINCT created_by_user_id FROM hr.leave_balance_transaction WHERE source_type = N'demo.leave'
              )
        """),
        "requests": _exec(db, "DELETE FROM hr.leave_request WHERE reason LIKE N'DEMO:%'"),
    }
    db.execute(text("""
        SELECT leave_balance_id AS id INTO #demo_balance
        FROM hr.leave_balance_transaction
        WHERE source_type = N'demo.leave' AND leave_balance_id IS NOT NULL
        GROUP BY leave_balance_id
        HAVING SUM(CASE WHEN source_type <> N'demo.leave' THEN 1 ELSE 0 END) = 0
    """))
    removed["transactions"] = _exec(db, "DELETE FROM hr.leave_balance_transaction WHERE source_type = N'demo.leave'")
    removed["balances"] = _exec(db, """
        DELETE b FROM hr.leave_balance b
        WHERE b.id IN (SELECT id FROM #demo_balance)
          AND NOT EXISTS (SELECT 1 FROM hr.leave_balance_transaction t WHERE t.leave_balance_id = b.id)
    """)
    return removed


def _exec(db: Session, statement: str) -> int:
    result = db.execute(text(statement))
    return result.rowcount or 0


if __name__ == "__main__":
    main()
