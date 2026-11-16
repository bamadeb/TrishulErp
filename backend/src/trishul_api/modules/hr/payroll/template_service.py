"""Saves salary templates. A saved employee structure keeps the values it copied."""

import json
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, NotFound
from trishul_api.common.schemas import Page
from trishul_api.db.models import SalaryComponent, SalaryTemplate, SalaryTemplateAssignment, SalaryTemplateLine
from trishul_api.modules.hr.organization.grades import require_grade
from trishul_api.modules.hr.payroll.template_repository import SalaryTemplateRepository
from trishul_api.modules.hr.payroll.template_schemas import (
    SalaryTemplateDetail,
    SalaryTemplateEmployee,
    SalaryTemplateHistoryItem,
    SalaryTemplateLineItem,
    SalaryTemplateLineWrite,
    SalaryTemplateListItem,
    SalaryTemplateQuery,
    SalaryTemplateStatusWrite,
    SalaryTemplateSummary,
    SalaryTemplateWrite,
)

_MONEY = Decimal("0.01")
_HUNDRED = Decimal("100")


class SalaryTemplateService:
    def __init__(self, db: Session) -> None:
        self._repo = SalaryTemplateRepository(db)

    def summary(self) -> SalaryTemplateSummary:
        total, active, inactive = self._repo.counts()
        return SalaryTemplateSummary(
            total=total,
            active=active,
            inactive=inactive,
            assigned_employees=self._repo.assigned_employees(),
            departments=self._repo.departments(),
            designations=self._repo.designations(),
        )

    def list_templates(self, query: SalaryTemplateQuery) -> Page[SalaryTemplateListItem]:
        rows, total = self._repo.search(query)
        designation_ids, grades = self._repo.links([int(template.id) for template, *_rest in rows])
        items = []
        for template, department, designation, assigned in rows:
            chosen = designation_ids.get(int(template.id)) or _single(template.designation_id)
            items.append(
                _list_item(template, department, designation, int(assigned)).model_copy(
                    update={"designation_ids": chosen, "grades": grades.get(int(template.id), [])}
                )
            )
        return Page(items=items, total=total, page=query.page, page_size=query.page_size)

    def get_template(self, template_id: int) -> SalaryTemplateDetail:
        template = self._require(template_id)
        return self._detail(template)

    def create(self, actor: CurrentUser, data: SalaryTemplateWrite) -> SalaryTemplateDetail:
        self._check(data, None)
        template = SalaryTemplate(
            code=data.code.upper(),
            name=data.name,
            description=data.description,
            template_type=data.template_type,
            employee_category=data.employee_category,
            department_id=data.department_id,
            designation_id=data.designation_id,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            is_active=data.is_active,
            created_by_user_id=actor.id,
        )
        self._repo.add(template)
        self._repo.flush()
        self._write_coverage(int(template.id), data)
        self._write_lines(actor, int(template.id), data.lines)
        self._repo.commit()
        self._repo.refresh(template)
        return self._detail(template)

    def update(
        self, actor: CurrentUser, template_id: int, expected: bytes, data: SalaryTemplateWrite
    ) -> SalaryTemplateDetail:
        template = self._require(template_id)
        check_row_version(template.row_version, expected)
        self._check(data, template_id)
        template.code = data.code.upper()
        template.name = data.name
        template.description = data.description
        template.template_type = data.template_type
        template.employee_category = data.employee_category
        template.department_id = data.department_id
        template.designation_id = data.designation_id
        template.effective_from = data.effective_from
        template.effective_to = data.effective_to
        template.is_active = data.is_active
        template.updated_by_user_id = actor.id
        self._write_coverage(template_id, data)
        self._write_lines(actor, template_id, data.lines)
        self._repo.commit()
        self._repo.refresh(template)
        return self._detail(template)

    def set_status(
        self, actor: CurrentUser, template_id: int, expected: bytes, data: SalaryTemplateStatusWrite
    ) -> SalaryTemplateDetail:
        template = self._require(template_id)
        check_row_version(template.row_version, expected)
        template.is_active = data.is_active
        template.updated_by_user_id = actor.id
        self._repo.commit()
        self._repo.refresh(template)
        return self._detail(template)

    def _write_coverage(self, template_id: int, data: SalaryTemplateWrite) -> None:
        sent_designations = "designation_ids" in data.model_fields_set or "designation_id" in data.model_fields_set
        if sent_designations:
            chosen = _ids(data)
            self._repo.replace_designations(template_id, chosen)
            template = self._repo.template(template_id)
            if template is not None:
                template.designation_id = chosen[0] if chosen else None
        if "grades" in data.model_fields_set:
            self._repo.replace_grades(template_id, list(dict.fromkeys(data.grades)))

    def _require(self, template_id: int) -> SalaryTemplate:
        template = self._repo.template(template_id)
        if template is None:
            raise NotFound("Salary template not found.")
        return template

    def _check(self, data: SalaryTemplateWrite, ignore_id: int | None) -> None:
        if self._repo.code_taken(data.code, ignore_id):
            raise ApiError("That template code is already used.", errors={"code": ["Choose another code."]})
        if data.department_id is not None and not self._repo.department_exists(data.department_id):
            raise ApiError("Choose a saved department.", errors={"departmentId": ["That department was not found."]})
        if data.designation_id is not None and not self._repo.designation_exists(data.designation_id):
            raise ApiError("Choose a saved designation.", errors={"designationId": ["That designation was not found."]})
        for designation_id in _ids(data):
            if not self._repo.designation_exists(designation_id):
                raise ApiError(
                    "Choose a saved designation.",
                    errors={"designationIds": ["That designation was not found."]},
                )
        for grade in data.grades:
            require_grade(grade, field="grades")
        if not data.lines:
            raise ApiError("Select at least one salary component.", errors={"lines": ["Select a component."]})
        components = self._repo.components()
        seen: set[int] = set()
        for line in data.lines:
            if line.salary_component_id in seen:
                raise ApiError(
                    "Each component can be added once.",
                    errors={"lines": ["Remove the duplicate component."]},
                )
            seen.add(line.salary_component_id)
            component = components.get(line.salary_component_id)
            if component is None:
                raise ApiError(
                    "Choose an active salary component.",
                    errors={"lines": ["That component is not active."]},
                )
            _require_value(component, line)

    def _write_lines(self, actor: CurrentUser, template_id: int, lines: list[SalaryTemplateLineWrite]) -> None:
        components = self._repo.components()
        stored = self._repo.stored_lines(template_id)
        chosen = {line.salary_component_id for line in lines}
        for component_id, row in stored.items():
            if component_id not in chosen:
                row.is_active = False
                row.updated_by_user_id = actor.id
        for line in lines:
            component = components[line.salary_component_id]
            amount = line.monthly_amount if component.calculation_type == "Fixed Amount" else None
            percentage = line.percentage if component.calculation_type == "Percentage" else None
            formula = line.formula if component.calculation_type == "Formula" else None
            order = line.display_order or int(component.display_order or 0)
            current = stored.get(line.salary_component_id)
            if current is None:
                self._repo.add(
                    SalaryTemplateLine(
                        salary_template_id=template_id,
                        salary_component_id=line.salary_component_id,
                        monthly_amount=amount,
                        percentage=percentage,
                        formula=formula,
                        display_order=order,
                        is_active=True,
                        created_by_user_id=actor.id,
                    )
                )
                continue
            current.monthly_amount = amount
            current.percentage = percentage
            current.formula = formula
            current.display_order = order
            current.is_active = True
            current.updated_by_user_id = actor.id

    def _detail(self, template: SalaryTemplate) -> SalaryTemplateDetail:
        pairs = self._repo.lines(int(template.id))
        estimated = _estimate(pairs)
        department = next((item.name for item in self._repo.departments() if item.id == template.department_id), None)
        designation = next(
            (item.name for item in self._repo.designations() if item.id == template.designation_id), None
        )
        assigned = len({int(row[0]) for row in self._repo.employees(int(template.id))})
        listed = _list_item(template, department, designation, assigned)
        designation_ids, grades = self._repo.links([int(template.id)])
        chosen = designation_ids.get(int(template.id)) or _single(template.designation_id)
        return SalaryTemplateDetail(
            id=listed.id,
            code=listed.code,
            name=listed.name,
            description=listed.description,
            employee_category=listed.employee_category,
            department=listed.department,
            designation=listed.designation,
            assigned_employees=listed.assigned_employees,
            is_active=listed.is_active,
            designation_ids=chosen,
            grades=grades.get(int(template.id), []),
            row_version=template.row_version,
            template_type="Monthly",
            department_id=template.department_id,
            designation_id=template.designation_id,
            effective_from=template.effective_from,
            effective_to=template.effective_to,
            monthly_gross=estimated.gross,
            employee_deductions=estimated.deductions,
            net_salary=estimated.net,
            employer_contribution=estimated.employer,
            annual_ctc=estimated.annual,
            lines=estimated.lines,
            employees=[
                SalaryTemplateEmployee(
                    employee_id=int(row[0]),
                    employee_code=row[1],
                    full_name=row[2],
                    department=row[3],
                    effective_from=row[4],
                    effective_to=row[5],
                    monthly_gross=row[6],
                )
                for row in self._repo.employees(int(template.id))
            ],
            history=[
                _history(action, changed_at, new_values, old_values)
                for action, changed_at, new_values, old_values in self._repo.history(int(template.id))
            ],
        )


