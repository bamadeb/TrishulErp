"""Calculates a payroll month from saved salary structures. Rates stay on those lines."""

import ast
import calendar
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError, NotFound
from trishul_api.db.models import AuditLog, PayrollRun, Payslip, PayslipLine
from trishul_api.modules.hr.payroll.run_repository import (
    EmployeeFact,
    PayableEmployee,
    PayableLine,
    PayrollRunRepository,
    SavedSettlement,
)
from trishul_api.modules.hr.payroll.run_schemas import (
    PayrollDifference,
    PayrollEmployeeDetail,
    PayrollLine,
    PayrollPreview,
    PayrollRunItem,
    PayrollRunRequest,
)
from trishul_api.modules.hr.payroll.statutory_repository import month_end, month_start

_MONEY = Decimal("0.01")
_HUNDRED = Decimal("100")
_AMOUNT = re.compile(r"Paid amount:\s*₹?\s*([0-9][0-9,]*(?:\.\d+)?)")
_MODE = re.compile(r"Payment mode:\s*([^|]+)")
_REFERENCE = re.compile(r"Payment reference:\s*([^|]+)")
_CLOSED = frozenset({"Approved", "Paid", "Locked"})
_LABELS = {
    "BASIC": "Basic",
    "HRA": "HRA",
    "CONV": "Conveyance",
    "SPL": "Special Allowance",
    "OTH_ALLOW": "Other Allowance",
    "FIX_INC": "Fixed Incentive",
    "PF": "PF",
    "ESI": "ESI",
    "PT": "Professional Tax",
    "IT": "TDS",
    "LOAN": "Loan",
    "SAL_ADV": "Salary Advance",
    "OTH_DED": "Other deductions",
    "TADA": "TA/DA Reimbursement",
}
_EARNINGS = ("BASIC", "HRA", "CONV", "SPL", "OTH_ALLOW", "FIX_INC")
_DEDUCTIONS = ("PF", "ESI", "PT", "IT", "LOAN", "SAL_ADV", "OTH_DED")


class _Wait(Enum):
    WAIT = "wait"
    SKIP = "skip"


@dataclass(frozen=True)
class PayrollAmount:
    history_id: int
    employee_id: int
    company_id: int
    amount: Decimal
    reference: str | None


@dataclass(frozen=True)
class BuiltLine:
    code: str
    name: str
    amount: Decimal
    source: str
    component_id: int | None
    deduction: bool


@dataclass(frozen=True)
class BuiltSlip:
    employee_id: int
    company_id: int
    paid_days: Decimal
    lop_days: Decimal
    lines: list[BuiltLine]
    gross: Decimal
    deductions: Decimal
    net_pay: Decimal


