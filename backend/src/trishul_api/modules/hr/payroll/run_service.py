"""Calculates a payroll month from saved salary structures. Rates stay on those lines."""

import ast
import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError
from trishul_api.db.models import PayrollRun, Payslip, PayslipLine
from trishul_api.modules.hr.payroll.run_repository import PayableEmployee, PayableLine, PayrollRunRepository
from trishul_api.modules.hr.payroll.run_schemas import PayrollRunItem, PayrollRunRequest
from trishul_api.modules.hr.payroll.statutory_repository import month_end, month_start

_MONEY = Decimal("0.01")
_HUNDRED = Decimal("100")


class _Wait(Enum):
    WAIT = "wait"
    SKIP = "skip"


class PayrollRunService:
    def __init__(self, db: Session) -> None:
        self._repo = PayrollRunRepository(db)

    def list_runs(self) -> list[PayrollRunItem]:
        return self._repo.list_runs()

    def process(self, actor: CurrentUser, data: PayrollRunRequest) -> list[PayrollRunItem]:
        month = month_start(data.month)
        people = [person for person in self._repo.payable(month) if _covers(person, month)]
        if not people:
            raise ApiError("No employee has a salary structure for this month.")
        companies = {person.company_id for person in people}
        for company_id in companies:
            if self._repo.existing(company_id, month) is not None:
                raise ApiError("Payroll for this month is already processed.")
        by_structure = _grouped(self._repo.lines([person.structure_id for person in people], month))
        created: list[int] = []
        for company_id in sorted(companies):
            run = PayrollRun(
                company_id=company_id,
                branch_id=None,
                period_month=month,
                run_date=date.today(),
                status="Processed",
                total_gross=Decimal("0.00"),
                total_deductions=Decimal("0.00"),
                total_net=Decimal("0.00"),
                is_active=True,
                created_by_user_id=actor.id,
            )
            self._repo.add(run)
            self._repo.flush()
            gross = deductions = net = Decimal("0.00")
            payslips = 0
            for person in people:
                if person.company_id != company_id:
                    continue
                amounts = _calculate(by_structure.get(person.structure_id, []), _factor(person, month, self._repo))
                if not amounts:
                    continue
                slip_gross, slip_deductions, slip_net = _totals(by_structure[person.structure_id], amounts)
                paid, lost = _days(person, month, self._repo)
                slip = Payslip(
                    payroll_run_id=int(run.id),
                    employee_id=person.employee_id,
                    paid_days=paid,
                    lop_days=lost,
                    gross=slip_gross,
                    total_deductions=slip_deductions,
                    net_pay=slip_net,
                    is_active=True,
                    created_by_user_id=actor.id,
                )
                self._repo.add(slip)
                self._repo.flush()
                for component_id, amount in amounts.items():
                    self._repo.add(
                        PayslipLine(
                            payslip_id=int(slip.id),
                            salary_component_id=component_id,
                            amount=amount,
                            is_active=True,
                            created_by_user_id=actor.id,
                        )
                    )
                gross += slip_gross
                deductions += slip_deductions
                net += slip_net
                payslips += 1
            if payslips == 0:
                raise ApiError("The salary structures for this month have no amounts to calculate.")
            run.total_gross = gross
            run.total_deductions = deductions
            run.total_net = net
            created.append(int(run.id))
        self._repo.commit()
        saved = {item.id: item for item in self._repo.list_runs()}
        return [saved[run_id] for run_id in created]


def _covers(person: PayableEmployee, month: date) -> bool:
    return _window(person, month) is not None


def _window(person: PayableEmployee, month: date) -> tuple[date, date] | None:
    start, end = month_start(month), month_end(month)
    first = person.effective_from
    if person.joining is not None:
        first = max(first, person.joining)
    first = max(first, start)
    last = end if person.effective_to is None else min(person.effective_to, end)
    if person.exited is not None:
        last = min(last, person.exited)
    if last < first:
        return None
    return first, last


def _days(person: PayableEmployee, month: date, repo: PayrollRunRepository) -> tuple[Decimal, Decimal]:
    window = _window(person, month)
    assert window is not None
    first, last = window
    covered = Decimal((last - first).days + 1)
    lost = min(repo.lop_days(person.employee_id, first, last), covered)
    return covered - lost, lost


def _factor(person: PayableEmployee, month: date, repo: PayrollRunRepository) -> Decimal:
    start = month_start(month)
    calendar_days = Decimal(calendar.monthrange(start.year, start.month)[1])
    paid, _lost = _days(person, month, repo)
    if calendar_days == 0:
        return Decimal("0")
    return paid / calendar_days


def _grouped(lines: list[PayableLine]) -> dict[int, list[PayableLine]]:
    grouped: dict[int, list[PayableLine]] = {}
    for line in lines:
        grouped.setdefault(line.structure_id, []).append(line)
    return grouped


