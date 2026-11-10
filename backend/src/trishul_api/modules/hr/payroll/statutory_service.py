"""Saves statutory rules on hr.statutory_config. Payroll calculation is a later step."""

import json
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, NotFound
from trishul_api.common.schemas import Page
from trishul_api.db.models import StatutoryConfig
from trishul_api.modules.hr.payroll.statutory_repository import (
    SCHEME_NAMES,
    PtEmployee,
    StatutoryRepository,
    closing_dates,
    month_end,
    month_start,
    to_rule,
)
from trishul_api.modules.hr.payroll.statutory_schemas import (
    CalculationStatus,
    Scheme,
    StatutoryContribution,
    StatutoryContributionQuery,
    StatutoryRule,
    StatutoryRuleWrite,
    StatutorySchemeStatus,
    StatutorySummary,
    StatutorySummaryQuery,
)

# Odisha abolished its professional tax with effect from this date. Earlier months keep their own result.
ODISHA_PT_REPEALED = date(2026, 4, 1)
ODISHA_PT_REASON = "Odisha professional tax was repealed from 1 April 2026."


class StatutoryService:
    def __init__(self, db: Session) -> None:
        self._repo = StatutoryRepository(db)

    def summary(self, query: StatutorySummaryQuery) -> StatutorySummary:
        month = month_start(query.month)
        rules = [rule for rule in self._repo.rules() if rule.is_active and rule.effective_from <= month_end(month)]
        configured = {rule.config_type for rule in rules}
        pt_rows = self.professional_tax(month, None, None, None)
        schemes = [
            _pt_scheme(pt_rows, "PT" in configured)
            if scheme == "PT"
            else _scheme(scheme, scheme in configured, self._repo.employee_contribution(month, scheme))
            for scheme in SCHEME_NAMES
        ]
        if query.scheme == "PT":
            employee, employer, total, eligible, calculation = _pt_totals(pt_rows)
        else:
            employee = self._repo.employee_contribution(month, None)
            employer = None
            total = None
            eligible = self._repo.eligible_count(month)
            calculation = (
                "Calculated"
                if employee is not None or any(item.calculation_status == "Calculated" for item in schemes)
                else "Not calculated"
            )
        ready = len(configured.intersection(SCHEME_NAMES))
        status: Literal["Configured", "Partial", "Not configured"] = (
            "Configured" if ready == len(SCHEME_NAMES) else "Partial" if ready else "Not configured"
        )
        return StatutorySummary(
            month=month,
            financial_year=_financial_year(month),
            eligible_employees=eligible,
            employee_contribution=employee,
            employer_contribution=employer,
            total_liability=total,
            configuration_status=status,
            calculation_status=calculation,
            filing_status="Not filed",
            schemes=schemes,
            states=self._repo.states(),
            departments=self._repo.departments(),
        )

    def rules(self, scheme: Scheme | None) -> list[StatutoryRule]:
        saved = self._repo.rules(scheme)
        ends = closing_dates(saved)
        return [self._present(rule, ends.get(int(rule.id))) for rule in saved]

    def save_rule(self, actor: CurrentUser, data: StatutoryRuleWrite) -> StatutoryRule:
        self._check(data, None)
        company_id = self._repo.company_id()
        if company_id is None:
            raise ApiError("Save the company before a statutory rule.")
        rule = StatutoryConfig(
            company_id=company_id,
            config_type=data.config_type,
            state_id=data.state_id,
            effective_from=data.effective_from,
            employee_rate=data.employee_rate,
            employer_rate=data.employer_rate,
            wage_ceiling=data.wage_ceiling,
            slab_json=data.slab_json,
            is_active=data.is_active,
            created_by_user_id=actor.id,
        )
        self._repo.add(rule)
        self._repo.commit()
        return self._present(rule, closing_dates(self._repo.rules(data.config_type)).get(int(rule.id)))

    def update_rule(self, actor: CurrentUser, rule_id: int, expected: bytes, data: StatutoryRuleWrite) -> StatutoryRule:
        rule = self._repo.rule(rule_id)
        if rule is None:
            raise NotFound("Statutory rule not found.")
        check_row_version(rule.row_version, expected)
        self._check(data, rule_id)
        rule.config_type = data.config_type
        rule.state_id = data.state_id
        rule.effective_from = data.effective_from
        rule.employee_rate = data.employee_rate
        rule.employer_rate = data.employer_rate
        rule.wage_ceiling = data.wage_ceiling
        rule.slab_json = data.slab_json
        rule.is_active = data.is_active
        rule.updated_by_user_id = actor.id
        self._repo.commit()
        return self._present(rule, closing_dates(self._repo.rules(data.config_type)).get(rule_id))

    def contributions(self, query: StatutoryContributionQuery) -> Page[StatutoryContribution]:
        if query.scheme != "PT":
            return self._repo.contributions(query)
        rows = self.professional_tax(query.month, query.search, query.department_id, query.state_id)
        start = (query.page - 1) * query.page_size
        return Page(
            items=rows[start : start + query.page_size],
            total=len(rows),
            page=query.page,
            page_size=query.page_size,
        )

    def professional_tax(
        self, month: date, search: str | None, department_id: int | None, state_id: int | None
    ) -> list[StatutoryContribution]:
        rules = self._repo.rules("PT")
        ends = closing_dates(rules)
        return [
            _classify_pt(month_start(month), employee, rules, ends)
            for employee in self._repo.professional_tax_employees(month, search, department_id, state_id)
        ]

    def _check(self, data: StatutoryRuleWrite, ignore_id: int | None) -> None:
        if data.config_type == "PT" and data.state_id is None:
            raise ApiError(
                "Professional tax needs a state.",
                errors={"stateId": ["Choose the state this rule applies to."]},
            )
        has_value = data.employee_rate is not None or data.employer_rate is not None or data.wage_ceiling is not None
        if not has_value and not data.slab_json:
            raise ApiError(
                "Enter a rate, a ceiling, or the slabs. A rate is not assumed.",
                errors={"employeeRate": ["Enter the value that applies."]},
            )
        if self._repo.same_start(data.config_type, data.state_id, data.effective_from, ignore_id):
            raise ApiError(
                "A rule for this scheme already starts on that date.",
                errors={"effectiveFrom": ["Choose another effective from, or edit the saved rule."]},
            )

    def _present(self, rule: StatutoryConfig, effective_to: date | None) -> StatutoryRule:
        return to_rule(
            rule,
            effective_to,
            self._repo.state_name(rule.state_id),
            self._repo.username(rule.created_by_user_id),
            self._repo.username(rule.updated_by_user_id),
        )