class PayrollRunService:
    def __init__(self, db: Session) -> None:
        self._repo = PayrollRunRepository(db)

    def list_runs(self) -> list[PayrollRunItem]:
        return self._repo.list_runs()

    def process(self, actor: CurrentUser, data: PayrollRunRequest) -> list[PayrollRunItem]:
        month = month_start(data.month)
        from trishul_api.modules.hr.attendance.finalization_ops import require_month_finalized

        require_month_finalized(self._repo._session, month.year, month.month)
        slips = self._slips(month)
        if not slips:
            covered = [person for person in self._repo.payable(month) if _covers(person, month)]
            if covered:
                raise ApiError("The salary structures for this month have no amounts to calculate.")
            raise ApiError("No employee has a salary structure for this month.")
        companies = {slip.company_id for slip in slips}
        for company_id in companies:
            if self._repo.existing(company_id, month) is not None:
                raise ApiError("Payroll for this month is already processed.")
        created: list[int] = []
        for company_id in sorted(companies):
            company_slips = [slip for slip in slips if slip.company_id == company_id]
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
            self._store(actor, run, company_slips, previous=None)
            created.append(int(run.id))
        self._repo.commit()
        saved = {item.id: item for item in self._repo.list_runs()}
        return [saved[run_id] for run_id in created]

    def details(self, run_id: int) -> list[PayrollEmployeeDetail]:
        run = self._open_run(run_id)
        return self._saved(run)

    def preview(self, run_id: int) -> PayrollPreview:
        run = self._open_run(run_id)
        self._ensure_editable(run)
        current = self._saved(run)
        nxt = self._details_for(run.company_id, self._slips(run.period_month))
        return _preview(run, current, nxt)

    def recalculate(self, actor: CurrentUser, run_id: int) -> PayrollRunItem:
        run = self._open_run(run_id)
        self._ensure_editable(run)
        from trishul_api.modules.hr.attendance.finalization_ops import require_month_finalized

        period = month_start(run.period_month)
        require_month_finalized(self._repo._session, period.year, period.month)
        current = self._saved(run)
        nxt = [slip for slip in self._slips(run.period_month) if slip.company_id == run.company_id]
        if not nxt:
            raise ApiError("No employee has a salary structure for this month.")
        self._repo.clear_payslips(int(run.id))
        self._store(actor, run, nxt, previous=current)
        self._repo.commit()
        saved = {item.id: item for item in self._repo.list_runs()}
        return saved[int(run.id)]

    def _open_run(self, run_id: int) -> PayrollRun:
        run = self._repo.run(run_id)
        if run is None:
            raise NotFound("Payroll run not found.")
        return run

    def _ensure_editable(self, run: PayrollRun) -> None:
        if run.status in _CLOSED:
            raise ApiError(f"This payroll is {run.status}. Recalculate it only after it is reopened.")

    def _slips(self, month: date) -> list[BuiltSlip]:
        people = [person for person in self._repo.payable(month) if _covers(person, month)]
        by_structure = _grouped(self._repo.lines([person.structure_id for person in people], month))
        settlements = {
            item.employee_id: item
            for item in (_payroll_settlement(row) for row in self._repo.settlements(month))
            if item is not None
        }
        facts = self._repo.employees([person.employee_id for person in people] + list(settlements))
        built: list[BuiltSlip] = []
        covered = {person.employee_id for person in people}
        for person in people:
            lines = by_structure.get(person.structure_id, [])
            amounts = _calculate(lines, _factor(person, month, self._repo))
            settlement = settlements.get(person.employee_id)
            if not amounts and settlement is None:
                continue
            paid, lost = _days(person, month, self._repo)
            built.append(_slip(person.employee_id, person.company_id, paid, lost, lines, amounts, settlement))
        for employee_id, settlement in settlements.items():
            if employee_id in covered:
                continue
            fact = facts.get(employee_id)
            company_id = fact.company_id if fact is not None else settlement.company_id
            built.append(
                _slip(employee_id, company_id, Decimal("0.0"), Decimal("0.0"), [], {}, settlement)
            )
        return built

    def _store(
        self,
        actor: CurrentUser,
        run: PayrollRun,
        slips: list[BuiltSlip],
        previous: list[PayrollEmployeeDetail] | None,
    ) -> None:
        gross = deductions = net = Decimal("0.00")
        for slip in slips:
            row = Payslip(
                payroll_run_id=int(run.id),
                employee_id=slip.employee_id,
                paid_days=slip.paid_days,
                lop_days=slip.lop_days,
                gross=slip.gross,
                total_deductions=slip.deductions,
                net_pay=slip.net_pay,
                is_active=True,
                created_by_user_id=actor.id,
            )
            self._repo.add(row)
            self._repo.flush()
            for line in slip.lines:
                if line.component_id is None:
                    continue
                self._repo.add(
                    PayslipLine(
                        payslip_id=int(row.id),
                        salary_component_id=line.component_id,
                        amount=line.amount,
                        is_active=True,
                        created_by_user_id=actor.id,
                    )
                )
            gross += slip.gross
            deductions += slip.deductions
            net += slip.net_pay
        run.total_gross = gross
        run.total_deductions = deductions
        run.total_net = net
        details = self._details_for(run.company_id, slips)
        self._repo.record(
            AuditLog(
                entity_type="hr.payroll_run",
                entity_id=int(run.id),
                action="Insert" if previous is None else "Update",
                old_values=None if previous is None else _dump(previous),
                new_values=_dump(details),
                changed_by_user_id=actor.id,
                changed_at=datetime.now(UTC).replace(tzinfo=None),
                source="API",
                ip_address=None,
            )
        )

    def _saved(self, run: PayrollRun) -> list[PayrollEmployeeDetail]:
        raw = self._repo.snapshot(int(run.id))
        if raw:
            return [PayrollEmployeeDetail.model_validate(item) for item in json.loads(raw)]
        slips = self._repo.payslips(int(run.id))
        facts = self._repo.employees([int(slip.employee_id) for slip, _code, _name in slips])
        saved: list[PayrollEmployeeDetail] = []
        for slip, code, name in slips:
            fact = facts.get(int(slip.employee_id))
            lines = [
                PayrollLine(
                    code=item_code,
                    name=_LABELS.get(item_code, item_name),
                    amount=amount,
                    source="Saved payslip",
                )
                for item_code, item_name, amount in self._repo.payslip_lines(int(slip.id))
            ]
            saved.append(
                PayrollEmployeeDetail(
                    employee_id=int(slip.employee_id),
                    employee_code=fact.employee_code if fact else code,
                    full_name=fact.full_name if fact else name,
                    department=fact.department if fact else None,
                    designation=fact.designation if fact else None,
                    paid_days=slip.paid_days,
                    lop_days=slip.lop_days,
                    gross=slip.gross,
                    deductions=slip.total_deductions,
                    net_pay=slip.net_pay,
                    lines=lines,
                )
            )
        return saved

    def _details_for(self, company_id: int, slips: list[BuiltSlip]) -> list[PayrollEmployeeDetail]:
        chosen = [slip for slip in slips if slip.company_id == company_id]
        facts = self._repo.employees([slip.employee_id for slip in chosen])
        return _details(facts, chosen)


