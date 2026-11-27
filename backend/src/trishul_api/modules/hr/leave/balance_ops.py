"""Leave balance board, audited adjustments, and confirmed entitlement generation.

Assignment does not create balances. A credit is posted only after HR confirms generation.
An existing balance is increased by the new credit. Opening, used and encashed amounts stay as they are.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError, NotFound
from trishul_api.db.models import (
    Attendance,
    Branch,
    Department,
    Designation,
    Employee,
    LeaveAttendanceClass,
    LeaveBalance,
    LeaveBalanceTransaction,
    LeaveEntitlementRun,
    LeavePolicy,
    LeavePolicyAssignment,
    LeavePolicyLine,
    LeaveRequest,
    LeaveType,
)
from trishul_api.modules.hr.leave.balance_schemas import (
    BalanceAdjustment,
    BalanceBoard,
    BalanceBucket,
    BalanceDetail,
    BalanceEmployee,
    BalanceLeaveHistory,
    BalanceSummary,
    BalanceTransactionItem,
    BalanceTypeDetail,
    EntitlementGenerateResult,
    EntitlementPreviewBoard,
    EntitlementPreviewEmployee,
    EntitlementPreviewLine,
    EntitlementPreviewRequest,
)
from trishul_api.modules.hr.leave.calculation import earned_leave_days, joining_threshold
from trishul_api.modules.hr.leave.mine_repository import _policy_fits, _service_months

_ZERO = Decimal("0.0")
_CODES = ("EL", "SL", "CL", "CO")


def balance_board(
    db: Session,
    actor: CurrentUser,
    *,
    year: int,
    policy_id: int | None,
    department_id: int | None,
    branch_id: int | None,
    search: str | None,
    page: int,
    page_size: int,
    sort: str,
) -> BalanceBoard:
    policy = _policy(db, policy_id) if policy_id is not None else None
    employees = _employees(db, actor, department_id, branch_id, search)
    summary, warning = _summary(db, employees, policy, year)
    ordered = _ordered(employees, sort)
    start = (page - 1) * page_size
    page_rows = ordered[start : start + page_size]
    balances = _balances(db, [row.id for row in page_rows], year)
    return BalanceBoard(
        year=year,
        policy_id=None if policy is None else policy.id,
        policy_name=None if policy is None else policy.name,
        warning=warning,
        summary=summary,
        items=[_employee_item(row, balances.get(row.id, {})) for row in page_rows],
        total=len(ordered),
        page=page,
        page_size=page_size,
    )


def balance_detail(db: Session, actor: CurrentUser, employee_id: int, year: int) -> BalanceDetail:
    employee = _one_employee(db, actor, employee_id)
    balances = _balances(db, [employee.id], year).get(employee.id, {})
    transactions = db.execute(
        select(LeaveBalanceTransaction, LeaveType.code)
        .join(LeaveType, LeaveType.id == LeaveBalanceTransaction.leave_type_id)
        .where(
            LeaveBalanceTransaction.employee_id == employee.id,
            LeaveBalanceTransaction.leave_year == year,
            LeaveBalanceTransaction.is_active == True,  # noqa: E712
        )
        .order_by(LeaveBalanceTransaction.id)
    ).all()
    types = {row.code: row for row in db.scalars(select(LeaveType).where(LeaveType.code.in_(_CODES))).all()}
    details: list[BalanceTypeDetail] = []
    for code in _CODES:
        balance = balances.get(code)
        leave_type = types.get(code)
        type_id = None if leave_type is None else leave_type.id
        kind_days = _kind_totals(transactions, code)
        details.append(
            BalanceTypeDetail(
                code=code,
                name=code if leave_type is None else leave_type.name,
                opening=_ZERO if balance is None else balance.opening,
                annual_entitlement=None,
                credited=_ZERO if balance is None else balance.accrued,
                consumed=_ZERO if balance is None else balance.availed,
                adjustments=kind_days.get("Adjustment", _ZERO),
                expired=kind_days.get("Expiry", _ZERO),
                closing=_ZERO if balance is None else balance.closing,
                leave_type_id=type_id,
            )
        )
    return BalanceDetail(
        employee_id=employee.id,
        employee_code=employee.employee_code,
        employee_name=_name(employee),
        year=year,
        types=details,
        leave_history=_leave_history(db, employee.id),
        transactions=[
            BalanceTransactionItem(
                id=row.id,
                code=code,
                on=date.today() if row.created_at is None else row.created_at.date(),
                kind=row.kind,
                days=row.days,
                reference=None if row.source_type is None else f"{row.source_type} {row.source_id or ''}".strip(),
                remarks=row.remarks,
            )
            for row, code in transactions
        ],
    )


def adjust_balance(db: Session, actor: CurrentUser, employee_id: int, data: BalanceAdjustment) -> BalanceDetail:
    employee = _one_employee(db, actor, employee_id)
    leave_type = db.get(LeaveType, data.leave_type_id)
    if leave_type is None or not leave_type.is_active:
        raise NotFound("Leave type")
    if leave_type.code == "CO":
        from trishul_api.modules.hr.leave.comp_off_ops import adjust

        adjust(db, actor, employee, leave_type, data.days, data.reason)
        db.commit()
        return balance_detail(db, actor, employee.id, data.year)
    balance = _balance_row(db, employee.id, leave_type.id, data.year, actor.id)
    db.add(
        LeaveBalanceTransaction(
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            leave_year=data.year,
            leave_balance_id=balance.id,
            kind="Adjustment",
            days=data.days,
            remarks=data.reason,
            source_type="hr.leave_balance",
            source_id=balance.id,
            created_by_user_id=actor.id,
        )
    )
    db.flush()
    _recompute_closing(db, balance)
    db.commit()
    return balance_detail(db, actor, employee.id, data.year)


def preview_generation(db: Session, actor: CurrentUser, data: EntitlementPreviewRequest) -> EntitlementPreviewBoard:
    policy = _active_policy(db, data.policy_id)
    employees = _policy_employees(db, actor, policy, data.year)
    warning = _classification_warning(db, policy)
    return EntitlementPreviewBoard(
        policy_id=policy.id,
        policy_name=policy.name,
        year=data.year,
        warning=warning,
        employees=[_preview_employee(db, policy, employee, data.year, warning) for employee in employees],
    )


def generate_entitlements(
    db: Session, actor: CurrentUser, data: EntitlementPreviewRequest
) -> EntitlementGenerateResult:
    policy = _active_policy(db, data.policy_id)
    warning = _classification_warning(db, policy)
    credited_ids: set[int] = set()
    skipped = blocked = 0
    for employee in _policy_employees(db, actor, policy, data.year):
        for line in _lines(db, policy.id):
            if _run_exists(db, employee.id, line.id, data.year):
                skipped += 1
                continue
            preview = _line_preview(db, policy, line, employee, data.year, warning)
            if preview.blocked:
                blocked += 1
                continue
            _store_run(db, actor, employee, line, data.year, preview)
            if preview.credited > 0:
                _credit_balance(db, actor, employee.id, line, data.year, preview.credited)
                credited_ids.add(employee.id)
    db.commit()
    return EntitlementGenerateResult(
        credited_employees=len(credited_ids), skipped_duplicates=skipped, blocked=blocked
    )


def _summary(
    db: Session, employees: list[Employee], policy: LeavePolicy | None, year: int
) -> tuple[BalanceSummary, str | None]:
    assigned = employees if policy is None else _policy_employees_from(db, employees, policy, year)
    generated = 0
    if assigned:
        generated = int(
            db.scalar(
                select(func.count(func.distinct(LeaveEntitlementRun.employee_id))).where(
                    LeaveEntitlementRun.employee_id.in_([row.id for row in assigned]),
                    LeaveEntitlementRun.leave_year == year,
                    LeaveEntitlementRun.is_active == True,  # noqa: E712
                )
            )
            or 0
        )
    warning = None if policy is None else _classification_warning(db, policy)
    review = 0
    if policy is not None:
        review = sum(1 for row in assigned if _preview_employee(db, policy, row, year, warning).requires_review)
    return (
        BalanceSummary(
            total_employees=len(employees),
            with_assigned_policy=len(assigned) if policy is not None else _any_assigned(db, employees, year),
            entitlement_generated=generated,
            requires_review=review,
        ),
        warning,
    )


def _employees(
    db: Session, actor: CurrentUser, department_id: int | None, branch_id: int | None, search: str | None
) -> list[Employee]:
    statement = (
        select(Employee, Department.name, Designation.name)
        .outerjoin(Department, Department.id == Employee.department_id)
        .outerjoin(Designation, Designation.id == Employee.designation_id)
        .where(Employee.is_active == True)  # noqa: E712
    )
    if actor.branch_ids is not None:
        statement = statement.where(Employee.branch_id.in_(actor.branch_ids or [0]))
    if department_id is not None:
        statement = statement.where(Employee.department_id == department_id)
    if branch_id is not None:
        statement = statement.where(Employee.branch_id == branch_id)
    if search and search.strip():
        term = search.strip()
        statement = statement.where(
            or_(
                Employee.employee_code.contains(term, autoescape=True),
                Employee.first_name.contains(term, autoescape=True),
                Employee.last_name.contains(term, autoescape=True),
            )
        )
    rows = db.execute(statement).all()
    found: list[Employee] = []
    for employee, department, designation in rows:
        employee.department_name = department  # type: ignore[attr-defined]
        employee.designation_name = designation  # type: ignore[attr-defined]
        found.append(employee)
    return found


def _ordered(employees: list[Employee], sort: str) -> list[Employee]:
    descending = sort.startswith("-")
    key = sort[1:] if descending else sort
    if key == "employeeName":
        ordered = sorted(employees, key=lambda row: _name(row).lower())
    elif key == "department":
        ordered = sorted(employees, key=lambda row: (getattr(row, "department_name", None) or "").lower())
    else:
        ordered = sorted(employees, key=lambda row: row.employee_code)
    return list(reversed(ordered)) if descending else ordered


def _policy_employees(db: Session, actor: CurrentUser, policy: LeavePolicy, year: int) -> list[Employee]:
    return _policy_employees_from(db, _employees(db, actor, None, None, None), policy, year)


def _policy_employees_from(db: Session, employees: list[Employee], policy: LeavePolicy, year: int) -> list[Employee]:
    start, end = _policy_window(policy, year)
    assigned = set(
        db.scalars(
            select(LeavePolicyAssignment.employee_id).where(
                LeavePolicyAssignment.leave_policy_id == policy.id,
                LeavePolicyAssignment.is_active == True,  # noqa: E712
                LeavePolicyAssignment.effective_from <= end,
                or_(LeavePolicyAssignment.effective_to.is_(None), LeavePolicyAssignment.effective_to >= start),
            )
        ).all()
    )
    states = {
        row.id: row.state_id
        for row in db.scalars(select(Branch).where(Branch.id.in_({item.branch_id for item in employees} or {0}))).all()
    }
    if policy.assignment_mode == "EXPLICIT":
        return [row for row in employees if row.id in assigned]
    return [row for row in employees if _policy_fits(policy, row, states.get(row.branch_id))]


def _any_assigned(db: Session, employees: list[Employee], year: int) -> int:
    if not employees:
        return 0
    start, end = date(year, 1, 1), date(year, 12, 31)
    return int(
        db.scalar(
            select(func.count(func.distinct(LeavePolicyAssignment.employee_id))).where(
                LeavePolicyAssignment.employee_id.in_([row.id for row in employees]),
                LeavePolicyAssignment.is_active == True,  # noqa: E712
                LeavePolicyAssignment.effective_from <= end,
                or_(LeavePolicyAssignment.effective_to.is_(None), LeavePolicyAssignment.effective_to >= start),
            )
        )
        or 0
    )


def _balances(db: Session, employee_ids: list[int], year: int) -> dict[int, dict[str, LeaveBalance]]:
    if not employee_ids:
        return {}
    rows = db.execute(
        select(LeaveBalance, LeaveType.code)
        .join(LeaveType, LeaveType.id == LeaveBalance.leave_type_id)
        .where(
            LeaveBalance.employee_id.in_(employee_ids),
            LeaveBalance.leave_year == year,
            LeaveBalance.is_active == True,  # noqa: E712
            LeaveType.code.in_(_CODES),
        )
    ).all()
    found: dict[int, dict[str, LeaveBalance]] = {}
    for balance, code in rows:
        found.setdefault(balance.employee_id, {})[code] = balance
    return found


def _employee_item(employee: Employee, balances: dict[str, LeaveBalance]) -> BalanceEmployee:
    return BalanceEmployee(
        employee_id=employee.id,
        employee_code=employee.employee_code,
        employee_name=_name(employee),
        department=getattr(employee, "department_name", None),
        designation=getattr(employee, "designation_name", None),
        el=_bucket(balances.get("EL")),
        sl=_bucket(balances.get("SL")),
        cl=_bucket(balances.get("CL")),
        comp_off_balance=_ZERO if balances.get("CO") is None else balances["CO"].closing,
    )


def _bucket(balance: LeaveBalance | None) -> BalanceBucket:
    if balance is None:
        return BalanceBucket()
    return BalanceBucket(
        opening=balance.opening, credited=balance.accrued, used=balance.availed, balance=balance.closing
    )


def _preview_employee(
    db: Session, policy: LeavePolicy, employee: Employee, year: int, warning: str | None
) -> EntitlementPreviewEmployee:
    lines = [_line_preview(db, policy, line, employee, year, warning) for line in _lines(db, policy.id)]
    return EntitlementPreviewEmployee(
        employee_id=employee.id,
        employee_code=employee.employee_code,
        employee_name=_name(employee),
        lines=lines,
        requires_review=any(line.blocked or line.review for line in lines),
    )


def _line_preview(
    db: Session, policy: LeavePolicy, line: LeavePolicyLine, employee: Employee, year: int, warning: str | None
) -> EntitlementPreviewLine:
    code = _type_code(db, line.leave_type_id)
    if line.compensatory_basis == "STATUTORY_WEEKLY_REST":
        return EntitlementPreviewLine(
            code=code, credited=_ZERO, message="Statutory weekly rest is granted separately from this annual run."
        )
    if line.compensatory_basis == "COMPANY_COMP_OFF":
        return EntitlementPreviewLine(
            code=code,
            credited=_ZERO,
            message="Company Comp-Off is credited from approved grants, not from this annual run.",
        )
    if line.calculation_method == "FORMULA":
        if warning:
            return EntitlementPreviewLine(code=code, credited=_ZERO, blocked=True, review=True, message=warning)
        return _formula_preview(db, policy, line, employee, year)
    if line.calculation_method == "ELIGIBILITY":
        start, _end = _policy_window(policy, year)
        months = _service_months(employee.date_of_joining, start)
        needed = line.minimum_service_months or 0
        if months < needed:
            return EntitlementPreviewLine(
                code=code,
                credited=_ZERO,
                review=True,
                message=f"Continuous service is {months} months. This leave needs {needed}.",
            )
        return EntitlementPreviewLine(code=code, credited=line.annual_entitlement)
    return EntitlementPreviewLine(code=code, credited=line.annual_entitlement)


def _formula_preview(
    db: Session, policy: LeavePolicy, line: LeavePolicyLine, employee: Employee, year: int
) -> EntitlementPreviewLine:
    attendance_year = year - 1
    start, end = _attendance_window(policy, attendance_year)
    counts = db.execute(
        select(Attendance.status, func.count())
        .where(
            Attendance.employee_id == employee.id,
            Attendance.is_active == True,  # noqa: E712
            Attendance.attendance_date >= start,
            Attendance.attendance_date <= end,
        )
        .group_by(Attendance.status)
    ).all()
    mapped = {row.attendance_status: row for row in db.scalars(select(LeaveAttendanceClass)).all()}
    missing = [status for status, _count in counts if status not in mapped or mapped[status].day_weight is None]
    if missing:
        names = ", ".join(sorted(set(missing)))
        return EntitlementPreviewLine(
            code=_type_code(db, line.leave_type_id),
            credited=_ZERO,
            blocked=True,
            review=True,
            message=f"Attendance classification is incomplete for {names}.",
        )
    worked = eligibility = deemed = _ZERO
    for status, count in counts:
        weight = mapped[status].day_weight or _ZERO
        total = Decimal(count) * weight
        if mapped[status].counts_for_eligibility:
            eligibility += total
        if mapped[status].counts_as_days_worked:
            worked += total
        if mapped[status].is_deemed_work:
            deemed += total
    minimum = line.minimum_qualifying_days or 0
    rule = line.joining_year_rule
    threshold = minimum
    if rule == "TWO_THIRDS_REMAINDER":
        threshold = joining_threshold(employee.date_of_joining, attendance_year, minimum)
    credited = earned_leave_days(
        eligibility_days=eligibility,
        days_worked=worked,
        credit_days=line.credit_days or _ZERO,
        per_days=line.qualifying_days_per_credit or 0,
        minimum_qualifying_days=minimum,
        joining=employee.date_of_joining,
        attendance_year=attendance_year,
        joining_rule=rule,
    )
    return EntitlementPreviewLine(
        code=_type_code(db, line.leave_type_id),
        credited=credited,
        eligibility_days=eligibility,
        days_worked=worked,
        deemed_days=deemed,
        threshold=threshold,
        review=eligibility < threshold,
        message=None if eligibility >= threshold else f"Qualifying days {eligibility} are below {threshold}.",
    )


def _store_run(
    db: Session,
    actor: CurrentUser,
    employee: Employee,
    line: LeavePolicyLine,
    year: int,
    preview: EntitlementPreviewLine,
) -> None:
    db.add(
        LeaveEntitlementRun(
            employee_id=employee.id,
            leave_policy_line_id=line.id,
            leave_year=year,
            eligibility_days=preview.eligibility_days or _ZERO,
            days_worked=preview.days_worked or _ZERO,
            deemed_days=preview.deemed_days or _ZERO,
            credited_days=preview.credited,
            created_by_user_id=actor.id,
        )
    )
    db.flush()


def _credit_balance(
    db: Session, actor: CurrentUser, employee_id: int, line: LeavePolicyLine, year: int, days: Decimal
) -> None:
    balance = _balance_row(db, employee_id, line.leave_type_id, year, actor.id)
    balance.accrued = (balance.accrued or _ZERO) + days
    db.add(
        LeaveBalanceTransaction(
            employee_id=employee_id,
            leave_type_id=line.leave_type_id,
            leave_year=year,
            leave_balance_id=balance.id,
            kind="Credit",
            days=days,
            remarks="Entitlement generation",
            source_type="hr.leave_entitlement_run",
            source_id=line.id,
            created_by_user_id=actor.id,
        )
    )
    db.flush()
    _recompute_closing(db, balance)


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


def _recompute_closing(db: Session, balance: LeaveBalance) -> None:
    extra = db.execute(
        select(LeaveBalanceTransaction.kind, func.coalesce(func.sum(LeaveBalanceTransaction.days), 0)).where(
            LeaveBalanceTransaction.leave_balance_id == balance.id,
            LeaveBalanceTransaction.is_active == True,  # noqa: E712
            LeaveBalanceTransaction.kind.in_(("Adjustment", "Expiry")),
        ).group_by(LeaveBalanceTransaction.kind)
    ).all()
    amounts = {kind: Decimal(total) for kind, total in extra}
    balance.closing = (
        (balance.opening or _ZERO)
        + (balance.accrued or _ZERO)
        - (balance.availed or _ZERO)
        - (balance.encashed or _ZERO)
        + amounts.get("Adjustment", _ZERO)
        - amounts.get("Expiry", _ZERO)
    )


def _run_exists(db: Session, employee_id: int, line_id: int, year: int) -> bool:
    return (
        db.scalar(
            select(LeaveEntitlementRun.id).where(
                LeaveEntitlementRun.employee_id == employee_id,
                LeaveEntitlementRun.leave_policy_line_id == line_id,
                LeaveEntitlementRun.leave_year == year,
                LeaveEntitlementRun.is_active == True,  # noqa: E712
            )
        )
        is not None
    )


def _lines(db: Session, policy_id: int) -> list[LeavePolicyLine]:
    return list(
        db.scalars(
            select(LeavePolicyLine).where(
                LeavePolicyLine.leave_policy_id == policy_id,
                LeavePolicyLine.is_active == True,  # noqa: E712
            )
        ).all()
    )


def _classification_warning(db: Session, policy: LeavePolicy) -> str | None:
    formula = any(line.calculation_method == "FORMULA" for line in _lines(db, policy.id))
    if not formula:
        return None
    ready = db.scalar(
        select(func.count()).select_from(LeaveAttendanceClass).where(LeaveAttendanceClass.day_weight.is_not(None))
    )
    if int(ready or 0) == 0:
        return "Attendance classification is not configured, so Earned Leave cannot be calculated."
    return None


def _leave_history(db: Session, employee_id: int) -> list[BalanceLeaveHistory]:
    rows = db.execute(
        select(LeaveRequest, LeaveType.code)
        .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
        .where(LeaveRequest.employee_id == employee_id, LeaveRequest.is_active == True)  # noqa: E712
        .order_by(LeaveRequest.from_date.desc())
        .limit(20)
    ).all()
    return [
        BalanceLeaveHistory(
            id=request.id, code=code, from_date=request.from_date, to_date=request.to_date,
            days=request.days, status=request.status,
        )
        for request, code in rows
    ]


def _kind_totals(transactions: list[tuple[LeaveBalanceTransaction, str]], code: str) -> dict[str, Decimal]:
    found: dict[str, Decimal] = {}
    for row, row_code in transactions:
        if row_code != code:
            continue
        found[row.kind] = found.get(row.kind, _ZERO) + row.days
    return found


def _type_code(db: Session, leave_type_id: int) -> str:
    code = db.scalar(select(LeaveType.code).where(LeaveType.id == leave_type_id))
    return code or ""


def _policy(db: Session, policy_id: int) -> LeavePolicy:
    policy = db.get(LeavePolicy, policy_id)
    if policy is None:
        raise NotFound("Leave policy")
    return policy


def _active_policy(db: Session, policy_id: int) -> LeavePolicy:
    policy = _policy(db, policy_id)
    if not policy.is_active:
        raise ApiError("An inactive policy cannot generate entitlements.")
    return policy


def _one_employee(db: Session, actor: CurrentUser, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None or (actor.branch_ids is not None and employee.branch_id not in actor.branch_ids):
        raise NotFound("Employee")
    return employee


def _policy_window(policy: LeavePolicy, year: int) -> tuple[date, date]:
    if policy.year_basis == "CALENDAR":
        return date(year, 1, 1), date(year, 12, 31)
    return date(year, 4, 1), date(year + 1, 3, 31)


def _attendance_window(policy: LeavePolicy, year: int) -> tuple[date, date]:
    return _policy_window(policy, year)


def _name(employee: Employee) -> str:
    return f"{employee.first_name} {employee.last_name}".strip()