def _scheme(scheme: Scheme, configured: bool, contribution: object) -> StatutorySchemeStatus:
    return StatutorySchemeStatus(
        scheme=scheme,
        name=SCHEME_NAMES[scheme],
        configuration_status="Configured" if configured else "Not configured",
        calculation_status="Calculated" if contribution is not None else "Not calculated",
        filing_status="Not filed",
    )


def _pt_scheme(rows: list[StatutoryContribution], configured: bool) -> StatutorySchemeStatus:
    return StatutorySchemeStatus(
        scheme="PT",
        name=SCHEME_NAMES["PT"],
        configuration_status="Configured" if configured else "Not configured",
        calculation_status=_pt_calculation(rows),
        filing_status="Not filed",
    )


def _pt_totals(
    rows: list[StatutoryContribution],
) -> tuple[Decimal | None, Decimal | None, Decimal | None, int, CalculationStatus]:
    employee_amounts = [row.employee_contribution for row in rows if row.employee_contribution is not None]
    employer_amounts = [row.employer_contribution for row in rows if row.employer_contribution is not None]
    employee = sum(employee_amounts, Decimal("0.00")) if employee_amounts else None
    employer = sum(employer_amounts, Decimal("0.00")) if employer_amounts else None
    if employee is None and employer is None:
        total = None
    else:
        total = (employee or Decimal("0.00")) + (employer or Decimal("0.00"))
    eligible = sum(1 for row in rows if row.calculation_status != "Not applicable")
    return employee, employer, total, eligible, _pt_calculation(rows)


