"""Salary component master. Statutory rates stay in hr.statutory_config."""

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, Conflict, NotFound
from trishul_api.common.schemas import Page
from trishul_api.db.models import SalaryComponent, SalaryComponentRevision
from trishul_api.modules.hr.payroll.repository import SalaryComponentRepository
from trishul_api.modules.hr.payroll.schemas import (
    CalculationBasis,
    CalculationMethod,
    SalaryComponentDetail,
    SalaryComponentListItem,
    SalaryComponentQuery,
    SalaryComponentStatus,
    SalaryComponentSummary,
    SalaryComponentUpdate,
    SalaryComponentWrite,
)

_BASIS: dict[CalculationMethod, set[CalculationBasis]] = {
    "Fixed Amount": {"Fixed Monthly Amount", "Attendance / Effective Workdays"},
    "Percentage": {"Basic Salary", "Gross Earnings", "Eligible PF Wages", "Eligible ESI Wages"},
    "Formula": {
        "Basic Salary",
        "Gross Earnings",
        "Eligible PF Wages",
        "Eligible ESI Wages",
        "Attendance / Effective Workdays",
        "Custom Formula",
    },
    "Manual Entry": set(),
}
_RULES = (
    "calculation_type",
    "calculation_basis",
    "fixed_amount",
    "percentage",
    "formula",
    "is_prorated",
    "is_taxable",
    "is_pf_wage",
    "is_esi_wage",
    "include_in_gross",
    "include_in_net_pay",
    "allow_reversal",
    "allow_manual_override",
    "effective_from",
    "effective_to",
)

_FORMULA = re.compile(r"^[A-Za-z0-9_+\-*/().,\s]+$")
_FORMULA_WORDS = re.compile(r"\b(IMPORT|EVAL|EXEC|OPEN|SELECT|DROP|INSERT|UPDATE|DELETE)\b", re.I)


class SalaryComponentService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = SalaryComponentRepository(db)

    def list_components(self, query: SalaryComponentQuery) -> Page[SalaryComponentListItem]:
        return self._repo.search(query)

    def summary(self) -> SalaryComponentSummary:
        return self._repo.summary()

    def get_component(self, component_id: int) -> SalaryComponentDetail:
        row = self._repo.get(component_id)
        if row is None:
            raise NotFound("Salary component not found.")
        in_use, rules_locked = self._repo.usage(component_id)
        row["in_use"] = in_use
        row["rules_locked"] = rules_locked
        row["created_by"] = self._repo.user_name(row.pop("created_by_user_id", None))
        row["updated_by"] = self._repo.user_name(row.pop("updated_by_user_id", None))
        row["revisions"] = self._repo.revisions(component_id)
        row["audit"] = self._repo.audit(component_id)
        return SalaryComponentDetail.model_validate(row)

    def create_component(self, actor: CurrentUser, data: SalaryComponentWrite) -> SalaryComponentDetail:
        self._unique(data.code, None)
        values = _configuration(data.model_dump())
        row = SalaryComponent(
            code=data.code,
            name=data.name,
            component_type=data.component_type,
            description=data.description,
            display_order=data.display_order,
            is_active=data.is_active,
            display_in_statement=data.display_in_statement,
            display_in_payslip=data.display_in_payslip,
            created_by_user_id=actor.id,
            **values,
        )
        return self.get_component(self._save(row))

    def update_component(
        self, actor: CurrentUser, component_id: int, expected: bytes, data: SalaryComponentUpdate
    ) -> SalaryComponentDetail:
        row = self._model(component_id)
        check_row_version(row.row_version, expected)
        if "code" in data.model_fields_set and data.code and data.code != row.code:
            self._unique(data.code, component_id)
        proposed = _proposed(row, data)
        in_use, rules_locked = self._repo.usage(component_id)
        if in_use and (proposed["code"] != row.code or proposed["component_type"] != row.component_type):
            raise Conflict(
                "This component is used by a salary structure or a payslip. Its code and type stay as they are."
            )
        if rules_locked and _rules_changed(row, proposed):
            raise Conflict(
                "This component is used in processed payroll. Its calculation rules stay as they were."
            )
        if _rules_changed(row, proposed):
            self._revise(row, actor)
        _apply(row, proposed)
        self._touch(row, actor)
        self._save(row)
        return self.get_component(component_id)

    def set_status(
        self, actor: CurrentUser, component_id: int, expected: bytes, data: SalaryComponentStatus
    ) -> SalaryComponentDetail:
        row = self._model(component_id)
        check_row_version(row.row_version, expected)
        row.is_active = data.is_active
        self._touch(row, actor)
        self._save(row)
        return self.get_component(component_id)

    def _model(self, component_id: int) -> SalaryComponent:
        row = self._repo.model(component_id)
        if row is None:
            raise NotFound("Salary component not found.")
        return row

    def _unique(self, code: str, current_id: int | None) -> None:
        owner = self._repo.code_owner(code)
        if owner is not None and owner != current_id:
            raise AlreadyExists(f"Component code '{code}' is already in use.")

    def _revise(self, row: SalaryComponent, actor: CurrentUser) -> None:
        self._repo.add(
            SalaryComponentRevision(
                salary_component_id=row.id,
                revision_no=self._repo.next_revision(row.id),
                code=row.code,
                name=row.name,
                component_type=row.component_type,
                calculation_type=row.calculation_type,
                calculation_basis=row.calculation_basis,
                fixed_amount=row.fixed_amount,
                percentage=row.percentage,
                formula=row.formula,
                is_prorated=row.is_prorated,
                is_taxable=row.is_taxable,
                is_pf_wage=row.is_pf_wage,
                is_esi_wage=row.is_esi_wage,
                include_in_gross=row.include_in_gross,
                include_in_net_pay=row.include_in_net_pay,
                allow_reversal=row.allow_reversal,
                allow_manual_override=row.allow_manual_override,
                display_in_statement=row.display_in_statement,
                display_in_payslip=row.display_in_payslip,
                display_order=row.display_order,
                effective_from=row.effective_from,
                effective_to=row.effective_to,
                is_active=row.is_active,
                created_by_user_id=actor.id,
            )
        )

    def _touch(self, row: SalaryComponent, actor: CurrentUser) -> None:
        row.updated_at = datetime.now(UTC).replace(tzinfo=None)
        row.updated_by_user_id = actor.id

    def _save(self, row: SalaryComponent) -> int:
        self._repo.add(row)
        try:
            self._repo.flush()
            row_id = int(row.id)
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists("Salary component could not be saved. The code may already be in use.") from error
        return row_id


