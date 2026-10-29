from collections.abc import Collection
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import Session, aliased

from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import AppUser, Branch, Company, Department, Designation, Employee
from trishul_api.modules.core.employees.schemas import (
    CompanyOption,
    DepartmentOption,
    DesignationOption,
    EmployeeListItem,
    EmployeeQuery,
)

_FULL_NAME: ColumnElement[str] = func.concat_ws(" ", Employee.first_name, Employee.last_name)
_COMPANY_NAME: ColumnElement[str | None] = func.coalesce(Company.trade_name, Company.legal_name)

_SORT_COLUMNS: SortColumns = {
    "employeeCode": Employee.employee_code,
    "firstName": Employee.first_name,
    "lastName": Employee.last_name,
    "status": Employee.status,
    "createdAt": Employee.created_at,
}


def _list_select() -> Select[*tuple[Any, ...]]:
    """Columns of EmployeeListItem: the employee plus its branch, department, designation and linked login."""
    return (
        select(
            Employee.id,
            Employee.employee_code,
            Employee.first_name,
            Employee.last_name,
            Employee.mobile,
            Employee.email,
            Employee.branch_id,
            Branch.name.label("branch_name"),
            Employee.department_id,
            Department.name.label("department"),
            Employee.designation_id,
            Designation.name.label("designation"),
            Employee.employee_type,
            Employee.status,
            Employee.is_active,
            AppUser.id.label("user_id"),
            Employee.created_at,
        )
        .outerjoin(Branch, Branch.id == Employee.branch_id)
        .outerjoin(Department, Department.id == Employee.department_id)
        .outerjoin(Designation, Designation.id == Employee.designation_id)
        .outerjoin(AppUser, AppUser.employee_id == Employee.id)
    )


class EmployeeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ reads

    def search(self, query: EmployeeQuery) -> Page[EmployeeListItem]:
        statement = _list_select()
        if query.status != "all":
            statement = statement.where(Employee.is_active == (query.status == "active"))
        if query.branch_id is not None:
            statement = statement.where(Employee.branch_id == query.branch_id)
        if query.department_id is not None:
            statement = statement.where(Employee.department_id == query.department_id)
        if query.employee_type is not None:
            statement = statement.where(Employee.employee_type == query.employee_type)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Employee.employee_code.contains(term, autoescape=True),
                    Employee.mobile.contains(term, autoescape=True),
                    Employee.email.contains(term, autoescape=True),
                    _FULL_NAME.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement, query.sort, _SORT_COLUMNS, default="firstName", tiebreaker=Employee.id.asc()
        )
        return paginate(self._session, statement, query, EmployeeListItem)

    def get(self, employee_id: int) -> Employee | None:
        return self._session.get(Employee, employee_id)

    def detail_row(self, employee_id: int) -> dict[str, Any]:
        """One employee with every field EmployeeDetail needs; the employee must exist."""
        manager = aliased(Employee)
        statement = (
            _list_select()
            .add_columns(
                Employee.company_id,
                _COMPANY_NAME.label("company_name"),
                Employee.reporting_manager_id,
                func.concat_ws(" ", manager.first_name, manager.last_name).label("reporting_manager_name"),
                Employee.date_of_joining,
                Employee.date_of_exit,
                Employee.mobile_platform,
                Employee.row_version,
            )
            .outerjoin(Company, Company.id == Employee.company_id)
            .outerjoin(manager, manager.id == Employee.reporting_manager_id)
            .where(Employee.id == employee_id)
        )
        return dict(self._session.execute(statement).mappings().one())

    # ------------------------------------------------------------------ option lists (form dropdowns)

    def companies(self) -> list[CompanyOption]:
        rows = self._session.execute(
            select(Company.id, _COMPANY_NAME.label("name")).where(Company.is_active).order_by(_COMPANY_NAME)
        ).mappings()
        return [CompanyOption.model_validate(row) for row in rows]

    def departments(self) -> list[DepartmentOption]:
        rows = self._session.execute(
            select(Department.id, Department.code, Department.name)
            .where(Department.is_active)
            .order_by(Department.name)
        ).mappings()
        return [DepartmentOption.model_validate(row) for row in rows]

    def designations(self) -> list[DesignationOption]:
        rows = self._session.execute(
            select(Designation.id, Designation.code, Designation.name, Designation.department_id)
            .where(Designation.is_active)
            .order_by(Designation.name)
        ).mappings()
        return [DesignationOption.model_validate(row) for row in rows]

    # ------------------------------------------------------------------ checks

    def code_owner(self, employee_code: str) -> int | None:
        """The id of the employee holding this code, or None."""
        return self._session.scalar(select(Employee.id).where(Employee.employee_code == employee_code).limit(1))

    def mobile_owner(self, mobile: str) -> int | None:
        return self._session.scalar(select(Employee.id).where(Employee.mobile == mobile).limit(1))

    def active_login_exists(self, employee_id: int) -> bool:
        return (
            self._session.scalar(
                select(AppUser.id).where(AppUser.employee_id == employee_id, AppUser.is_active).limit(1)
            )
            is not None
        )

    def missing(self, model: type[Any], ids: Collection[int]) -> set[int]:
        """Ids in `ids` that are not active rows of `model`."""
        wanted = {i for i in ids if i is not None}
        if not wanted:
            return set()
        found = self._session.scalars(select(model.id).where(model.id.in_(wanted), model.is_active))
        return wanted - set(found)

    # ------------------------------------------------------------------ writes (committed by the service)

    def add(self, row: object) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()