def _pt_calculation(rows: list[StatutoryContribution]) -> CalculationStatus:
    if not rows or any(row.calculation_status == "Not calculated" for row in rows):
        return "Not calculated"
    if all(row.calculation_status == "Not applicable" for row in rows):
        return "Not applicable"
    return "Calculated"


def _classify_pt(
    month: date, employee: PtEmployee, rules: list[StatutoryConfig], ends: dict[int, date | None]
) -> StatutoryContribution:
    state = (employee.state_name or "").strip()
    if employee.state_id is None:
        return _pt_row(employee, None, _zero(), _zero(), _zero(), "Not applicable", "Work location has no state.")
    if state.casefold() == "odisha" and month >= ODISHA_PT_REPEALED:
        return _pt_row(employee, employee.wages, _zero(), _zero(), _zero(), "Not applicable", ODISHA_PT_REASON)
    if employee.stored_amount is not None:
        amount = _money(employee.stored_amount)
        return _pt_row(employee, employee.wages, amount, _zero(), amount, "Calculated", None)
    rule = _rule_on(rules, ends, employee.state_id, month)
    if rule is None:
        return _pt_row(
            employee,
            employee.wages,
            None,
            None,
            None,
            "Not calculated",
            f"No professional tax rule is saved for {state} for this month.",
        )
    if employee.wages is None:
        return _pt_row(
            employee,
            None,
            None,
            None,
            None,
            "Not calculated",
            f"Payroll wages are not available for {state} for this month.",
        )
    amount = _slab_amount(employee.wages, rule.slab_json)
    if amount is None:
        return _pt_row(
            employee,
            employee.wages,
            None,
            None,
            None,
            "Not calculated",
            f"Professional tax slabs are not saved for {state}.",
        )
    deducted = _money(amount)
    return _pt_row(employee, _money(employee.wages), deducted, _zero(), deducted, "Calculated", None)


def _rule_on(
    rules: list[StatutoryConfig], ends: dict[int, date | None], state_id: int, month: date
) -> StatutoryConfig | None:
    start = month_start(month)
    end = month_end(month)
    chosen: StatutoryConfig | None = None
    for rule in rules:
        if not rule.is_active or rule.state_id != state_id or rule.effective_from > end:
            continue
        closes = ends.get(int(rule.id))
        if closes is not None and closes < start:
            continue
        if chosen is None or (rule.effective_from, rule.id) > (chosen.effective_from, chosen.id):
            chosen = rule
    return chosen


def _slab_amount(wages: Decimal, slab_json: str | None) -> Decimal | None:
    if slab_json is None or not slab_json.strip():
        return None
    try:
        rows = json.loads(slab_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(rows, list) or not rows:
        return None
    for row in rows:
        if not isinstance(row, dict) or "amount" not in row:
            return None
        low = Decimal(str(row.get("min", row.get("from", 0))))
        high_raw = row.get("max", row.get("to"))
        high = None if high_raw in (None, "") else Decimal(str(high_raw))
        if wages >= low and (high is None or wages <= high):
            return Decimal(str(row["amount"]))
    return None


def _pt_row(
    employee: PtEmployee,
    wages: Decimal | None,
    employee_amount: Decimal | None,
    employer_amount: Decimal | None,
    total: Decimal | None,
    status: CalculationStatus,
    reason: str | None,
) -> StatutoryContribution:
    return StatutoryContribution(
        employee_id=employee.employee_id,
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        department=employee.department,
        location=employee.state_name,
        applicable_wages=_money(wages) if wages is not None else None,
        employee_contribution=employee_amount,
        employer_contribution=employer_amount,
        total_contribution=total,
        calculation_status=status,
        reason=reason,
    )


def _zero() -> Decimal:
    return Decimal("0.00")


def _money(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _financial_year(month: date) -> str:
    start = month.year if month.month >= 4 else month.year - 1
    return f"{start}-{(start + 1) % 100:02d}"

