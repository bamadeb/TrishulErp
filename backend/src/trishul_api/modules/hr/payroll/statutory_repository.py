"""Reads statutory rules and the employees those rules can apply to. It does not calculate payroll."""

import itertools
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.orm import Session, aliased

from trishul_api.common.paging import order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Branch,
    Company,
    Department,
    Employee,
    EmployeeProfile,
    PayrollRun,
    Payslip,
    PayslipLine,
    SalaryComponent,
    SalaryStructure,
    State,
    StatutoryConfig,
)
from trishul_api.modules.hr.payroll.statutory_schemas import (
    DepartmentChoice,
    Scheme,
    StateChoice,
    StatutoryContribution,
    StatutoryContributionQuery,
    StatutoryRule,
)

# Payslip component codes already saved on the salary component master. Not rates.
SCHEME_CODES: dict[Scheme, tuple[str, ...]] = {
    "PF": ("PF", "VPF"),
    "ESI": ("ESI",),
    "PT": ("PT",),
    "TDS": ("IT",),
}


@dataclass(frozen=True)
class PtEmployee:
    employee_id: int
    employee_code: str
    full_name: str
    department: str | None
    state_id: int | None
    state_name: str | None
    wages: Decimal | None
    stored_amount: Decimal | None


SCHEME_NAMES: dict[Scheme, str] = {
    "PF": "PF",
    "ESI": "ESI",
    "PT": "Professional Tax",
    "TDS": "TDS",
}


def month_start(value: date) -> date:
    return value.replace(day=1)


def month_end(value: date) -> date:
    start = month_start(value)
    if start.month == 12:
        return date(start.year, 12, 31)
    return date(start.year, start.month + 1, 1) - timedelta(days=1)


class StatutoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def company_id(self) -> int | None:
        return self._session.scalar(
            select(Company.id).where(Company.is_active == True).order_by(Company.id).limit(1)  # noqa: E712
        )

    def states(self) -> list[StateChoice]:
        rows = self._session.execute(
            select(State.id, State.name).where(State.is_active == True).order_by(State.name)  # noqa: E712
        )
        return [StateChoice(id=row.id, name=row.name) for row in rows]

    def departments(self) -> list[DepartmentChoice]:
        rows = self._session.execute(
            select(Department.id, Department.name)
            .where(Department.is_active == True)  # noqa: E712
            .order_by(Department.name)
        )
        return [DepartmentChoice(id=row.id, name=row.name) for row in rows]

    def rules(self, scheme: Scheme | None = None) -> list[StatutoryConfig]:
        statement = select(StatutoryConfig).order_by(
            StatutoryConfig.effective_from.desc(), StatutoryConfig.id.desc()
        )
        if scheme is not None:
            statement = statement.where(StatutoryConfig.config_type == scheme)
        return list(self._session.scalars(statement))

    def rule(self, rule_id: int) -> StatutoryConfig | None:
        return self._session.get(StatutoryConfig, rule_id)

    def state_name(self, state_id: int | None) -> str | None:
        if state_id is None:
            return None
        return self._session.scalar(select(State.name).where(State.id == state_id))

    def username(self, user_id: int | None) -> str | None:
        if user_id is None:
            return None
        return self._session.scalar(select(AppUser.username).where(AppUser.id == user_id))

    def same_start(self, scheme: Scheme, state_id: int | None, effective_from: date, ignore_id: int | None) -> bool:
        statement = select(StatutoryConfig.id).where(
            StatutoryConfig.config_type == scheme,
            StatutoryConfig.effective_from == effective_from,
        )
        statement = statement.where(
            StatutoryConfig.state_id.is_(None) if state_id is None else StatutoryConfig.state_id == state_id
        )
        if ignore_id is not None:
            statement = statement.where(StatutoryConfig.id != ignore_id)
        return self._session.scalar(statement.limit(1)) is not None

    def eligible_count(self, month: date) -> int:
        return int(
            self._session.scalar(
                select(func.count(func.distinct(Employee.id))).where(*_eligible(month_start(month), month_end(month)))
            )
            or 0
        )

    def employee_contribution(self, month: date, scheme: Scheme | None) -> Any:
        codes = _codes(scheme)
        if not codes:
            return None
        return self._session.scalar(
            select(func.sum(PayslipLine.amount))
            .join(Payslip, Payslip.id == PayslipLine.payslip_id)
            .join(PayrollRun, PayrollRun.id == Payslip.payroll_run_id)
            .join(SalaryComponent, SalaryComponent.id == PayslipLine.salary_component_id)
            .where(
                PayrollRun.period_month == month_start(month),
                SalaryComponent.code.in_(codes),
                PayslipLine.is_active == True,  # noqa: E712
            )
        )

    def contributions(self, query: StatutoryContributionQuery) -> Page[StatutoryContribution]:
        start = month_start(query.month)
        amount = _line_amount(query.scheme, start)
        statement = (
            select(
                Employee.id.label("employee_id"),
                Employee.employee_code.label("employee_code"),
                _full_name(),
                Department.name.label("department"),
                Branch.name.label("location"),
                literal(None).label("applicable_wages"),
                amount.label("employee_contribution"),
                literal(None).label("employer_contribution"),
                literal(None).label("total_contribution"),
                literal("Not calculated").label("calculation_status"),
            )
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(Branch, Branch.id == Employee.branch_id)
            .where(*_eligible(start, month_end(query.month)))
        )
        if query.department_id is not None:
            statement = statement.where(Employee.department_id == query.department_id)
        if query.search:
            term = f"%{query.search.strip()}%"
            statement = statement.where(
                or_(
                    Employee.employee_code.ilike(term),
                    _full_name().ilike(term),
                    Department.name.ilike(term),
                    Branch.name.ilike(term),
                )
            )
        statement = order_by_sort(
            statement,
            query.sort,
            {"employeeCode": Employee.employee_code, "fullName": _full_name(), "department": Department.name},
            default="employeeCode",
            tiebreaker=Employee.id.asc(),
        )
        page = paginate(self._session, statement, query, StatutoryContribution)
        return page.model_copy(
            update={
                "items": [
                    item.model_copy(
                        update={
                            "calculation_status": "Calculated"
                            if item.employee_contribution is not None
                            else "Not calculated"
                        }
                    )
                    for item in page.items
                ]
            }
        )

    def professional_tax_employees(
        self, month: date, search: str | None, department_id: int | None, state_id: int | None
    ) -> list[PtEmployee]:
        """Active employees with the state that decides professional tax.

        The state is the professional-tax state on the employee, or the work branch's state.
        A branch or city name is not used.
        """
        branch_state = aliased(State)
        profile_state = aliased(State)
        applicable_id = func.coalesce(EmployeeProfile.pt_state_id, Branch.state_id)
        applicable_name = case(
            (EmployeeProfile.pt_state_id.is_not(None), profile_state.name),
            else_=branch_state.name,
        )
        statement = (
            select(
                Employee.id.label("employee_id"),
                Employee.employee_code.label("employee_code"),
                _full_name(),
                Department.name.label("department"),
                applicable_id.label("state_id"),
                applicable_name.label("state_name"),
            )
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(Branch, Branch.id == Employee.branch_id)
            .outerjoin(branch_state, branch_state.id == Branch.state_id)
            .outerjoin(EmployeeProfile, EmployeeProfile.employee_id == Employee.id)
            .outerjoin(profile_state, profile_state.id == EmployeeProfile.pt_state_id)
            .where(Employee.status == "Active", Employee.is_active == True)  # noqa: E712
        )
        if department_id is not None:
            statement = statement.where(Employee.department_id == department_id)
        if state_id is not None:
            statement = statement.where(applicable_id == state_id)
        if search and search.strip():
            term = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Employee.employee_code.ilike(term),
                    _full_name().ilike(term),
                    Department.name.ilike(term),
                    applicable_name.ilike(term),
                    Branch.name.ilike(term),
                )
            )
        statement = statement.order_by(Employee.employee_code.asc(), Employee.id.asc())
        wages = self._payroll_wages(month)
        stored = self._stored_contributions(month, SCHEME_CODES["PT"])
        employees: list[PtEmployee] = []
        for row in self._session.execute(statement):
            employees.append(
                PtEmployee(
                    employee_id=int(row.employee_id),
                    employee_code=row.employee_code,
                    full_name=row.full_name,
                    department=row.department,
                    state_id=int(row.state_id) if row.state_id is not None else None,
                    state_name=row.state_name,
                    wages=_decimal(wages.get(int(row.employee_id))),
                    stored_amount=_decimal(stored.get(int(row.employee_id))),
                )
            )
        return employees

    def _payroll_wages(self, month: date) -> dict[int, Decimal]:
        rows = self._session.execute(
            select(Payslip.employee_id, func.sum(Payslip.gross))
            .join(PayrollRun, PayrollRun.id == Payslip.payroll_run_id)
            .where(PayrollRun.period_month == month_start(month), Payslip.is_active == True)  # noqa: E712
            .group_by(Payslip.employee_id)
        )
        return {int(employee_id): amount for employee_id, amount in rows}

    def _stored_contributions(self, month: date, codes: tuple[str, ...]) -> dict[int, Decimal]:
        if not codes:
            return {}
        rows = self._session.execute(
            select(Payslip.employee_id, func.sum(PayslipLine.amount))
            .join(PayslipLine, PayslipLine.payslip_id == Payslip.id)
            .join(PayrollRun, PayrollRun.id == Payslip.payroll_run_id)
            .join(SalaryComponent, SalaryComponent.id == PayslipLine.salary_component_id)
            .where(
                PayrollRun.period_month == month_start(month),
                SalaryComponent.code.in_(codes),
                PayslipLine.is_active == True,  # noqa: E712
            )
            .group_by(Payslip.employee_id)
        )
        return {int(employee_id): amount for employee_id, amount in rows}

    def add(self, rule: StatutoryConfig) -> None:
        self._session.add(rule)

    def commit(self) -> None:
        self._session.commit()


