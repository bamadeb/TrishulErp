"""Reads employees and their current salary structure. Amounts stay on the structure line."""

from typing import Any

from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.orm import Session

from trishul_api.common.paging import order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    Department,
    Designation,
    Employee,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureLine,
)
from trishul_api.modules.hr.payroll.structure_schemas import (
    SalaryStructureDetail,
    SalaryStructureLineItem,
    SalaryStructureListItem,
    SalaryStructureQuery,
    SalaryStructureSummary,
)


def _full_name() -> Any:
    return func.trim(Employee.first_name + literal(" ") + func.coalesce(Employee.last_name, literal(""))).label(
        "full_name"
    )


def _current_structures():
    ranked = (
        select(
            SalaryStructure.id.label("structure_id"),
            SalaryStructure.employee_id.label("employee_id"),
            SalaryStructure.effective_from.label("effective_from"),
            SalaryStructure.effective_to.label("effective_to"),
            SalaryStructure.annual_ctc.label("annual_ctc"),
            SalaryStructure.monthly_gross.label("monthly_gross"),
            SalaryStructure.row_version.label("row_version"),
            func.row_number()
            .over(
                partition_by=SalaryStructure.employee_id,
                order_by=(SalaryStructure.effective_from.desc(), SalaryStructure.id.desc()),
            )
            .label("rn"),
        )
        .where(SalaryStructure.is_active == True)  # noqa: E712
        .subquery()
    )
    return select(ranked).where(ranked.c.rn == 1).subquery()


class SalaryStructureRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def summary(self) -> SalaryStructureSummary:
        current = _current_structures()
        assigned = case((current.c.structure_id.is_not(None), 1), else_=0)
        active = case((Employee.status == "Active", 1), else_=0)
        total, assigned_count, active_count = self._session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(assigned), 0),
                func.coalesce(func.sum(active), 0),
            )
            .select_from(Employee)
            .outerjoin(current, current.c.employee_id == Employee.id)
        ).one()
        employees = int(total or 0)
        assigned_total = int(assigned_count or 0)
        return SalaryStructureSummary(
            employees=employees,
            assigned=assigned_total,
            unassigned=employees - assigned_total,
            active=int(active_count or 0),
        )

    def search(self, query: SalaryStructureQuery) -> Page[SalaryStructureListItem]:
        current = _current_structures()
        statement = (
            select(
                Employee.id.label("employee_id"),
                Employee.employee_code,
                _full_name(),
                Department.name.label("department"),
                Designation.name.label("designation"),
                Employee.status,
                current.c.structure_id,
                current.c.effective_from,
                current.c.effective_to,
                current.c.annual_ctc,
                current.c.monthly_gross,
                current.c.row_version,
            )
            .select_from(Employee)
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(Designation, Designation.id == Employee.designation_id)
            .outerjoin(current, current.c.employee_id == Employee.id)
        )
        statement = _filter(statement, current, query)
        statement = order_by_sort(
            statement,
            query.sort,
            {
                "employeeCode": Employee.employee_code,
                "fullName": _full_name(),
                "department": Department.name,
            },
            default="employeeCode",
            tiebreaker=Employee.id.asc(),
        )
        return paginate(self._session, statement, query, SalaryStructureListItem)

    def employee(self, employee_id: int) -> dict[str, Any] | None:
        row = self._session.execute(
            select(
                Employee.id.label("employee_id"),
                Employee.employee_code,
                _full_name(),
                Department.name.label("department"),
                Designation.name.label("designation"),
            )
            .select_from(Employee)
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(Designation, Designation.id == Employee.designation_id)
            .where(Employee.id == employee_id)
        ).mappings().first()
        return dict(row) if row else None

    def current(self, employee_id: int) -> SalaryStructure | None:
        return self._session.scalar(
            select(SalaryStructure)
            .where(SalaryStructure.employee_id == employee_id, SalaryStructure.is_active == True)  # noqa: E712
            .order_by(SalaryStructure.effective_from.desc(), SalaryStructure.id.desc())
            .limit(1)
        )

    def active_structures(self, employee_id: int) -> list[SalaryStructure]:
        return list(
            self._session.scalars(
                select(SalaryStructure)
                .where(SalaryStructure.employee_id == employee_id, SalaryStructure.is_active == True)  # noqa: E712
                .order_by(SalaryStructure.effective_from.asc(), SalaryStructure.id.asc())
            )
        )

    def components(self) -> list[SalaryComponent]:
        return list(
            self._session.scalars(
                select(SalaryComponent)
                .where(SalaryComponent.is_active == True)  # noqa: E712
                .order_by(SalaryComponent.display_order.asc(), SalaryComponent.id.asc())
            )
        )

    def lines_for(self, structure_id: int) -> dict[int, SalaryStructureLine]:
        rows = self._session.scalars(
            select(SalaryStructureLine).where(
                SalaryStructureLine.salary_structure_id == structure_id,
                SalaryStructureLine.is_active == True,  # noqa: E712
            )
        )
        return {int(row.salary_component_id): row for row in rows}

    def detail(self, employee_id: int) -> SalaryStructureDetail | None:
        employee = self.employee(employee_id)
        if employee is None:
            return None
        structure = self.current(employee_id)
        saved = self.lines_for(int(structure.id)) if structure is not None else {}
        lines = [
            SalaryStructureLineItem(
                salary_component_id=int(component.id),
                code=component.code,
                name=component.name,
                component_type=component.component_type,
                calculation_method=component.calculation_type,
                calculation_basis=component.calculation_basis,
                included=int(component.id) in saved,
                monthly_amount=saved[int(component.id)].monthly_amount if int(component.id) in saved else None,
                percentage=saved[int(component.id)].percentage if int(component.id) in saved else None,
                formula=saved[int(component.id)].formula if int(component.id) in saved else None,
                include_in_net_pay=bool(component.include_in_net_pay),
            )
            for component in self.components()
        ]
        employee.update(
            {
                "structure_id": int(structure.id) if structure is not None else None,
                "effective_from": structure.effective_from if structure is not None else None,
                "effective_to": structure.effective_to if structure is not None else None,
                "annual_ctc": structure.annual_ctc if structure is not None else None,
                "monthly_gross": structure.monthly_gross if structure is not None else None,
                "row_version": structure.row_version if structure is not None else None,
                "lines": lines,
            }
        )
        return SalaryStructureDetail.model_validate(employee)

    def add(self, row: SalaryStructure | SalaryStructureLine) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()

    def replace_lines(self, structure_id: int) -> None:
        for line in self.lines_for(structure_id).values():
            self._session.delete(line)

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()


def _filter(statement: Any, current: Any, query: SalaryStructureQuery) -> Any:
    if query.search:
        term = f"%{query.search.strip()}%"
        statement = statement.where(
            or_(
                Employee.employee_code.ilike(term),
                Employee.first_name.ilike(term),
                Employee.last_name.ilike(term),
                Department.name.ilike(term),
                Designation.name.ilike(term),
            )
        )
    if query.assignment == "assigned":
        statement = statement.where(current.c.structure_id.is_not(None))
    elif query.assignment == "unassigned":
        statement = statement.where(current.c.structure_id.is_(None))
    return statement
