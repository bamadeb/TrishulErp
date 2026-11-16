"""Idempotent November 2026 leave requests for the existing TrishulDev employees.

Refuses every database except TrishulDev. Selects active employees, leave types and balances
from the database. A second run inserts nothing. Demo requests use reasons that start with
``DEMO-REQ:``. Approved rows increase ``availed`` and reduce ``closing`` on the existing
financial-year balance, and write a ``demo.leave_request`` debit. Pending and rejected rows
do not change balances. Employee master rows, policies and leave types are not modified.

The saved Odisha policy starts on 1 January 2027, so the live apply action still rejects a
November 2026 date. These rows are development display data. Sick leave is not approved,
because that policy line requires a document and a leave request cannot store one. Comp-Off
is used only where the policy line is configured and the current closing balance covers it.

    uv run --no-sync python scripts/seed_demo_leave_requests.py
    uv run --no-sync python scripts/seed_demo_leave_requests.py --rollback
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))

from trishul_api.auth import CurrentUser  # noqa: E402
from trishul_api.config import get_settings  # noqa: E402
from trishul_api.db.engine import create_db_engine  # noqa: E402
from trishul_api.db.models import (  # noqa: E402
    EmployeeShift,
    Holiday,
    LeaveBalance,
    LeaveBalanceTransaction,
    LeavePolicy,
    LeavePolicyLine,
    LeaveRequest,
    LeaveType,
    StatusHistory,
)
from trishul_api.modules.hr.leave.mine_repository import _financial_year, _off_days, _service_months  # noqa: E402
from trishul_api.modules.hr.leave.request_ops import LeaveRequestRepository  # noqa: E402
from trishul_api.modules.hr.leave.request_schemas import LeaveRequestFilter, LeaveRequestQuery  # noqa: E402
from trishul_api.secrets import create_secret_provider  # noqa: E402

MARKER = "DEMO-REQ:"
SOURCE = "demo.leave_request"
MONTH_START = date(2026, 11, 1)
MONTH_END = date(2026, 11, 30)
YEAR = _financial_year(MONTH_START)
SLOTS: tuple[tuple[str, str, int, str], ...] = (
    ("Approved", "CL", 1, "Family function"),
    ("Approved", "CL", 1, "Personal work"),
    ("Approved", "CL", 2, "House repair"),
    ("Approved", "EL", 1, "Travel home"),
    ("Approved", "EL", 2, "Wedding in the family"),
    ("Approved", "EL", 1, "Outstation visit"),
    ("Approved", "CO", 1, "Compensatory off for extra duty"),
    ("Approved", "CL", 1, "Bank work"),
    ("Pending", "CL", 1, "Personal errand"),
    ("Pending", "CL", 1, "Parent meeting"),
    ("Pending", "EL", 1, "Home town visit"),
    ("Pending", "EL", 1, "Family ceremony"),
    ("Pending", "SL", 1, "Fever and rest"),
    ("Pending", "SL", 1, "Medical appointment"),
    ("Pending", "SL", 2, "Recovery after treatment"),
    ("Pending", "CO", 1, "Compensatory off for holiday duty"),
    ("Pending", "CL", 1, "Vehicle servicing"),
    ("Pending", "CL", 2, "Family visit"),
    ("Pending", "EL", 2, "Out of station"),
    ("Pending", "EL", 1, "Ceremony at home"),
    ("Rejected", "CL", 1, "Personal work on a busy day"),
    ("Rejected", "SL", 1, "Clinic visit"),
    ("Rejected", "EL", 1, "Short travel"),
)


@dataclass
class Person:
    id: int
    code: str
    name: str
    department: str
    joining: date | None
    branch_id: int


def main() -> None:
    engine = _engine()
    with Session(engine) as db:
        _require_dev(db)
        if "--rollback" in sys.argv:
            removed = _rollback(db)
            db.commit()
            print("rolled back", removed)
        else:
            inserted = _seed(db)
            db.commit()
            print("inserted", inserted)
    if "--rollback" not in sys.argv:
        with Session(engine) as db:
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


def _seed(db: Session) -> int:
    existing = _marked(db)
    if len(existing) >= len(SLOTS):
        print(f"{len(existing)} demo requests already present; nothing inserted", flush=True)
        return 0
    if existing:
        raise SystemExit("A partial DEMO-REQ set exists. Run with --rollback before seeding again.")
    people = _people(db)
    types = _types(db)
    policy = db.scalars(select(LeavePolicy).where(LeavePolicy.is_active == True)).one()  # noqa: E712
    lines = {
        types[line.leave_type_id]: line
        for line in db.scalars(
            select(LeavePolicyLine).where(
                LeavePolicyLine.leave_policy_id == policy.id,
                LeavePolicyLine.is_active == True,  # noqa: E712
            )
        ).all()
    }
    print(
        f"policy {policy.name} effective {policy.effective_from.isoformat()} "
        f"employees {len(people)} year {YEAR}",
        flush=True,
    )
    balances = _balances(db, types)
    before = {key: (row.availed or Decimal("0.0"), row.closing or Decimal("0.0")) for key, row in balances.items()}
    remaining = {key: closing for key, (_, closing) in before.items()}
    user_id = db.execute(text("SELECT TOP 1 id FROM core.app_user WHERE is_active = 1 ORDER BY id")).scalar()
    if user_id is None:
        raise SystemExit("No active application user is available to record the demo requests.")
    occupied = _occupied(db)
    chosen = _place(people, lines, {code: type_id for type_id, code in types.items()}, remaining, occupied)
    approved_days: dict[tuple[int, int], Decimal] = {}
    for person, status, code, span, reason in chosen:
        leave_type_id = next(type_id for type_id, type_code in types.items() if type_code == code)
        days = Decimal(len(span)).quantize(Decimal("0.1"))
        applied = span[0] - timedelta(days=2)
        if person.joining is not None and applied < person.joining:
            applied = person.joining
        acted = datetime.combine(applied + timedelta(days=1), datetime.min.time()).replace(hour=11)
        row = LeaveRequest(
            employee_id=person.id,
            leave_type_id=leave_type_id,
            from_date=span[0],
            to_date=span[-1],
            is_half_day=False,
            days=days,
            reason=reason,
            status=status,
            approver_user_id=None if status == "Pending" else int(user_id),
            acted_at=None if status == "Pending" else acted,
            created_at=datetime.combine(applied, datetime.min.time()).replace(hour=9, minute=30),
            created_by_user_id=int(user_id),
            is_active=True,
        )
        db.add(row)
        db.flush()
        _history(db, row.id, status, reason, int(user_id), row.created_at, acted)
        if status == "Approved":
            key = (person.id, leave_type_id)
            _deduct(balances[key], days, int(user_id))
            _debit(db, person.id, leave_type_id, balances[key].id, row.id, days, int(user_id))
            approved_days[key] = approved_days.get(key, Decimal("0.0")) + days
        print(f"{status} {person.code} {person.department} {code} {span[0].isoformat()} {days} {reason}", flush=True)
    _check_balances(balances, before, approved_days)
    return len(chosen)


def _place(
    people: list[Person],
    lines: dict[str, LeavePolicyLine],
    type_ids: dict[str, int],
    remaining: dict[tuple[int, int], Decimal],
    occupied: dict[int, set[date]],
) -> list[tuple[Person, str, str, list[date], str]]:
    sl_months = lines["SL"].minimum_service_months or 0
    co_ready = lines["CO"].compensatory_basis == "COMPANY_COMP_OFF"
    dept_used = {person.department: 0 for person in people}
    person_used = {person.id: 0 for person in people}
    placed: list[tuple[Person, str, str, list[date], str]] = []
    for index, (status, code, days, phrase) in enumerate(SLOTS, start=1):
        reason = f"{MARKER} {index:02d} {phrase}"
        person, span = _pick(
            people, status, code, days, sl_months, co_ready, type_ids, remaining, occupied, dept_used, person_used
        )
        for day in span:
            occupied.setdefault(person.id, set()).add(day)
        if status != "Rejected":
            remaining[(person.id, type_ids[code])] -= Decimal(days)
        dept_used[person.department] += 1
        person_used[person.id] += 1
        placed.append((person, status, code, span, reason))
    counts = {status: sum(1 for item in placed if item[1] == status) for status in ("Pending", "Approved", "Rejected")}
    if counts != {"Pending": 12, "Approved": 8, "Rejected": 3}:
        raise SystemExit(f"The placed set is {counts}, not 12 pending, 8 approved and 3 rejected.")
    return placed


def _pick(
    people: list[Person],
    status: str,
    code: str,
    days: int,
    sl_months: int,
    co_ready: bool,
    type_ids: dict[str, int],
    remaining: dict[tuple[int, int], Decimal],
    occupied: dict[int, set[date]],
    dept_used: dict[str, int],
    person_used: dict[int, int],
) -> tuple[Person, list[date]]:
    ranked = sorted(people, key=lambda person: (dept_used[person.department], person_used[person.id], person.code))
    for person in ranked:
        if not _eligible(person, status, code, days, sl_months, co_ready, type_ids, remaining):
            continue
        span = _span(person, days, occupied.get(person.id, set()))
        if span is not None:
            return person, span
    raise SystemExit(f"No employee can take {status} {code} for {days} day(s) without overlap or a short balance.")


def _eligible(
    person: Person,
    status: str,
    code: str,
    days: int,
    sl_months: int,
    co_ready: bool,
    type_ids: dict[str, int],
    remaining: dict[tuple[int, int], Decimal],
) -> bool:
    if code == "SL" and (status == "Approved" or _service_months(person.joining, MONTH_START) < sl_months):
        return False
    if code == "CO" and not co_ready:
        return False
    if status == "Rejected":
        return True
    return remaining.get((person.id, type_ids[code]), Decimal("0")) >= Decimal(days)


def _span(person: Person, days: int, occupied: set[date]) -> list[date] | None:
    free = [day for day in _working_days(person) if day not in occupied]
    if days == 1:
        return [free[0]] if free else None
    for index, day in enumerate(free[:-1]):
        if free[index + 1] == day + timedelta(days=1):
            return [day, free[index + 1]]
    return None


def _working_days(person: Person) -> list[date]:
    holidays = getattr(_working_days, "holidays", set())
    offs = getattr(_working_days, "offs", {})
    off = offs.get(person.id, {6})
    found: list[date] = []
    cursor = MONTH_START
    while cursor <= MONTH_END:
        joined = person.joining is None or cursor >= person.joining
        if joined and cursor.weekday() not in off and cursor not in holidays:
            found.append(cursor)
        cursor += timedelta(days=1)
    return found


def _people(db: Session) -> list[Person]:
    rows = db.execute(text("""
        SELECT e.id, e.employee_code, e.first_name, e.last_name, d.name, e.date_of_joining, e.branch_id
        FROM core.employee e
        LEFT JOIN hr.department d ON d.id = e.department_id
        WHERE e.is_active = 1 AND e.status = N'Active'
        ORDER BY e.employee_code
    """)).all()
    people = [
        Person(
            id=int(row[0]),
            code=row[1],
            name=" ".join(part for part in (row[2], row[3]) if part),
            department=row[4] or "Unassigned",
            joining=row[5],
            branch_id=int(row[6]),
        )
        for row in rows
    ]
    if len(people) < 3:
        raise SystemExit("At least three active employees are required.")
    holidays: set[date] = set()
    for person in people:
        holidays.update(_holiday_dates(db, person.branch_id))
    _working_days.holidays = holidays  # type: ignore[attr-defined]
    _working_days.offs = {person.id: _weekly_off(db, person.id) for person in people}  # type: ignore[attr-defined]
    print(f"active employees {len(people)}; November holidays {len(holidays)}", flush=True)
    return people


def _types(db: Session) -> dict[int, str]:
    rows = db.execute(select(LeaveType.id, LeaveType.code).where(LeaveType.is_active == True)).all()  # noqa: E712
    types = {int(type_id): code for type_id, code in rows}
    missing = {"CL", "EL", "SL", "CO"} - set(types.values())
    if missing:
        raise SystemExit(f"Missing leave types: {', '.join(sorted(missing))}")
    return types


def _balances(db: Session, types: dict[int, str]) -> dict[tuple[int, int], LeaveBalance]:
    wanted = {type_id for type_id, code in types.items() if code in {"CL", "EL", "SL", "CO"}}
    rows = db.scalars(
        select(LeaveBalance)
        .where(
            LeaveBalance.leave_year == YEAR,
            LeaveBalance.is_active == True,  # noqa: E712
            LeaveBalance.leave_type_id.in_(wanted),
        )
        .order_by(LeaveBalance.id)
    ).all()
    return {(row.employee_id, row.leave_type_id): row for row in rows}


def _occupied(db: Session) -> dict[int, set[date]]:
    rows = db.scalars(select(LeaveRequest).where(LeaveRequest.is_active == True)).all()  # noqa: E712
    occupied: dict[int, set[date]] = {}
    for row in rows:
        if row.to_date < MONTH_START or row.from_date > MONTH_END:
            continue
        cursor = max(row.from_date, MONTH_START)
        while cursor <= min(row.to_date, MONTH_END):
            occupied.setdefault(row.employee_id, set()).add(cursor)
            cursor += timedelta(days=1)
    return occupied


def _holiday_dates(db: Session, branch_id: int) -> set[date]:
    rows = db.scalars(
        select(Holiday.holiday_date).where(
            Holiday.is_active == True,  # noqa: E712
            Holiday.holiday_date >= MONTH_START,
            Holiday.holiday_date <= MONTH_END,
            or_(Holiday.branch_id.is_(None), Holiday.branch_id == branch_id),
        )
    ).all()
    return set(rows)


def _weekly_off(db: Session, employee_id: int) -> set[int]:
    raw = db.execute(
        select(EmployeeShift.weekly_off_days)
        .where(
            EmployeeShift.employee_id == employee_id,
            EmployeeShift.is_active == True,  # noqa: E712
            EmployeeShift.from_date <= MONTH_START,
            or_(EmployeeShift.to_date.is_(None), EmployeeShift.to_date >= MONTH_START),
        )
        .order_by(EmployeeShift.from_date.desc(), EmployeeShift.id.desc())
        .limit(1)
    ).scalar()
    return _off_days(raw)


def _history(
    db: Session, request_id: int, status: str, reason: str, user_id: int, applied: datetime, acted: datetime
) -> None:
    db.add(StatusHistory(
        entity_type="hr.leave_request",
        entity_id=request_id,
        from_status=None,
        to_status="Pending",
        changed_by_user_id=user_id,
        changed_at=applied,
        remarks=reason,
    ))
    if status == "Pending":
        return
    db.add(StatusHistory(
        entity_type="hr.leave_request",
        entity_id=request_id,
        from_status="Pending",
        to_status=status,
        changed_by_user_id=user_id,
        changed_at=acted,
        remarks="Approved." if status == "Approved" else f"{MARKER} The requested dates are not available.",
    ))


def _deduct(balance: LeaveBalance, days: Decimal, user_id: int) -> None:
    closing = balance.closing or Decimal("0.0")
    if closing < days:
        raise SystemExit("Approval would make a leave balance negative.")
    balance.availed = (balance.availed or Decimal("0.0")) + days
    balance.closing = closing - days
    balance.updated_by_user_id = user_id


def _debit(
    db: Session, employee_id: int, leave_type_id: int, balance_id: int, request_id: int, days: Decimal, user_id: int
) -> None:
    db.add(LeaveBalanceTransaction(
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        leave_year=YEAR,
        leave_balance_id=balance_id,
        kind="Debit",
        days=days,
        remarks=f"{MARKER} approved deduction",
        source_type=SOURCE,
        source_id=request_id,
        created_by_user_id=user_id,
        is_active=True,
    ))


def _check_balances(
    balances: dict[tuple[int, int], LeaveBalance],
    before: dict[tuple[int, int], tuple[Decimal, Decimal]],
    approved_days: dict[tuple[int, int], Decimal],
) -> None:
    for key, row in balances.items():
        old_availed, old_closing = before[key]
        used = approved_days.get(key, Decimal("0.0"))
        availed = row.availed or Decimal("0.0")
        closing = row.closing or Decimal("0.0")
        if availed - old_availed != used or old_closing - closing != used:
            raise SystemExit(f"Balance movement for employee {key[0]} does not match the approved days.")
        if used == 0 and (availed != old_availed or closing != old_closing):
            raise SystemExit("A pending or rejected request changed a leave balance.")


def _latest_balance(db: Session, employee_id: int, leave_type_id: int) -> LeaveBalance | None:
    rows = db.scalars(
        select(LeaveBalance)
        .where(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.leave_year == YEAR,
            LeaveBalance.is_active == True,  # noqa: E712
        )
        .order_by(LeaveBalance.id)
    ).all()
    return rows[-1] if rows else None


def _marked(db: Session) -> list[LeaveRequest]:
    return list(
        db.scalars(
            select(LeaveRequest).where(
                LeaveRequest.reason.like(f"{MARKER}%"),
                LeaveRequest.is_active == True,  # noqa: E712
            )
        ).all()
    )


def _rollback(db: Session) -> int:
    rows = _marked(db)
    for row in rows:
        if row.status == "Approved":
            balance = _latest_balance(db, row.employee_id, row.leave_type_id)
            if balance is not None:
                removed = min(balance.availed or Decimal("0.0"), row.days)
                balance.availed = (balance.availed or Decimal("0.0")) - removed
                balance.closing = (balance.closing or Decimal("0.0")) + removed
        db.execute(text(
            "DELETE FROM hr.leave_balance_transaction WHERE source_type = :source AND source_id = :request_id"
        ), {"source": SOURCE, "request_id": row.id})
        db.execute(text(
            "DELETE FROM core.status_history WHERE entity_type = N'hr.leave_request' AND entity_id = :request_id"
        ), {"request_id": row.id})
        db.delete(row)
    return len(rows)


def _verify(db: Session) -> None:
    actor = CurrentUser(
        id=1,
        employee_id=None,
        username="seed-check",
        display_name="Seed check",
        email=None,
        default_branch_id=None,
        roles=frozenset({"ADMIN"}),
        permissions=frozenset({"hr.leave.view", "hr.leave.manage"}),
        branch_ids=None,
        principal_ids=None,
    )
    repo = LeaveRequestRepository(db)
    window = LeaveRequestFilter(from_date=MONTH_START, to_date=MONTH_END)
    summary = repo.summary(actor, window)
    print(
        f"summary pending {summary.pending} approved {summary.approved} "
        f"rejected {summary.rejected} total {summary.total}",
        flush=True,
    )
    for status in ("Pending", "Approved", "Rejected", None):
        page = repo.page(actor, LeaveRequestQuery(
            from_date=MONTH_START, to_date=MONTH_END, status=status, page=1, page_size=50
        ))
        print(f"list {status or 'All'} {page.total}", flush=True)
        if status is None and page.items:
            item = page.items[0]
            print(
                f"sample {item.display_id} {item.employee.code} {item.employee.name} "
                f"{item.employee.department} {item.leave_type} {item.from_date} {item.days} {item.status}",
                flush=True,
            )


if __name__ == "__main__":
    main()
