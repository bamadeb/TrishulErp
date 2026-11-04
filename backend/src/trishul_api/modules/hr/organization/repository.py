"""Reads and writes the existing organization tables. No new tables are mapped here."""

from typing import Any, cast

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import Session, aliased

from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import Branch, Company, Department, Designation, Employee, State
from trishul_api.modules.hr.organization.schemas import (
    BranchListItem,
    CompanyListItem,
    DepartmentListItem,
    DesignationListItem,
    GradeDesignation,
    GradeDetail,
    GradeListItem,
    HierarchyListItem,
    OrganizationQuery,
)

_PARENT = aliased(Department)
_HEAD = aliased(Employee)
_MANAGER = aliased(Employee)
_REPORT = aliased(Employee)

_COMPANY_NAME: ColumnElement[str] = func.coalesce(Company.trade_name, Company.legal_name)


def _person_name(person: Any) -> ColumnElement[str]:
    return func.concat_ws(" ", person.first_name, person.last_name)


def _employee_count(match: ColumnElement[bool]) -> ColumnElement[int]:
    return (
        select(func.count(Employee.id))
        .where(Employee.is_active == True, match)  # noqa: E712  SQL Server rejects "IS 1"
        .scalar_subquery()
    )


def _active(status: str, column: Any) -> Any:
    if status == "all":
        return None
    return column == (status == "active")


class OrganizationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search_departments(self, query: OrganizationQuery) -> Page[DepartmentListItem]:
        statement = self._filter_department(self._department_select(), query)
        statement = order_by_sort(
            statement, query.sort, _DEPARTMENT_SORT, default="name", tiebreaker=Department.id.asc()
        )
        return paginate(self._session, statement, query, DepartmentListItem)

    def department(self, department_id: int) -> dict[str, Any] | None:
        row = self._session.execute(
            self._department_select(detail=True).where(Department.id == department_id)
        ).mappings().first()
        return dict(row) if row else None

    def department_code_owner(self, code: str) -> int | None:
        return self._session.scalar(select(Department.id).where(Department.code == code).limit(1))

    def search_designations(self, query: OrganizationQuery) -> Page[DesignationListItem]:
        statement = self._filter_designation(self._designation_select(), query)
        statement = order_by_sort(
            statement, query.sort, _DESIGNATION_SORT, default="name", tiebreaker=Designation.id.asc()
        )
        return paginate(self._session, statement, query, DesignationListItem)

    def designation(self, designation_id: int) -> dict[str, Any] | None:
        row = self._session.execute(
            self._designation_select(detail=True).where(Designation.id == designation_id)
        ).mappings().first()
        return dict(row) if row else None

    def designation_code_owner(self, code: str) -> int | None:
        return self._session.scalar(select(Designation.id).where(Designation.code == code).limit(1))

    def search_grades(self, query: OrganizationQuery) -> Page[GradeListItem]:
        statement = self._grade_select()
        if (active := _active(query.status, Designation.is_active)) is not None:
            statement = statement.where(active)
        if query.search:
            statement = statement.where(Designation.grade.contains(query.search.strip(), autoescape=True))
        statement = statement.group_by(Designation.grade).order_by(Designation.grade.asc())
        return paginate(self._session, statement, query, GradeListItem)

    def grade(self, grade: str) -> GradeDetail | None:
        summary = self._session.execute(
            self._grade_select().where(Designation.grade == grade).group_by(Designation.grade)
        ).mappings().first()
        if summary is None:
            return None
        rows = self._session.execute(
            select(
                Designation.id,
                Designation.code,
                Designation.name,
                Designation.department_id,
                Department.name.label("department_name"),
                _employee_count(Employee.designation_id == Designation.id).label("employee_count"),
                Designation.is_active,
                Designation.row_version,
            )
            .outerjoin(Department, Department.id == Designation.department_id)
            .where(Designation.grade == grade)
            .order_by(Designation.name)
        ).mappings()
        return GradeDetail(
            grade=summary["grade"],
            designation_count=summary["designation_count"],
            employee_count=summary["employee_count"],
            designations=[GradeDesignation.model_validate(row) for row in rows],
        )

    def search_branches(self, query: OrganizationQuery) -> Page[BranchListItem]:
        statement = self._filter_branch(self._branch_select(), query)
        statement = order_by_sort(statement, query.sort, _BRANCH_SORT, default="name", tiebreaker=Branch.id.asc())
        return paginate(self._session, statement, query, BranchListItem)

    def branch(self, branch_id: int) -> dict[str, Any] | None:
        row = self._session.execute(self._branch_select(detail=True).where(Branch.id == branch_id)).mappings().first()
        return dict(row) if row else None

    def branch_code_owner(self, code: str) -> int | None:
        return self._session.scalar(select(Branch.id).where(Branch.code == code).limit(1))

    def search_companies(self, query: OrganizationQuery) -> Page[CompanyListItem]:
        statement = self._filter_company(self._company_select(), query)
        statement = order_by_sort(
            statement, query.sort, _COMPANY_SORT, default="legalName", tiebreaker=Company.id.asc()
        )
        return paginate(self._session, statement, query, CompanyListItem)

    def company(self, company_id: int) -> dict[str, Any] | None:
        row = self._session.execute(
            self._company_select(detail=True).where(Company.id == company_id)
        ).mappings().first()
        return dict(row) if row else None

    def company_code_owner(self, code: str) -> int | None:
        return self._session.scalar(select(Company.id).where(Company.code == code).limit(1))

    def search_hierarchy(self, query: OrganizationQuery) -> Page[HierarchyListItem]:
        statement = self._filter_hierarchy(self._hierarchy_select(), query)
        statement = order_by_sort(
            statement, query.sort, _HIERARCHY_SORT, default="employeeCode", tiebreaker=Employee.id.asc()
        )
        return paginate(self._session, statement, query, HierarchyListItem)

    def hierarchy_member(self, employee_id: int) -> dict[str, Any] | None:
        row = self._session.execute(
            self._hierarchy_select(detail=True).where(Employee.id == employee_id)
        ).mappings().first()
        return dict(row) if row else None

    def manager_of(self, employee_id: int) -> int | None:
        return self._session.scalar(select(Employee.reporting_manager_id).where(Employee.id == employee_id))

    def get(self, model: type[Any], row_id: int) -> Any | None:
        return self._session.get(model, row_id)

    def missing(self, model: type[Any], ids: set[int], *, active: bool = True) -> set[int]:
        wanted = {row_id for row_id in ids if row_id is not None}
        if not wanted:
            return set()
        statement = select(model.id).where(model.id.in_(wanted))
        if active and hasattr(model, "is_active"):
            statement = statement.where(model.is_active == True)  # noqa: E712
        return wanted - set(self._session.scalars(statement))

    def add(self, row: object) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()

    def rename_grade(self, current: str, new: str, *, updated_at: Any, updated_by_user_id: int) -> int:
        rows = self._session.scalars(select(Designation).where(Designation.grade == current)).all()
        for row in rows:
            row.grade = new
            row.updated_at = updated_at
            row.updated_by_user_id = updated_by_user_id
        return len(rows)

    def _department_select(self, *, detail: bool = False) -> Select[Any]:
        columns: list[Any] = [
            Department.id,
            Department.code,
            Department.name,
            Department.parent_department_id,
            _PARENT.name.label("parent_department_name"),
            Department.head_employee_id,
            _person_name(_HEAD).label("head_name"),
            _employee_count(Employee.department_id == Department.id).label("employee_count"),
            Department.is_active,
            Department.created_at,
        ]
        if detail:
            columns.extend([Department.updated_at, Department.row_version])
        return (
            select(*columns)
            .outerjoin(_PARENT, _PARENT.id == Department.parent_department_id)
            .outerjoin(_HEAD, _HEAD.id == Department.head_employee_id)
        )

    def _filter_department(self, statement: Select[Any], query: OrganizationQuery) -> Select[Any]:
        if (active := _active(query.status, Department.is_active)) is not None:
            statement = statement.where(active)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(Department.code.contains(term, autoescape=True), Department.name.contains(term, autoescape=True))
            )
        return statement

    def _designation_select(self, *, detail: bool = False) -> Select[Any]:
        columns: list[Any] = [
            Designation.id,
            Designation.code,
            Designation.name,
            Designation.grade,
            Designation.department_id,
            Department.name.label("department_name"),
            _employee_count(Employee.designation_id == Designation.id).label("employee_count"),
            Designation.is_active,
            Designation.created_at,
        ]
        if detail:
            columns.extend([Designation.updated_at, Designation.row_version])
        return select(*columns).outerjoin(Department, Department.id == Designation.department_id)

    def _filter_designation(self, statement: Select[Any], query: OrganizationQuery) -> Select[Any]:
        if (active := _active(query.status, Designation.is_active)) is not None:
            statement = statement.where(active)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Designation.code.contains(term, autoescape=True),
                    Designation.name.contains(term, autoescape=True),
                    Designation.grade.contains(term, autoescape=True),
                )
            )
        return statement

    def _grade_select(self) -> Select[Any]:
        return cast(
            Select[Any],
            select(
                Designation.grade.label("grade"),
                func.count(func.distinct(Designation.id)).label("designation_count"),
                func.count(Employee.id).label("employee_count"),
            )
            .outerjoin(
                Employee,
                (Employee.designation_id == Designation.id) & (Employee.is_active == True),  # noqa: E712
            )
            .where(Designation.grade.is_not(None), Designation.grade != "")
        )

    def _branch_select(self, *, detail: bool = False) -> Select[Any]:
        parent = aliased(Branch)
        columns: list[Any] = [
            Branch.id,
            Branch.code,
            Branch.name,
            Branch.branch_type,
            Branch.company_id,
            _COMPANY_NAME.label("company_name"),
            Branch.state_id,
            State.name.label("state_name"),
            _employee_count(Employee.branch_id == Branch.id).label("employee_count"),
            Branch.is_active,
            Branch.created_at,
        ]
        statement = select(*columns).outerjoin(Company, Company.id == Branch.company_id).outerjoin(
            State, State.id == Branch.state_id
        )
        if detail:
            statement = statement.add_columns(
                Branch.parent_warehouse_id,
                parent.name.label("parent_warehouse_name"),
                Branch.address,
                Branch.district_id,
                Branch.pincode_id,
                Branch.gstin_registration_id,
                Branch.phone,
                Branch.email,
                Branch.latitude,
                Branch.longitude,
                Branch.updated_at,
                Branch.row_version,
            ).outerjoin(parent, parent.id == Branch.parent_warehouse_id)
        return statement

    def _filter_branch(self, statement: Select[Any], query: OrganizationQuery) -> Select[Any]:
        if (active := _active(query.status, Branch.is_active)) is not None:
            statement = statement.where(active)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(Branch.code.contains(term, autoescape=True), Branch.name.contains(term, autoescape=True))
            )
        return statement

    def _company_select(self, *, detail: bool = False) -> Select[Any]:
        columns: list[Any] = [
            Company.id,
            Company.code,
            Company.legal_name,
            Company.trade_name,
            Company.state_id,
            State.name.label("state_name"),
            _employee_count(Employee.company_id == Company.id).label("employee_count"),
            Company.is_active,
            Company.created_at,
        ]
        if detail:
            columns.extend(
                [
                    Company.pan,
                    Company.cin,
                    Company.address,
                    Company.logo_url,
                    Company.fiscal_year_start_month,
                    Company.updated_at,
                    Company.row_version,
                ]
            )
        return select(*columns).outerjoin(State, State.id == Company.state_id)

    def _filter_company(self, statement: Select[Any], query: OrganizationQuery) -> Select[Any]:
        if (active := _active(query.status, Company.is_active)) is not None:
            statement = statement.where(active)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Company.code.contains(term, autoescape=True),
                    Company.legal_name.contains(term, autoescape=True),
                    Company.trade_name.contains(term, autoescape=True),
                )
            )
        return statement

    def _hierarchy_select(self, *, detail: bool = False) -> Select[Any]:
        columns: list[Any] = [
            Employee.id,
            Employee.employee_code,
            Employee.first_name,
            Employee.last_name,
            Employee.department_id,
            Department.name.label("department_name"),
            Employee.designation_id,
            Designation.name.label("designation_name"),
            Designation.grade,
            Employee.company_id,
            _COMPANY_NAME.label("company_name"),
            Employee.branch_id,
            Branch.name.label("branch_name"),
            Employee.reporting_manager_id,
            _MANAGER.employee_code.label("reporting_manager_code"),
            _person_name(_MANAGER).label("reporting_manager_name"),
            (
                select(func.count(_REPORT.id))
                .where(_REPORT.reporting_manager_id == Employee.id, _REPORT.is_active == True)  # noqa: E712
                .correlate(Employee)
                .scalar_subquery()
            ).label("direct_report_count"),
            Employee.status,
            Employee.is_active,
            Employee.created_at,
        ]
        if detail:
            columns.extend([Employee.updated_at, Employee.row_version])
        return (
            select(*columns)
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(Designation, Designation.id == Employee.designation_id)
            .outerjoin(Company, Company.id == Employee.company_id)
            .outerjoin(Branch, Branch.id == Employee.branch_id)
            .outerjoin(_MANAGER, _MANAGER.id == Employee.reporting_manager_id)
        )

    def _filter_hierarchy(self, statement: Select[Any], query: OrganizationQuery) -> Select[Any]:
        if (active := _active(query.status, Employee.is_active)) is not None:
            statement = statement.where(active)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Employee.employee_code.contains(term, autoescape=True),
                    Employee.first_name.contains(term, autoescape=True),
                    Employee.last_name.contains(term, autoescape=True),
                    _person_name(_MANAGER).contains(term, autoescape=True),
                )
            )
        return statement


_DEPARTMENT_SORT: SortColumns = {
    "code": Department.code,
    "name": Department.name,
    "createdAt": Department.created_at,
    "employeeCount": _employee_count(Employee.department_id == Department.id),
}
_DESIGNATION_SORT: SortColumns = {
    "code": Designation.code,
    "name": Designation.name,
    "grade": Designation.grade,
    "createdAt": Designation.created_at,
}
_BRANCH_SORT: SortColumns = {"code": Branch.code, "name": Branch.name, "createdAt": Branch.created_at}
_COMPANY_SORT: SortColumns = {
    "code": Company.code,
    "legalName": Company.legal_name,
    "createdAt": Company.created_at,
}
_HIERARCHY_SORT: SortColumns = {
    "employeeCode": Employee.employee_code,
    "firstName": Employee.first_name,
    "createdAt": Employee.created_at,
}