def to_rule(
    rule: StatutoryConfig,
    effective_to: date | None,
    state_name: str | None,
    created_by: str | None,
    updated_by: str | None,
) -> StatutoryRule:
    return StatutoryRule(
        id=int(rule.id),
        config_type=rule.config_type,
        state_id=rule.state_id,
        state_name=state_name,
        effective_from=rule.effective_from,
        effective_to=effective_to,
        employee_rate=rule.employee_rate,
        employer_rate=rule.employer_rate,
        wage_ceiling=rule.wage_ceiling,
        slab_json=rule.slab_json,
        is_active=rule.is_active,
        created_at=rule.created_at,
        created_by=created_by,
        updated_at=rule.updated_at,
        updated_by=updated_by,
        row_version=rule.row_version,
    )


def closing_dates(rules: list[StatutoryConfig]) -> dict[int, date | None]:
    """The saved row has no effective-to column. The next rule for the same scheme and state closes it."""
    grouped: dict[tuple[str, int | None], list[StatutoryConfig]] = {}
    for rule in rules:
        grouped.setdefault((rule.config_type, rule.state_id), []).append(rule)
    ends: dict[int, date | None] = {}
    for group in grouped.values():
        ordered = sorted(group, key=lambda row: (row.effective_from, row.id))
        for current, nxt in itertools.pairwise(ordered):
            ends[int(current.id)] = nxt.effective_from - timedelta(days=1)
    return ends


def _decimal(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _codes(scheme: Scheme | None) -> tuple[str, ...]:
    if scheme is None:
        return tuple(code for codes in SCHEME_CODES.values() for code in codes)
    return SCHEME_CODES[scheme]


def _full_name() -> Any:
    return func.trim(Employee.first_name + literal(" ") + func.coalesce(Employee.last_name, literal(""))).label(
        "full_name"
    )


def _eligible(start: date, end: date) -> tuple[Any, ...]:
    covered = (
        select(SalaryStructure.id)
        .where(
            SalaryStructure.employee_id == Employee.id,
            SalaryStructure.is_active == True,  # noqa: E712
            SalaryStructure.effective_from <= end,
            or_(SalaryStructure.effective_to.is_(None), SalaryStructure.effective_to >= start),
        )
        .exists()
    )
    return (Employee.status == "Active", Employee.is_active == True, covered)  # noqa: E712


def _line_amount(scheme: Scheme, month: date) -> Any:
    codes = SCHEME_CODES[scheme]
    if not codes:
        return literal(None)
    return (
        select(func.sum(PayslipLine.amount))
        .join(Payslip, Payslip.id == PayslipLine.payslip_id)
        .join(PayrollRun, PayrollRun.id == Payslip.payroll_run_id)
        .join(SalaryComponent, SalaryComponent.id == PayslipLine.salary_component_id)
        .where(
            Payslip.employee_id == Employee.id,
            PayrollRun.period_month == month,
            SalaryComponent.code.in_(codes),
            PayslipLine.is_active == True,  # noqa: E712
        )
        .correlate(Employee)
        .scalar_subquery()
    )