def _payroll_settlement(row: SavedSettlement) -> PayrollAmount | None:
    remarks = row.remarks or ""
    mode = _MODE.search(remarks)
    if mode is None or mode.group(1).strip().casefold() != "payroll":
        return None
    found = _AMOUNT.search(remarks)
    if found is None:
        return None
    amount = _money(Decimal(found.group(1).replace(",", "")))
    if amount <= 0:
        return None
    reference = _REFERENCE.search(remarks)
    text = reference.group(1).strip() if reference else None
    return PayrollAmount(row.history_id, row.employee_id, row.company_id, amount, text or None)


def _slip(
    employee_id: int,
    company_id: int,
    paid: Decimal,
    lost: Decimal,
    lines: list[PayableLine],
    amounts: dict[int, Decimal],
    settlement: PayrollAmount | None,
) -> BuiltSlip:
    by_id = {line.salary_component_id: line for line in lines}
    built = [
        BuiltLine(
            code=by_id[component_id].code,
            name=_LABELS.get(by_id[component_id].code, by_id[component_id].name),
            amount=amount,
            source=_source(by_id[component_id], paid, lost),
            component_id=component_id,
            deduction=by_id[component_id].component_type == "Employee Deduction",
        )
        for component_id, amount in amounts.items()
    ]
    gross, deductions, net = _totals(lines, amounts) if lines else (Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))
    if settlement is not None:
        source = f"TA/DA settlement {settlement.history_id}, payment mode Payroll"
        if settlement.reference:
            source = f"{source}, reference {settlement.reference}"
        built.append(
            BuiltLine("TADA", _LABELS["TADA"], settlement.amount, source, None, False)
        )
        gross = _money(gross + settlement.amount)
        net = _money(net + settlement.amount)
    built.sort(key=lambda item: (_line_order(item), item.code))
    return BuiltSlip(employee_id, company_id, paid, lost, built, gross, deductions, net)


def _source(line: PayableLine, paid: Decimal, lost: Decimal) -> str:
    text = f"Salary structure {line.structure_id}. {line.calculation_type}"
    if line.calculation_basis:
        text = f"{text}, basis {line.calculation_basis}"
    if line.is_prorated:
        text = f"{text}, paid days {paid}, LOP {lost}"
    return text


def _line_order(line: BuiltLine) -> tuple[int, int]:
    if line.code in _EARNINGS:
        return (0, _EARNINGS.index(line.code))
    if line.code == "TADA":
        return (1, 0)
    if line.deduction and line.code in _DEDUCTIONS:
        return (3, _DEDUCTIONS.index(line.code))
    if line.deduction:
        return (4, 0)
    return (2, 0)


def _details(facts: dict[int, EmployeeFact], slips: list[BuiltSlip]) -> list[PayrollEmployeeDetail]:
    rows: list[PayrollEmployeeDetail] = []
    for slip in slips:
        fact = facts.get(slip.employee_id)
        rows.append(
            PayrollEmployeeDetail(
                employee_id=slip.employee_id,
                employee_code=fact.employee_code if fact else str(slip.employee_id),
                full_name=fact.full_name if fact else "",
                department=fact.department if fact else None,
                designation=fact.designation if fact else None,
                paid_days=slip.paid_days,
                lop_days=slip.lop_days,
                gross=slip.gross,
                deductions=slip.deductions,
                net_pay=slip.net_pay,
                lines=[
                    PayrollLine(code=line.code, name=line.name, amount=line.amount, source=line.source)
                    for line in slip.lines
                ],
            )
        )
    return rows


def _dump(rows: list[PayrollEmployeeDetail]) -> str:
    return json.dumps([row.model_dump(mode="json", by_alias=True) for row in rows])


def _preview(run: PayrollRun, current: list[PayrollEmployeeDetail], nxt: list[PayrollEmployeeDetail]) -> PayrollPreview:
    previous = {item.employee_code: item for item in current}
    following = {item.employee_code: item for item in nxt}
    differences: list[PayrollDifference] = []
    for code in dict.fromkeys([*previous, *following]):
        old = previous.get(code)
        new = following.get(code)
        if old is not None and new is not None and old.net_pay == new.net_pay and old.gross == new.gross:
            change = "Unchanged"
        elif old is not None and new is not None:
            change = "Changed"
        elif new is not None:
            change = "Added"
        else:
            change = "Removed"
        person = new or old
        assert person is not None
        differences.append(
            PayrollDifference(
                employee_code=code,
                full_name=person.full_name,
                previous_net=None if old is None else old.net_pay,
                next_net=None if new is None else new.net_pay,
                change=change,
            )
        )
    return PayrollPreview(
        run_id=int(run.id),
        status=run.status,
        previous_employees=len(current),
        next_employees=len(nxt),
        previous_gross=_sum(current, "gross"),
        next_gross=_sum(nxt, "gross"),
        previous_deductions=_sum(current, "deductions"),
        next_deductions=_sum(nxt, "deductions"),
        previous_net=_sum(current, "net_pay"),
        next_net=_sum(nxt, "net_pay"),
        differences=differences,
    )


def _sum(rows: list[PayrollEmployeeDetail], field: str) -> Decimal:
    return _money(sum((getattr(row, field) for row in rows), Decimal("0")))


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
