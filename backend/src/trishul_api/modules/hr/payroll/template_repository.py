"""Reads and stores salary templates. Assignment rows point at a saved structure."""

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from trishul_api.db.models import (
    AuditLog,
    Department,
    Designation,
    Employee,
    SalaryComponent,
    SalaryStructure,
    SalaryTemplate,
    SalaryTemplateAssignment,
    SalaryTemplateDesignation,
    SalaryTemplateGrade,
    SalaryTemplateLine,
)
from trishul_api.modules.hr.payroll.template_schemas import NamedOption, SalaryTemplateQuery


def _full_name():
    return func.trim(Employee.first_name + " " + func.coalesce(Employee.last_name, ""))


class SalaryTemplateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: SalaryTemplate | SalaryTemplateLine | SalaryTemplateAssignment | object) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()

    def refresh(self, row: SalaryTemplate) -> None:
        self._session.refresh(row)

    def template(self, template_id: int) -> SalaryTemplate | None:
        return self._session.get(SalaryTemplate, template_id)

    def code_taken(self, code: str, ignore_id: int | None) -> bool:
        statement = select(SalaryTemplate.id).where(func.upper(SalaryTemplate.code) == code.upper())
        if ignore_id is not None:
            statement = statement.where(SalaryTemplate.id != ignore_id)
        return self._session.scalar(statement) is not None

    def components(self) -> dict[int, SalaryComponent]:
        rows = self._session.scalars(select(SalaryComponent).where(SalaryComponent.is_active == True))  # noqa: E712
        return {int(row.id): row for row in rows}

    def lines(self, template_id: int) -> list[tuple[SalaryTemplateLine, SalaryComponent]]:
        rows = self._session.execute(
            select(SalaryTemplateLine, SalaryComponent)
            .join(SalaryComponent, SalaryComponent.id == SalaryTemplateLine.salary_component_id)
            .where(
                SalaryTemplateLine.salary_template_id == template_id,
                SalaryTemplateLine.is_active == True,  # noqa: E712
            )
            .order_by(SalaryTemplateLine.display_order, SalaryComponent.code)
        ).all()
        return [(line, component) for line, component in rows]

    def stored_lines(self, template_id: int) -> dict[int, SalaryTemplateLine]:
        rows = self._session.scalars(
            select(SalaryTemplateLine).where(SalaryTemplateLine.salary_template_id == template_id)
        )
        return {int(row.salary_component_id): row for row in rows}

    def counts(self) -> tuple[int, int, int]:
        rows = self._session.execute(
            select(SalaryTemplate.is_active, func.count()).group_by(SalaryTemplate.is_active)
        ).all()
        active = inactive = 0
        for is_active, count in rows:
            if is_active:
                active = int(count)
            else:
                inactive = int(count)
        return active + inactive, active, inactive

    def assigned_employees(self) -> int:
        return int(
            self._session.scalar(
                select(func.count(func.distinct(SalaryTemplateAssignment.employee_id))).where(
                    SalaryTemplateAssignment.is_active == True  # noqa: E712
                )
            )
            or 0
        )

    def departments(self) -> list[NamedOption]:
        rows = self._session.execute(
            select(Department.id, Department.name).where(Department.is_active == True).order_by(Department.name)  # noqa: E712
        ).all()
        return [NamedOption(id=int(row[0]), name=row[1]) for row in rows]

    def designations(self) -> list[NamedOption]:
        rows = self._session.execute(
            select(Designation.id, Designation.name)
            .where(Designation.is_active == True)  # noqa: E712
            .order_by(Designation.name)
        ).all()
        return [NamedOption(id=int(row[0]), name=row[1]) for row in rows]

    def department_exists(self, department_id: int) -> bool:
        return self._session.get(Department, department_id) is not None

    def designation_exists(self, designation_id: int) -> bool:
        return self._session.get(Designation, designation_id) is not None

    def search(self, query: SalaryTemplateQuery) -> tuple[list[tuple], int]:
        assigned = (
            select(
                SalaryTemplateAssignment.salary_template_id.label("template_id"),
                func.count(func.distinct(SalaryTemplateAssignment.employee_id)).label("employees"),
            )
            .where(SalaryTemplateAssignment.is_active == True)  # noqa: E712
            .group_by(SalaryTemplateAssignment.salary_template_id)
            .subquery()
        )
        statement = (
            select(SalaryTemplate, Department.name, Designation.name, func.coalesce(assigned.c.employees, 0))
            .outerjoin(Department, Department.id == SalaryTemplate.department_id)
            .outerjoin(Designation, Designation.id == SalaryTemplate.designation_id)
            .outerjoin(assigned, assigned.c.template_id == SalaryTemplate.id)
        )
        if query.status == "active":
            statement = statement.where(SalaryTemplate.is_active == True)  # noqa: E712
        elif query.status == "inactive":
            statement = statement.where(SalaryTemplate.is_active == False)  # noqa: E712
        if query.department_id is not None:
            statement = statement.where(SalaryTemplate.department_id == query.department_id)
        if query.employee_category is not None:
            statement = statement.where(SalaryTemplate.employee_category == query.employee_category)
        if query.designation_id is not None:
            linked = select(SalaryTemplateDesignation.salary_template_id).where(
                SalaryTemplateDesignation.designation_id == query.designation_id
            )
            statement = statement.where(
                or_(SalaryTemplate.designation_id == query.designation_id, SalaryTemplate.id.in_(linked))
            )
        if query.grade:
            graded = select(SalaryTemplateGrade.salary_template_id).where(SalaryTemplateGrade.grade == query.grade)
            same_grade = select(Designation.id).where(Designation.grade == query.grade)
            statement = statement.where(
                or_(SalaryTemplate.id.in_(graded), SalaryTemplate.designation_id.in_(same_grade))
            )
        if query.search and query.search.strip():
            term = f"%{query.search.strip()}%"
            statement = statement.where(
                or_(
                    SalaryTemplate.code.ilike(term),
                    SalaryTemplate.name.ilike(term),
                    SalaryTemplate.description.ilike(term),
                )
            )
        total = int(self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        rows = self._session.execute(
            statement.order_by(SalaryTemplate.code)
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
        return list(rows), total

    def employees(self, template_id: int) -> list[tuple]:
        rows = self._session.execute(
            select(
                Employee.id,
                Employee.employee_code,
                _full_name(),
                Department.name,
                SalaryStructure.effective_from,
                SalaryStructure.effective_to,
                SalaryStructure.monthly_gross,
            )
            .join(SalaryTemplateAssignment, SalaryTemplateAssignment.employee_id == Employee.id)
            .join(SalaryStructure, SalaryStructure.id == SalaryTemplateAssignment.salary_structure_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .where(
                SalaryTemplateAssignment.salary_template_id == template_id,
                SalaryTemplateAssignment.is_active == True,  # noqa: E712
                SalaryStructure.is_active == True,  # noqa: E712
            )
            .order_by(Employee.employee_code)
        ).all()
        return list(rows)

    def history(self, template_id: int) -> list[tuple]:
        rows = self._session.execute(
            select(AuditLog.action, AuditLog.changed_at, AuditLog.new_values, AuditLog.old_values)
            .where(AuditLog.entity_type == "hr.salary_template", AuditLog.entity_id == template_id)
            .order_by(AuditLog.id.desc())
        ).all()
        return list(rows)

    def links(self, template_ids: list[int]) -> tuple[dict[int, list[int]], dict[int, list[str]]]:
        if not template_ids:
            return {}, {}
        designations: dict[int, list[int]] = {}
        for template_id, designation_id in self._session.execute(
            select(SalaryTemplateDesignation.salary_template_id, SalaryTemplateDesignation.designation_id)
            .where(SalaryTemplateDesignation.salary_template_id.in_(template_ids))
            .order_by(SalaryTemplateDesignation.designation_id)
        ):
            designations.setdefault(int(template_id), []).append(int(designation_id))
        grades: dict[int, list[str]] = {}
        for template_id, grade in self._session.execute(
            select(SalaryTemplateGrade.salary_template_id, SalaryTemplateGrade.grade)
            .where(SalaryTemplateGrade.salary_template_id.in_(template_ids))
            .order_by(SalaryTemplateGrade.grade)
        ):
            grades.setdefault(int(template_id), []).append(grade)
        return designations, grades

    def replace_designations(self, template_id: int, designation_ids: list[int]) -> None:
        self._session.execute(
            delete(SalaryTemplateDesignation).where(SalaryTemplateDesignation.salary_template_id == template_id)
        )
        for designation_id in designation_ids:
            self.add(SalaryTemplateDesignation(salary_template_id=template_id, designation_id=designation_id))

    def replace_grades(self, template_id: int, grades: list[str]) -> None:
        self._session.execute(delete(SalaryTemplateGrade).where(SalaryTemplateGrade.salary_template_id == template_id))
        for grade in grades:
            self.add(SalaryTemplateGrade(salary_template_id=template_id, grade=grade))

    def assignment_for_structure(self, structure_id: int) -> SalaryTemplateAssignment | None:
        return self._session.scalar(
            select(SalaryTemplateAssignment).where(SalaryTemplateAssignment.salary_structure_id == structure_id)
        )
