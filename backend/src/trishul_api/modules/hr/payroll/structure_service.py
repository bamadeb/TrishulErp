"""Saves salary structures. A later effective date is a new record; the earlier one stays."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, NotFound
from trishul_api.common.schemas import Page
from trishul_api.db.models import SalaryComponent, SalaryStructure, SalaryStructureLine
from trishul_api.modules.hr.payroll.service import _safe_formula
from trishul_api.modules.hr.payroll.structure_repository import SalaryStructureRepository
from trishul_api.modules.hr.payroll.structure_schemas import (
    SalaryStructureDetail,
    SalaryStructureLineWrite,
    SalaryStructureListItem,
    SalaryStructureQuery,
    SalaryStructureSummary,
    SalaryStructureWrite,
)


class SalaryStructureService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = SalaryStructureRepository(db)

    def summary(self) -> SalaryStructureSummary:
        return self._repo.summary()

    def list_structures(self, query: SalaryStructureQuery) -> Page[SalaryStructureListItem]:
        return self._repo.search(query)

    def get_structure(self, employee_id: int) -> SalaryStructureDetail:
        detail = self._repo.detail(employee_id)
        if detail is None:
            raise NotFound("Employee not found.")
        return detail

    def save_structure(
        self, actor: CurrentUser, employee_id: int, expected: bytes | None, data: SalaryStructureWrite
    ) -> SalaryStructureDetail:
        if self._repo.employee(employee_id) is None:
            raise NotFound("Employee not found.")
        if data.effective_to is not None and data.effective_to <= data.effective_from:
            raise ApiError(
                "Effective to must be later than effective from.",
                errors={"effectiveTo": ["Choose a later date."]},
            )
        current = self._repo.current(employee_id)
        if current is None and expected is not None:
            raise ApiError("This employee does not have a salary structure yet.")
        if current is not None:
            if expected is None:
                raise ApiError("Reload this structure before saving. It already exists.")
            check_row_version(current.row_version, expected)
        components = {int(row.id): row for row in self._repo.components()}
        chosen = _chosen(data.lines, components)
        if current is not None and data.effective_from != current.effective_from:
            current = self._revise(actor, current, data.effective_from)
        _reject_overlap(self._repo.active_structures(employee_id), data.effective_from, data.effective_to, current)
        if current is None:
            current = SalaryStructure(
                employee_id=employee_id,
                effective_from=data.effective_from,
                effective_to=data.effective_to,
                annual_ctc=data.annual_ctc,
                monthly_gross=data.monthly_gross,
                is_active=True,
                created_by_user_id=actor.id,
            )
            self._repo.add(current)
            self._repo.flush()
        else:
            current.effective_to = data.effective_to
            current.annual_ctc = data.annual_ctc
            current.monthly_gross = data.monthly_gross
            current.updated_by_user_id = actor.id
            self._repo.replace_lines(int(current.id))
        for component_id, line in chosen:
            self._repo.add(_line(actor, int(current.id), components[component_id], line))
        self._repo.commit()
        return self.get_structure(employee_id)

    def _revise(self, actor: CurrentUser, current: SalaryStructure, starts: date) -> SalaryStructure:
        if starts <= current.effective_from:
            raise ApiError(
                "A revised structure starts after the current effective from.",
                errors={"effectiveFrom": ["Choose a later date. The current structure is kept."]},
            )
        closing = starts - timedelta(days=1)
        if current.effective_to is None or current.effective_to >= starts:
            if closing < current.effective_from:
                raise ApiError(
                    "The previous structure cannot be closed before it starts.",
                    errors={"effectiveFrom": ["Choose a later date."]},
                )
            current.effective_to = closing
            current.updated_by_user_id = actor.id
        revised = SalaryStructure(
            employee_id=current.employee_id,
            effective_from=starts,
            effective_to=None,
            annual_ctc=current.annual_ctc,
            monthly_gross=current.monthly_gross,
            is_active=True,
            created_by_user_id=actor.id,
        )
        self._repo.add(revised)
        self._repo.flush()
        return revised


def _reject_overlap(
    structures: list[SalaryStructure], start: date, end: date | None, current: SalaryStructure | None
) -> None:
    for structure in structures:
        if current is not None and structure.id == current.id:
            continue
        if _ranges_overlap(start, end, structure.effective_from, structure.effective_to):
            raise ApiError(
                "Another salary structure already covers this period.",
                errors={"effectiveFrom": ["Choose dates that do not overlap the saved structures."]},
            )


def _ranges_overlap(start: date, end: date | None, other_start: date, other_end: date | None) -> bool:
    latest_start = max(start, other_start)
    earliest_end = min(end or date.max, other_end or date.max)
    return latest_start <= earliest_end


def _chosen(
    lines: list[SalaryStructureLineWrite], components: dict[int, SalaryComponent]
) -> list[tuple[int, SalaryStructureLineWrite]]:
    seen: set[int] = set()
    chosen: list[tuple[int, SalaryStructureLineWrite]] = []
    for line in lines:
        if not line.included:
            continue
        if line.salary_component_id in seen:
            raise ApiError(
                "A component can be included once.",
                errors={"lines": ["Remove the duplicate component."]},
            )
        if line.salary_component_id not in components:
            raise ApiError(
                "Choose a saved, active salary component.",
                errors={"lines": ["That component is not available."]},
            )
        seen.add(line.salary_component_id)
        chosen.append((line.salary_component_id, line))
    return chosen


def _line(
    actor: CurrentUser, structure_id: int, component: SalaryComponent, line: SalaryStructureLineWrite
) -> SalaryStructureLine:
    amount: Decimal | None
    percentage: Decimal | None
    formula: str | None
    method = component.calculation_type
    if method == "Fixed Amount":
        amount, percentage, formula = line.monthly_amount, None, None
    elif method == "Percentage":
        amount, percentage, formula = None, line.percentage, None
    elif method == "Formula":
        if line.formula is not None:
            _safe_formula(line.formula)
        amount, percentage, formula = None, None, line.formula
    else:
        amount, percentage, formula = None, None, None
    return SalaryStructureLine(
        salary_structure_id=structure_id,
        salary_component_id=int(component.id),
        monthly_amount=amount,
        percentage=percentage,
        formula=formula,
        is_active=True,
        created_by_user_id=actor.id,
    )