def record_template_assignment(
    session: Session, structure_id: int, employee_id: int, template_id: int | None, user_id: int
) -> None:
    """Point this structure at a template. Existing structure lines are left as saved."""
    repo = SalaryTemplateRepository(session)
    if template_id is not None:
        template = repo.template(template_id)
        if template is None or not template.is_active:
            raise ApiError(
                "Choose an active salary template.",
                errors={"salaryTemplateId": ["That template is not active."]},
            )
    current = repo.assignment_for_structure(structure_id)
    if template_id is None:
        if current is not None:
            current.is_active = False
            current.updated_by_user_id = user_id
        return
    if current is None:
        repo.add(
            SalaryTemplateAssignment(
                salary_template_id=template_id,
                salary_structure_id=structure_id,
                employee_id=employee_id,
                is_active=True,
                created_by_user_id=user_id,
            )
        )
        return
    current.salary_template_id = template_id
    current.employee_id = employee_id
    current.is_active = True
    current.updated_by_user_id = user_id


class _Estimate:
    def __init__(self) -> None:
        self.gross = Decimal("0.00")
        self.deductions = Decimal("0.00")
        self.net = Decimal("0.00")
        self.employer = Decimal("0.00")
        self.annual = Decimal("0.00")
        self.lines: list[SalaryTemplateLineItem] = []