def _configuration(values: dict[str, Any]) -> dict[str, Any]:
    method: CalculationMethod = values["calculation_method"]
    basis: CalculationBasis | None = values.get("calculation_basis")
    allowed = _BASIS[method]
    if method == "Manual Entry":
        if basis is not None:
            raise ApiError(
                "Manual entry does not use a calculation basis.",
                errors={"calculationBasis": ["Leave the basis empty."]},
            )
        basis = None
    elif basis not in allowed:
        raise ApiError(
            "That basis does not match the calculation method.",
            errors={"calculationBasis": ["Choose a basis for this method."]},
        )
    fixed = values.get("fixed_amount") if method == "Fixed Amount" else None
    percentage = values.get("percentage") if method == "Percentage" else None
    formula = values.get("formula") if method == "Formula" else None
    if formula is not None:
        _safe_formula(formula)
    manual = True if method == "Manual Entry" else bool(values.get("allow_manual_override"))
    start: date = values["effective_from"]
    end: date | None = values.get("effective_to")
    if end is not None and end < start:
        raise ApiError(
            "Effective to cannot be earlier than effective from.",
            errors={"effectiveTo": ["Choose the same date or a later one."]},
        )
    include_gross = bool(values.get("include_in_gross"))
    include_net = bool(values.get("include_in_net_pay"))
    component_type = values.get("component_type")
    if component_type == "Employer Contribution":
        include_net = False
    if component_type == "Informational":
        include_gross = False
        include_net = False
    return {
        "calculation_type": method,
        "calculation_basis": basis,
        "fixed_amount": fixed,
        "percentage": percentage,
        "formula": formula,
        "is_prorated": bool(values.get("is_prorated")),
        "allow_manual_override": manual,
        "include_in_gross": include_gross,
        "is_taxable": bool(values.get("is_taxable")),
        "is_pf_wage": bool(values.get("is_pf_applicable")),
        "is_esi_wage": bool(values.get("is_esi_applicable")),
        "include_in_net_pay": include_net,
        "allow_reversal": bool(values.get("allow_reversal")),
        "effective_from": start,
        "effective_to": end,
    }


def _safe_formula(formula: str) -> None:
    if not _FORMULA.fullmatch(formula) or _FORMULA_WORDS.search(formula):
        raise ApiError(
            "The formula can use numbers, component names, + - * /, parentheses, and MIN, MAX or ROUND.",
            errors={"formula": ["Remove anything else from the formula."]},
        )


def _proposed(row: SalaryComponent, data: SalaryComponentUpdate) -> dict[str, Any]:
    current: dict[str, Any] = {
        "code": row.code,
        "name": row.name,
        "component_type": row.component_type,
        "description": row.description,
        "display_order": row.display_order,
        "is_active": row.is_active,
        "display_in_statement": row.display_in_statement,
        "display_in_payslip": row.display_in_payslip,
        "calculation_method": row.calculation_type,
        "calculation_basis": row.calculation_basis,
        "fixed_amount": row.fixed_amount,
        "percentage": row.percentage,
        "formula": row.formula,
        "is_prorated": row.is_prorated,
        "allow_manual_override": row.allow_manual_override,
        "include_in_gross": row.include_in_gross,
        "is_taxable": row.is_taxable,
        "is_pf_applicable": row.is_pf_wage,
        "is_esi_applicable": row.is_esi_wage,
        "include_in_net_pay": row.include_in_net_pay,
        "allow_reversal": row.allow_reversal,
        "effective_from": row.effective_from,
        "effective_to": row.effective_to,
    }
    for field in data.model_fields_set:
        current[field] = getattr(data, field)
    rules = _configuration(current)
    current.update(rules)
    return current


def _rules_changed(row: SalaryComponent, proposed: dict[str, Any]) -> bool:
    return any(not _same(getattr(row, field), proposed[field]) for field in _RULES)


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, Decimal) or isinstance(right, Decimal):
        if left is None or right is None:
            return left is None and right is None
        return Decimal(left) == Decimal(right)
    return left == right


def _apply(row: SalaryComponent, proposed: dict[str, Any]) -> None:
    row.code = proposed["code"]
    row.name = proposed["name"]
    row.component_type = proposed["component_type"]
    row.description = proposed["description"]
    row.display_order = proposed["display_order"]
    row.is_active = proposed["is_active"]
    row.display_in_statement = proposed["display_in_statement"]
    row.display_in_payslip = proposed["display_in_payslip"]
    for field in _RULES:
        setattr(row, field, proposed[field])