def _calculate(lines: list[PayableLine], factor: Decimal) -> dict[int, Decimal]:
    pending = list(lines)
    done: dict[int, Decimal] = {}
    for _ in range(len(lines) + 1):
        if not pending:
            break
        still: list[PayableLine] = []
        progressed = False
        known = {line.code for line in lines if line.salary_component_id in done}
        for line in pending:
            resolved = _resolve(line, lines, done, known)
            if resolved is _Wait.WAIT:
                still.append(line)
                continue
            if resolved is _Wait.SKIP:
                progressed = True
                continue
            amount = resolved
            if line.is_prorated:
                amount = amount * factor
            done[line.salary_component_id] = _money(amount)
            progressed = True
        pending = still
        if not progressed:
            break
    return done


def _resolve(
    line: PayableLine, lines: list[PayableLine], done: dict[int, Decimal], known: set[str]
) -> Decimal | _Wait:
    if line.calculation_type == "Fixed Amount":
        return line.monthly_amount if line.monthly_amount is not None else _Wait.SKIP
    if line.calculation_type == "Manual Entry":
        return line.monthly_amount if line.monthly_amount is not None else _Wait.SKIP
    if line.calculation_type == "Percentage":
        return _percentage(line, lines, done)
    if line.calculation_type == "Formula":
        return _formula(line, lines, done, known)
    return _Wait.SKIP


def _percentage(line: PayableLine, lines: list[PayableLine], done: dict[int, Decimal]) -> Decimal | _Wait:
    if line.percentage is None:
        return _Wait.SKIP
    basis = _basis(line, lines, done)
    if basis is _Wait.WAIT or basis is _Wait.SKIP:
        return basis
    return basis * line.percentage / _HUNDRED


def _basis(line: PayableLine, lines: list[PayableLine], done: dict[int, Decimal]) -> Decimal | _Wait:
    basis = line.calculation_basis
    if basis == "Basic Salary":
        basic = [item for item in lines if item.code == "BASIC"]
        if not basic:
            return _Wait.SKIP
        if any(item.salary_component_id not in done for item in basic):
            return _Wait.WAIT
        return sum((done[item.salary_component_id] for item in basic), Decimal("0"))
    if basis == "Gross Earnings":
        return _sum_when_ready(
            line,
            lines,
            done,
            lambda item: item.component_type == "Earning" and item.include_in_gross,
        )
    if basis == "Eligible PF Wages":
        return _sum_when_ready(line, lines, done, lambda item: item.is_pf_wage)
    if basis == "Eligible ESI Wages":
        return _sum_when_ready(line, lines, done, lambda item: item.is_esi_wage)
    return _Wait.SKIP


def _sum_when_ready(
    line: PayableLine, lines: list[PayableLine], done: dict[int, Decimal], include
) -> Decimal | _Wait:
    relevant = [item for item in lines if item.salary_component_id != line.salary_component_id and include(item)]
    if any(item.salary_component_id not in done for item in relevant):
        return _Wait.WAIT
    return sum((done[item.salary_component_id] for item in relevant), Decimal("0"))


def _formula(
    line: PayableLine, lines: list[PayableLine], done: dict[int, Decimal], known: set[str]
) -> Decimal | _Wait:
    if not line.formula:
        return _Wait.SKIP
    names = {item.code: done[item.salary_component_id] for item in lines if item.salary_component_id in done}
    try:
        tree = ast.parse(line.formula, mode="eval")
    except SyntaxError:
        return _Wait.SKIP
    missing = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id not in names]
    codes = {item.code for item in lines}
    if any(name not in {"MIN", "MAX", "ROUND"} and name not in known and name in codes for name in missing):
        return _Wait.WAIT
    if any(name not in names and name not in {"MIN", "MAX", "ROUND"} for name in missing):
        return _Wait.SKIP
    try:
        return _evaluate(tree, names)
    except (ValueError, KeyError, ArithmeticError):
        return _Wait.SKIP


def _evaluate(tree: ast.Expression, names: dict[str, Decimal]) -> Decimal:
    def walk(node: ast.AST) -> Decimal:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return Decimal(str(node.value))
        if isinstance(node, ast.Name):
            return names[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
            value = walk(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add | ast.Sub | ast.Mult | ast.Div):
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            return left / right
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"MIN", "MAX", "ROUND"}:
            args = [walk(arg) for arg in node.args]
            if node.func.id == "MIN" and args:
                return min(args)
            if node.func.id == "MAX" and args:
                return max(args)
            if node.func.id == "ROUND" and len(args) == 2:
                places = int(args[1])
                return args[0].quantize(Decimal("1").scaleb(-places))
        raise ValueError(line_text(node))

    return walk(tree)


def line_text(node: ast.AST) -> str:
    return type(node).__name__


def _totals(lines: list[PayableLine], amounts: dict[int, Decimal]) -> tuple[Decimal, Decimal, Decimal]:
    gross = deductions = net = Decimal("0.00")
    by_id = {line.salary_component_id: line for line in lines}
    for component_id, amount in amounts.items():
        line = by_id[component_id]
        if line.component_type == "Earning" and line.include_in_gross:
            gross += amount
        if line.include_in_net_pay and line.component_type == "Employee Deduction":
            deductions += amount
            net -= amount
        elif line.include_in_net_pay and line.component_type in {"Earning", "Reimbursement"}:
            net += amount
    return _money(gross), _money(deductions), _money(net)


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)
