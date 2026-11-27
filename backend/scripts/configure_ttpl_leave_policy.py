"""Configure TTPL Leave Policy on TrishulDev only.

Idempotent: upserts AL/CL/CO types and settings, TTPL policy + lines, national holidays,
and EMP0015 confirmation / assignment / balances. Never deletes leave_request,
leave_balance_transaction, or audit history. Obsolete types and policies are deactivated
(is_active=0) only. Credits/adjustments use source_type ``ttpl.leave.config``.

    uv run --no-sync python scripts/configure_ttpl_leave_policy.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))

from trishul_api.config import get_settings  # noqa: E402
from trishul_api.db.engine import create_db_engine  # noqa: E402
from trishul_api.db.models import (  # noqa: E402
    AppUser,
    Employee,
    EmploymentHistory,
    Holiday,
    LeaveBalance,
    LeaveBalanceTransaction,
    LeavePolicy,
    LeavePolicyAssignment,
    LeavePolicyLine,
    LeaveType,
    LeaveTypeSetting,
)
from trishul_api.secrets import create_secret_provider  # noqa: E402

SOURCE = "ttpl.leave.config"
POLICY_NAME = "TTPL Leave Policy"
EFFECTIVE_FROM = date(2026, 1, 1)
OBSOLETE_TYPE_CODES = ("EL", "SL", "ML", "PL", "WR", "LWP")
KEEP_TYPE_CODES = ("AL", "CL", "CO")
NATIONAL = (
    ("Republic Day", 1, 26),
    ("May Day", 5, 1),
    ("Independence Day", 8, 15),
    ("Gandhi Jayanti", 10, 2),
)
ZERO = Decimal("0.0")
AL_ACCRUED = Decimal("15.0")
CL_ACCRUED = Decimal("6.0")
DAY_BEFORE = EFFECTIVE_FROM - timedelta(days=1)


def main() -> None:
    engine = _engine()
    with Session(engine) as db:
        _require_dev(db)
        backup_path = _backup(db)
        print(f"backup {backup_path}", flush=True)
        report = _configure(db)
        db.commit()
        _print_report(db, report)
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


def _configure(db: Session) -> dict[str, Any]:
    types = _ensure_leave_types(db)
    _deactivate_obsolete_types(db)
    policy = _ensure_policy(db)
    _deactivate_other_policies(db, policy.id)
    lines = _ensure_policy_lines(db, policy, types)
    holiday_counts = _ensure_holidays(db)
    jyoti = _configure_jyoti(db, policy, types)
    return {
        "types": types,
        "policy": policy,
        "lines": lines,
        "holiday_counts": holiday_counts,
        "jyoti": jyoti,
    }


def _ensure_leave_types(db: Session) -> dict[str, LeaveType]:
    specs: dict[str, dict[str, Any]] = {
        "AL": {
            "name": "Annual Leave",
            "annual_quota": Decimal("15.0"),
            "carry_forward_max": Decimal("15.0"),
            "is_paid": True,
            "is_encashable": False,
            "accrual_applicable": False,
            "half_day_allowed": True,
            "description": "Annual Leave",
        },
        "CL": {
            "name": "Casual Leave",
            "annual_quota": Decimal("6.0"),
            "carry_forward_max": None,
            "is_paid": True,
            "is_encashable": False,
            "accrual_applicable": True,
            "half_day_allowed": True,
            "description": "Casual Leave",
        },
        "CO": {
            "name": "Compensatory Off",
            "annual_quota": None,
            "carry_forward_max": None,
            "is_paid": True,
            "is_encashable": False,
            "accrual_applicable": False,
            "half_day_allowed": True,
            "description": "Compensatory Off / C-Off",
        },
    }
    out: dict[str, LeaveType] = {}
    for code, spec in specs.items():
        row = db.scalars(select(LeaveType).where(LeaveType.code == code)).first()
        if row is None:
            row = LeaveType(
                code=code,
                name=spec["name"],
                annual_quota=spec["annual_quota"],
                carry_forward_max=spec["carry_forward_max"],
                is_paid=spec["is_paid"],
                is_encashable=spec["is_encashable"],
                is_active=True,
            )
            db.add(row)
            db.flush()
            print(f"leave_type created {code}", flush=True)
        else:
            row.name = spec["name"]
            row.annual_quota = spec["annual_quota"]
            row.carry_forward_max = spec["carry_forward_max"]
            row.is_paid = spec["is_paid"]
            row.is_encashable = spec["is_encashable"]
            row.is_active = True
            print(f"leave_type updated {code}", flush=True)
        setting = db.get(LeaveTypeSetting, row.id)
        if setting is None:
            db.add(
                LeaveTypeSetting(
                    leave_type_id=row.id,
                    description=spec["description"],
                    accrual_applicable=spec["accrual_applicable"],
                    half_day_allowed=spec["half_day_allowed"],
                    attachment_required=False,
                    max_consecutive_days=None,
                )
            )
        else:
            setting.description = spec["description"]
            setting.accrual_applicable = spec["accrual_applicable"]
            setting.half_day_allowed = spec["half_day_allowed"]
        out[code] = row
    db.flush()
    return out


def _deactivate_obsolete_types(db: Session) -> None:
    active_keep = db.scalars(
        select(LeaveType).where(LeaveType.code.in_(KEEP_TYPE_CODES), LeaveType.is_active == True)  # noqa: E712
    ).all()
    if not active_keep:
        raise SystemExit("Refusing to deactivate obsolete types: AL/CL/CO are not active.")
    for code in OBSOLETE_TYPE_CODES:
        row = db.scalars(select(LeaveType).where(LeaveType.code == code)).first()
        if row is None or not row.is_active:
            continue
        row.is_active = False
        print(f"leave_type deactivated {code}", flush=True)
    db.flush()


def _ensure_policy(db: Session) -> LeavePolicy:
    row = db.scalars(select(LeavePolicy).where(LeavePolicy.name == POLICY_NAME)).first()
    if row is None:
        row = LeavePolicy(
            name=POLICY_NAME,
            employee_type="Permanent",
            year_basis="CALENDAR",
            assignment_mode="AUTOMATIC",
            applies_during_probation=False,
            negative_balance_allowed=False,
            effective_from=EFFECTIVE_FROM,
            effective_to=None,
            is_active=True,
        )
        db.add(row)
        db.flush()
        print(f"policy created {POLICY_NAME}", flush=True)
    else:
        row.employee_type = "Permanent"
        row.year_basis = "CALENDAR"
        row.assignment_mode = "AUTOMATIC"
        row.applies_during_probation = False
        row.negative_balance_allowed = False
        row.effective_from = EFFECTIVE_FROM
        row.effective_to = None
        row.is_active = True
        print(f"policy updated {POLICY_NAME}", flush=True)
    db.flush()
    return row


def _deactivate_other_policies(db: Session, keep_id: int) -> None:
    others = db.scalars(
        select(LeavePolicy).where(LeavePolicy.id != keep_id, LeavePolicy.is_active == True)  # noqa: E712
    ).all()
    for row in others:
        row.is_active = False
        print(f"policy deactivated {row.name}", flush=True)
    db.flush()


def _ensure_policy_lines(
    db: Session, policy: LeavePolicy, types: dict[str, LeaveType]
) -> dict[str, LeavePolicyLine]:
    specs: dict[str, dict[str, Any]] = {
        "AL": {
            "annual_entitlement": Decimal("15.0"),
            "accrual_frequency": "Yearly",
            "calculation_method": "FIXED",
            "benefit_class": "COMPANY",
            "carry_forward": True,
            "max_accumulation": Decimal("30.0"),
            "encashment_eligible": False,
            "exclude_boundary_holidays": False,
            "max_backdate_days": 0,
            "backdate_requires_authorization": False,
            "compensatory_basis": "NONE",
            "compensatory_expiry_months": None,
        },
        "CL": {
            "annual_entitlement": Decimal("6.0"),
            "accrual_frequency": "Yearly",
            "calculation_method": "FIXED",
            "benefit_class": "COMPANY",
            "carry_forward": False,
            "max_accumulation": None,
            "encashment_eligible": False,
            "exclude_boundary_holidays": True,
            "max_backdate_days": 1,
            "backdate_requires_authorization": False,
            "compensatory_basis": "NONE",
            "compensatory_expiry_months": None,
        },
        "CO": {
            "annual_entitlement": ZERO,
            "accrual_frequency": "None",
            "calculation_method": "FIXED",
            "benefit_class": "COMPANY",
            "carry_forward": False,
            "max_accumulation": None,
            "encashment_eligible": False,
            "exclude_boundary_holidays": False,
            "max_backdate_days": 0,
            "backdate_requires_authorization": False,
            "compensatory_basis": "COMPANY_COMP_OFF",
            "compensatory_expiry_months": 3,
        },
    }
    existing = {
        line.leave_type_id: line
        for line in db.scalars(
            select(LeavePolicyLine).where(LeavePolicyLine.leave_policy_id == policy.id)
        ).all()
    }
    keep_ids = {types[code].id for code in KEEP_TYPE_CODES}
    for leave_type_id, line in existing.items():
        if leave_type_id not in keep_ids and line.is_active:
            line.is_active = False
            print(f"policy_line deactivated leave_type_id={leave_type_id}", flush=True)

    out: dict[str, LeavePolicyLine] = {}
    for code, spec in specs.items():
        leave_type = types[code]
        line = existing.get(leave_type.id)
        if line is None:
            line = LeavePolicyLine(
                leave_policy_id=policy.id,
                leave_type_id=leave_type.id,
                annual_entitlement=spec["annual_entitlement"],
                accrual_frequency=spec["accrual_frequency"],
                carry_forward=spec["carry_forward"],
                max_accumulation=spec["max_accumulation"],
                encashment_eligible=spec["encashment_eligible"],
                calculation_method=spec["calculation_method"],
                benefit_class=spec["benefit_class"],
                exclude_boundary_holidays=spec["exclude_boundary_holidays"],
                compensatory_basis=spec["compensatory_basis"],
                compensatory_expiry_months=spec["compensatory_expiry_months"],
                max_backdate_days=spec["max_backdate_days"],
                backdate_requires_authorization=spec["backdate_requires_authorization"],
                joining_year_rule="NONE",
                document_required=False,
                is_active=True,
            )
            db.add(line)
            print(f"policy_line created {code}", flush=True)
        else:
            line.annual_entitlement = spec["annual_entitlement"]
            line.accrual_frequency = spec["accrual_frequency"]
            line.carry_forward = spec["carry_forward"]
            line.max_accumulation = spec["max_accumulation"]
            line.encashment_eligible = spec["encashment_eligible"]
            line.calculation_method = spec["calculation_method"]
            line.benefit_class = spec["benefit_class"]
            line.exclude_boundary_holidays = spec["exclude_boundary_holidays"]
            line.compensatory_basis = spec["compensatory_basis"]
            line.compensatory_expiry_months = spec["compensatory_expiry_months"]
            line.max_backdate_days = spec["max_backdate_days"]
            line.backdate_requires_authorization = spec["backdate_requires_authorization"]
            line.is_active = True
            print(f"policy_line updated {code}", flush=True)
        out[code] = line
    db.flush()
    return out


def _holiday_years() -> list[int]:
    years = {2026, 2027, date.today().year}
    return sorted(years)


def _ensure_holidays(db: Session) -> dict[str, int]:
    years = _holiday_years()
    national_keys = {
        (date(year, month, day), name.lower()) for year in years for name, month, day in NATIONAL
    }
    upserted = 0
    for year in years:
        for name, month, day in NATIONAL:
            when = date(year, month, day)
            existing_id = db.scalar(
                select(Holiday.id)
                .where(Holiday.holiday_date == when, func.lower(Holiday.name) == name.lower())
                .limit(1)
            )
            if existing_id is None:
                db.execute(
                    Holiday.__table__.insert().values(
                        branch_id=None,
                        state_id=None,
                        holiday_date=when,
                        name=name,
                        holiday_type="National",
                        description="TTPL national holiday",
                        is_active=True,
                    )
                )
                upserted += 1
                print(f"holiday inserted {when.isoformat()} {name}", flush=True)
            else:
                db.execute(
                    Holiday.__table__.update()
                    .where(Holiday.id == existing_id)
                    .values(
                        branch_id=None,
                        state_id=None,
                        holiday_type="National",
                        description="TTPL national holiday",
                        is_active=True,
                        name=name,
                    )
                )
                print(f"holiday upserted {when.isoformat()} {name}", flush=True)
    db.flush()

    start = date(min(years), 1, 1)
    candidates = db.scalars(
        select(Holiday).where(
            Holiday.holiday_date >= start,
            Holiday.is_active == True,  # noqa: E712
            Holiday.holiday_type.in_(("Festival", "Optional")),
        )
    ).all()
    deactivated = 0
    for row in candidates:
        key = (row.holiday_date, row.name.lower())
        if key in national_keys:
            continue
        row.is_active = False
        deactivated += 1
    db.flush()
    print(f"holidays national upserted/checked {upserted}; festival/optional deactivated {deactivated}", flush=True)

    active_from = date(2026, 1, 1)
    active_rows = db.execute(
        select(Holiday.holiday_type, func.count())
        .where(Holiday.is_active == True, Holiday.holiday_date >= active_from)  # noqa: E712
        .group_by(Holiday.holiday_type)
    ).all()
    return {str(holiday_type): int(count) for holiday_type, count in active_rows}


def _configure_jyoti(
    db: Session, policy: LeavePolicy, types: dict[str, LeaveType]
) -> dict[str, Any]:
    employee = db.scalars(select(Employee).where(Employee.employee_code == "EMP0015")).first()
    if employee is None:
        raise SystemExit("EMP0015 not found.")

    user = db.scalars(select(AppUser).where(AppUser.employee_id == employee.id)).first()
    assumptions: list[str] = []
    profile = {
        "employee_code": employee.employee_code,
        "name": f"{employee.first_name} {employee.last_name or ''}".strip(),
        "date_of_joining": employee.date_of_joining.isoformat() if employee.date_of_joining else None,
        "status": employee.status,
        "employee_type": employee.employee_type,
        "reporting_manager_id": employee.reporting_manager_id,
        "app_user": None
        if user is None
        else {"id": user.id, "username": user.username, "email": user.email, "is_active": user.is_active},
    }
    print(
        "jyoti",
        profile["employee_code"],
        profile["name"],
        "doj",
        profile["date_of_joining"] or "null",
        "status",
        profile["status"],
        "type",
        profile["employee_type"],
        "manager",
        profile["reporting_manager_id"],
        "user",
        None if user is None else user.username,
        flush=True,
    )

    confirmed = _ensure_confirmation(db, employee, assumptions)
    assignment = _ensure_assignment(db, employee, policy)
    balances = _ensure_balances(db, employee, types, assumptions)
    return {
        "profile": profile,
        "confirmed": confirmed,
        "assignment": assignment,
        "balances": balances,
        "assumptions": assumptions,
    }


def _ensure_confirmation(db: Session, employee: Employee, assumptions: list[str]) -> dict[str, Any]:
    existing = db.scalars(
        select(EmploymentHistory).where(
            EmploymentHistory.employee_id == employee.id,
            EmploymentHistory.event_type == "Confirmed",
            EmploymentHistory.is_active == True,  # noqa: E712
        )
    ).first()
    if existing is not None:
        return {
            "action": "unchanged",
            "effective_date": existing.effective_date.isoformat(),
            "remarks": existing.remarks,
        }

    if employee.employee_type != "Permanent" or employee.status != "Active":
        assumptions.append(
            f"Skipped Confirmed event: employee_type={employee.employee_type!r} status={employee.status!r}"
        )
        return {"action": "skipped", "effective_date": None, "remarks": None}

    doj = employee.date_of_joining
    if doj is None:
        effective = EFFECTIVE_FROM
        remarks = "TTPL leave config: Permanent Active treated as confirmed (joining date missing)"
        assumptions.append(
            "DOJ is null; Confirmed effective_date set to 2026-01-01; AL full-year credit assumption applies."
        )
    else:
        effective = doj
        remarks = "TTPL leave config: Permanent Active treated as confirmed"
        assumptions.append(f"Confirmed effective_date set from date_of_joining {doj.isoformat()}.")

    row = EmploymentHistory(
        employee_id=employee.id,
        event_type="Confirmed",
        effective_date=effective,
        remarks=remarks,
        is_active=True,
    )
    db.add(row)
    db.flush()
    print(f"employment_history Confirmed {effective.isoformat()}", flush=True)
    return {"action": "inserted", "effective_date": effective.isoformat(), "remarks": remarks}


def _ensure_assignment(db: Session, employee: Employee, policy: LeavePolicy) -> dict[str, Any]:
    prior = db.scalars(
        select(LeavePolicyAssignment).where(
            LeavePolicyAssignment.employee_id == employee.id,
            LeavePolicyAssignment.is_active == True,  # noqa: E712
            or_(
                LeavePolicyAssignment.effective_to.is_(None),
                LeavePolicyAssignment.effective_to >= EFFECTIVE_FROM,
            ),
        )
    ).all()
    ended = 0
    for row in prior:
        if row.leave_policy_id == policy.id and row.effective_from == EFFECTIVE_FROM:
            continue
        if row.effective_from < EFFECTIVE_FROM:
            row.effective_to = DAY_BEFORE
            ended += 1
        else:
            # Cannot end-date before effective_from (CK); deactivate overlapping future rows.
            row.is_active = False
            ended += 1
    db.flush()

    current = db.scalars(
        select(LeavePolicyAssignment).where(
            LeavePolicyAssignment.employee_id == employee.id,
            LeavePolicyAssignment.leave_policy_id == policy.id,
            LeavePolicyAssignment.effective_from == EFFECTIVE_FROM,
        )
    ).first()
    if current is None:
        current = LeavePolicyAssignment(
            leave_policy_id=policy.id,
            employee_id=employee.id,
            effective_from=EFFECTIVE_FROM,
            effective_to=None,
            is_active=True,
        )
        db.add(current)
        action = "inserted"
        print("assignment inserted TTPL Leave Policy from 2026-01-01", flush=True)
    else:
        current.effective_to = None
        current.is_active = True
        action = "updated"
        print("assignment refreshed TTPL Leave Policy from 2026-01-01", flush=True)
    db.flush()
    return {
        "action": action,
        "ended_prior": ended,
        "effective_from": EFFECTIVE_FROM.isoformat(),
        "leave_policy_id": policy.id,
    }


def _balance_years() -> list[int]:
    years = [2026]
    if date.today().year >= 2026:
        years.append(2027)
    return years


def _ensure_balances(
    db: Session, employee: Employee, types: dict[str, LeaveType], assumptions: list[str]
) -> dict[str, dict[str, Any]]:
    if employee.date_of_joining is None:
        assumptions.append(
            "AL credit assumption: DOJ null + Permanent Confirmed ⇒ full-year AL accrued=15 for each balance year."
        )
    else:
        assumptions.append(
            "AL credit: full-year accrued=15 when creating a missing AL balance "
            f"(DOJ={employee.date_of_joining.isoformat()})."
        )

    result: dict[str, dict[str, Any]] = {}
    for year in _balance_years():
        result[str(year)] = {
            "AL": _ensure_al_balance(db, employee, types["AL"], year),
            "CL": _ensure_cl_balance(db, employee, types["CL"], year),
            "CO": _ensure_co_balance(db, employee, types["CO"], year),
        }
    return result


def _get_balance(db: Session, employee_id: int, leave_type_id: int, year: int) -> LeaveBalance | None:
    return db.scalars(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.leave_year == year,
        )
    ).first()


def _has_source_txn(
    db: Session, employee_id: int, leave_type_id: int, year: int, kind: str
) -> bool:
    return (
        db.scalar(
            select(LeaveBalanceTransaction.id).where(
                LeaveBalanceTransaction.employee_id == employee_id,
                LeaveBalanceTransaction.leave_type_id == leave_type_id,
                LeaveBalanceTransaction.leave_year == year,
                LeaveBalanceTransaction.source_type == SOURCE,
                LeaveBalanceTransaction.kind == kind,
                LeaveBalanceTransaction.is_active == True,  # noqa: E712
            )
        )
        is not None
    )


def _add_txn(
    db: Session,
    *,
    employee_id: int,
    leave_type_id: int,
    year: int,
    balance_id: int,
    kind: str,
    days: Decimal,
    remarks: str,
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
            source_id=None,
            is_active=True,
        )
    )


def _recompute_closing(balance: LeaveBalance) -> None:
    balance.closing = (
        Decimal(balance.opening)
        + Decimal(balance.accrued)
        - Decimal(balance.availed)
        - Decimal(balance.encashed)
    )


def _snapshot_balance(balance: LeaveBalance) -> dict[str, Any]:
    return {
        "id": balance.id,
        "opening": str(balance.opening),
        "accrued": str(balance.accrued),
        "availed": str(balance.availed),
        "encashed": str(balance.encashed),
        "closing": str(balance.closing),
        "is_active": bool(balance.is_active),
    }


def _ensure_al_balance(
    db: Session, employee: Employee, leave_type: LeaveType, year: int
) -> dict[str, Any]:
    balance = _get_balance(db, employee.id, leave_type.id, year)
    if balance is not None:
        return {"action": "unchanged", **_snapshot_balance(balance)}

    balance = LeaveBalance(
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        leave_year=year,
        opening=ZERO,
        accrued=AL_ACCRUED,
        availed=ZERO,
        encashed=ZERO,
        closing=AL_ACCRUED,
        is_active=True,
    )
    db.add(balance)
    db.flush()
    if not _has_source_txn(db, employee.id, leave_type.id, year, "Credit"):
        _add_txn(
            db,
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            year=year,
            balance_id=balance.id,
            kind="Credit",
            days=AL_ACCRUED,
            remarks=f"TTPL: AL full-year credit for calendar {year}",
        )
    db.flush()
    print(f"AL balance created year={year} accrued={AL_ACCRUED}", flush=True)
    return {"action": "created", **_snapshot_balance(balance)}


def _ensure_cl_balance(
    db: Session, employee: Employee, leave_type: LeaveType, year: int
) -> dict[str, Any]:
    balance = _get_balance(db, employee.id, leave_type.id, year)
    if balance is None:
        balance = LeaveBalance(
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            leave_year=year,
            opening=ZERO,
            accrued=CL_ACCRUED,
            availed=ZERO,
            encashed=ZERO,
            closing=CL_ACCRUED,
            is_active=True,
        )
        db.add(balance)
        db.flush()
        if not _has_source_txn(db, employee.id, leave_type.id, year, "Credit"):
            _add_txn(
                db,
                employee_id=employee.id,
                leave_type_id=leave_type.id,
                year=year,
                balance_id=balance.id,
                kind="Credit",
                days=CL_ACCRUED,
                remarks=f"TTPL: CL annual credit for calendar {year}",
            )
        db.flush()
        print(f"CL balance created year={year} accrued={CL_ACCRUED}", flush=True)
        return {"action": "created", **_snapshot_balance(balance)}

    accrued = Decimal(balance.accrued)
    if accrued == CL_ACCRUED:
        return {"action": "unchanged", **_snapshot_balance(balance)}

    delta = CL_ACCRUED - accrued
    if _has_source_txn(db, employee.id, leave_type.id, year, "Adjustment"):
        return {"action": "already_adjusted", **_snapshot_balance(balance)}

    balance.accrued = CL_ACCRUED
    _recompute_closing(balance)
    _add_txn(
        db,
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        year=year,
        balance_id=balance.id,
        kind="Adjustment",
        days=delta,
        remarks=f"TTPL: CL accrued adjusted from {accrued} to {CL_ACCRUED} for calendar {year}",
    )
    db.flush()
    print(f"CL balance adjusted year={year} accrued {accrued} -> {CL_ACCRUED}", flush=True)
    return {"action": "adjusted", "delta": str(delta), **_snapshot_balance(balance)}


def _ensure_co_balance(
    db: Session, employee: Employee, leave_type: LeaveType, year: int
) -> dict[str, Any]:
    balance = _get_balance(db, employee.id, leave_type.id, year)
    if balance is not None:
        return {"action": "unchanged", **_snapshot_balance(balance)}

    balance = LeaveBalance(
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        leave_year=year,
        opening=ZERO,
        accrued=ZERO,
        availed=ZERO,
        encashed=ZERO,
        closing=ZERO,
        is_active=True,
    )
    db.add(balance)
    db.flush()
    print(f"CO balance created year={year} zeros (credits via Comp-Off ledger)", flush=True)
    return {"action": "created", **_snapshot_balance(balance)}


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _backup(db: Session) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = BACKEND / "scripts" / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"ttpl_leave_config_{stamp}.json"

    types = db.execute(
        text(
            """
            SELECT t.id, t.code, t.name, t.annual_quota, t.carry_forward_max, t.is_paid, t.is_encashable,
                   t.is_active, s.description, s.accrual_applicable, s.half_day_allowed,
                   s.attachment_required, s.max_consecutive_days
            FROM hr.leave_type t
            LEFT JOIN hr.leave_type_setting s ON s.leave_type_id = t.id
            ORDER BY t.code
            """
        )
    ).mappings().all()
    policies = db.execute(
        text(
            """
            SELECT id, name, employee_type, year_basis, assignment_mode, applies_during_probation,
                   negative_balance_allowed, effective_from, effective_to, is_active
            FROM hr.leave_policy
            ORDER BY id
            """
        )
    ).mappings().all()
    lines = db.execute(
        text(
            """
            SELECT l.id, l.leave_policy_id, p.name AS policy_name, t.code AS leave_type_code,
                   l.annual_entitlement, l.accrual_frequency, l.carry_forward, l.max_accumulation,
                   l.encashment_eligible, l.calculation_method, l.benefit_class, l.compensatory_basis,
                   l.compensatory_expiry_months, l.exclude_boundary_holidays, l.max_backdate_days,
                   l.backdate_requires_authorization, l.is_active
            FROM hr.leave_policy_line l
            JOIN hr.leave_policy p ON p.id = l.leave_policy_id
            JOIN hr.leave_type t ON t.id = l.leave_type_id
            ORDER BY l.leave_policy_id, t.code
            """
        )
    ).mappings().all()
    holidays = db.execute(
        text(
            """
            SELECT id, holiday_date, name, holiday_type, branch_id, state_id, description, is_active
            FROM hr.holiday
            WHERE holiday_date >= '2026-01-01' AND is_active = 1
            ORDER BY holiday_date, id
            """
        )
    ).mappings().all()

    payload = {
        "database": db.execute(text("SELECT DB_NAME()")).scalar(),
        "taken_at": datetime.now().isoformat(timespec="seconds"),
        "leave_types": [dict(row) for row in types],
        "policies": [dict(row) for row in policies],
        "policy_lines": [dict(row) for row in lines],
        "active_holidays_2026_plus": [dict(row) for row in holidays],
    }
    path.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")
    return path


def _print_report(db: Session, report: dict[str, Any]) -> None:
    print("\n=== TTPL leave config report ===", flush=True)
    print("--- leave types ---", flush=True)
    rows = db.execute(
        text(
            """
            SELECT t.code, t.name, t.annual_quota, t.carry_forward_max, t.is_paid, t.is_encashable,
                   t.is_active, s.accrual_applicable, s.half_day_allowed, s.description
            FROM hr.leave_type t
            LEFT JOIN hr.leave_type_setting s ON s.leave_type_id = t.id
            WHERE t.code IN (N'AL', N'CL', N'CO', N'EL', N'SL', N'ML', N'PL', N'WR', N'LWP')
            ORDER BY t.code
            """
        )
    ).all()
    for row in rows:
        print(" ", row, flush=True)

    print("--- TTPL policy lines ---", flush=True)
    lines = db.execute(
        text(
            """
            SELECT t.code, l.annual_entitlement, l.accrual_frequency, l.carry_forward, l.max_accumulation,
                   l.calculation_method, l.benefit_class, l.compensatory_basis, l.compensatory_expiry_months,
                   l.exclude_boundary_holidays, l.max_backdate_days, l.backdate_requires_authorization,
                   l.is_active
            FROM hr.leave_policy_line l
            JOIN hr.leave_policy p ON p.id = l.leave_policy_id
            JOIN hr.leave_type t ON t.id = l.leave_type_id
            WHERE p.name = :name
            ORDER BY t.code
            """
        ),
        {"name": POLICY_NAME},
    ).all()
    for row in lines:
        print(" ", row, flush=True)

    print("--- active holiday counts (2026+) ---", flush=True)
    print(" ", report["holiday_counts"], flush=True)

    jyoti = report["jyoti"]
    print("--- EMP0015 Jyoti ---", flush=True)
    print(" ", jyoti["profile"], flush=True)
    print("  confirmation", jyoti["confirmed"], flush=True)
    print("  assignment", jyoti["assignment"], flush=True)
    print("  balances", jyoti["balances"], flush=True)
    print("--- assumptions ---", flush=True)
    for item in jyoti["assumptions"]:
        print(" ", item, flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