def _estimate(pairs: list[tuple[SalaryTemplateLine, SalaryComponent]]) -> _Estimate:
    basic = Decimal("0.00")
    for line, component in pairs:
        if component.code == "BASIC" and line.monthly_amount is not None:
            basic = line.monthly_amount
    result = _Estimate()
    for line, component in pairs:
        amount = _amount(line, component, basic)
        if amount is not None and component.component_type == "Earning" and component.include_in_gross:
            result.gross += amount
        if amount is not None and component.component_type == "Employee Deduction" and component.include_in_net_pay:
            result.deductions += amount
        if amount is not None and component.include_in_net_pay and component.component_type == "Earning":
            result.net += amount
        if amount is not None and component.include_in_net_pay and component.component_type == "Employee Deduction":
            result.net -= amount
        if amount is not None and component.component_type == "Employer Contribution":
            result.employer += amount
        result.lines.append(
            SalaryTemplateLineItem(
                salary_component_id=int(component.id),
                code=component.code,
                name=component.name,
                component_type=component.component_type,
                calculation_method=component.calculation_type,
                calculation_basis=component.calculation_basis,
                monthly_amount=line.monthly_amount,
                percentage=line.percentage,
                formula=line.formula,
                display_order=int(line.display_order or 0),
                estimated_amount=amount,
            )
        )
    result.gross = _money(result.gross)
    result.deductions = _money(result.deductions)
    result.net = _money(result.net)
    result.employer = _money(result.employer)
    result.annual = _money(result.gross * 12)
    return result


def _amount(line: SalaryTemplateLine, component: SalaryComponent, basic: Decimal) -> Decimal | None:
    if component.calculation_type == "Fixed Amount" and line.monthly_amount is not None:
        return _money(line.monthly_amount)
    if (
        component.calculation_type == "Percentage"
        and component.calculation_basis == "Basic Salary"
        and line.percentage is not None
    ):
        return _money(basic * line.percentage / _HUNDRED)
    return None


def _require_value(component: SalaryComponent, line: SalaryTemplateLineWrite) -> None:
    if component.calculation_type == "Fixed Amount" and line.monthly_amount is None:
        raise ApiError(
            f"Enter the monthly amount for {component.code}.",
            errors={"lines": [f"{component.code} needs a monthly amount."]},
        )
    if component.calculation_type == "Percentage" and line.percentage is None:
        raise ApiError(
            f"Enter the percentage for {component.code}.",
            errors={"lines": [f"{component.code} needs a percentage."]},
        )
    if component.calculation_type == "Formula" and not line.formula:
        raise ApiError(
            f"Enter the formula for {component.code}.",
            errors={"lines": [f"{component.code} needs a formula."]},
        )


def _list_item(
    template: SalaryTemplate, department: str | None, designation: str | None, assigned: int
) -> SalaryTemplateListItem:
    return SalaryTemplateListItem(
        id=int(template.id),
        code=template.code,
        name=template.name,
        description=template.description,
        employee_category=template.employee_category,
        department=department,
        designation=designation,
        assigned_employees=assigned,
        is_active=bool(template.is_active),
        row_version=template.row_version,
    )


def _history(
    action: str, changed_at: object, new_values: str | None, old_values: str | None
) -> SalaryTemplateHistoryItem:
    payload = new_values or old_values or "{}"
    try:
        saved = json.loads(payload)
    except json.JSONDecodeError:
        saved = {}
    name = saved.get("name") or saved.get("code") or action
    when = changed_at.date() if isinstance(changed_at, datetime) else changed_at
    return SalaryTemplateHistoryItem(action=action, changed_at=when, changed_by=None, summary=str(name))


def _single(designation_id: int | None) -> list[int]:
    return [int(designation_id)] if designation_id else []


def _ids(data: SalaryTemplateWrite) -> list[int]:
    source = data.designation_ids or _single(data.designation_id)
    chosen: list[int] = []
    for designation_id in source:
        if designation_id not in chosen:
            chosen.append(designation_id)
    return chosen


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)
