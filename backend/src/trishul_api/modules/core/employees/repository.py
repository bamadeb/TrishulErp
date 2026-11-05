from collections.abc import Collection
from typing import Any

from sqlalchemy import ColumnElement, Select, case, false, func, or_, select, true
from sqlalchemy.orm import Session, aliased

from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.db.models import (
    AppUser,
    Attachment,
    Branch,
    Company,
    Department,
    Designation,
    Employee,
    EmployeeProfile,
    EmploymentHistory,
)
from trishul_api.modules.core.employees.schemas import (
    CompanyOption,
    DepartmentOption,
    DesignationOption,
    EmployeeCounts,
    EmployeeDirectoryPage,
    EmployeeLifecycle,
    EmployeeListItem,
    EmployeeQuery,
    EmploymentEvent,
)

_FULL_NAME: ColumnElement[str] = func.concat_ws(" ", Employee.first_name, Employee.last_name)
_COMPANY_NAME: ColumnElement[str | None] = func.coalesce(Company.trade_name, Company.legal_name)

_SORT_COLUMNS: SortColumns = {
    "employeeCode": Employee.employee_code,
    "firstName": Employee.first_name,
    "fullName": Employee.first_name,
    "lastName": Employee.last_name,
    "mobile": Employee.mobile,
    "email": Employee.email,
    "branch": Branch.name,
    "department": Department.name,
    "designation": Designation.name,
    "grade": Designation.grade,
    "employeeType": Employee.employee_type,
    "type": Employee.employee_type,
    "status": Employee.status,
    "dateOfJoining": Employee.date_of_joining,
    "createdAt": Employee.created_at,
}


def _confirmation_date() -> ColumnElement[Any]:
    """Latest Confirmed event. The date lives on hr.employment_history, not on the employee."""
    return (
        select(EmploymentHistory.effective_date)
        .where(
            EmploymentHistory.employee_id == Employee.id,
            EmploymentHistory.event_type == "Confirmed",
            EmploymentHistory.is_active == True,  # noqa: E712  SQL Server rejects "IS 1"
        )
        .order_by(EmploymentHistory.effective_date.desc())
        .limit(1)
        .scalar_subquery()
    )


def _list_select() -> Select[*tuple[Any, ...]]:
    """Columns of EmployeeListItem: the employee plus branch, company, department, designation, profile and login."""
    manager = aliased(Employee)
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
            _COMPANY_NAME.label("company_name"),
            Employee.department_id,
            Department.name.label("department"),
            Employee.designation_id,
            Designation.name.label("designation"),
            Designation.grade.label("grade"),
            Employee.employee_type,
            Employee.status,
            Employee.is_active,
            Employee.date_of_joining,
            _confirmation_date().label("confirmation_date"),
            func.concat_ws(" ", manager.first_name, manager.last_name).label("reporting_manager_name"),
            EmployeeProfile.gender,
            EmployeeProfile.date_of_birth,
            AppUser.id.label("user_id"),
            Employee.created_at,
        )
        .outerjoin(Branch, Branch.id == Employee.branch_id)
        .outerjoin(Company, Company.id == Employee.company_id)
        .outerjoin(Department, Department.id == Employee.department_id)
        .outerjoin(Designation, Designation.id == Employee.designation_id)
        .outerjoin(manager, manager.id == Employee.reporting_manager_id)
        .outerjoin(EmployeeProfile, EmployeeProfile.employee_id == Employee.id)
        .outerjoin(AppUser, AppUser.employee_id == Employee.id)
    )


def _lifecycle_clause(lifecycle: EmployeeLifecycle) -> ColumnElement[bool]:
    """Card filter. Archived is is_active = 0. Probation is not stored, so that card is empty."""
    if lifecycle == "active":
        return Employee.is_active == True  # noqa: E712
    if lifecycle == "archived":
        return Employee.is_active == False  # noqa: E712
    if lifecycle == "notice":
        return Employee.status == "Notice"
    if lifecycle == "exited":
        return Employee.status == "Exited"
    if lifecycle == "probation":
        return false()
    return true()


def _narrow(statement: Select[Any], query: EmployeeQuery, *, apply_lifecycle: bool) -> Select[Any]:
    if apply_lifecycle and query.lifecycle is not None:
        statement = statement.where(_lifecycle_clause(query.lifecycle))
    elif apply_lifecycle and query.status != "all":
        statement = statement.where(Employee.is_active == (query.status == "active"))
    if query.branch_id is not None:
        statement = statement.where(Employee.branch_id == query.branch_id)
    if query.department_id is not None:
        statement = statement.where(Employee.department_id == query.department_id)
    if query.designation_id is not None:
        statement = statement.where(Employee.designation_id == query.designation_id)
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
    return statement


def _count_value(condition: ColumnElement[bool]) -> ColumnElement[int]:
    return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)


class EmployeeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ reads

    def search(self, query: EmployeeQuery) -> EmployeeDirectoryPage:
        statement = _narrow(_list_select(), query, apply_lifecycle=True)
        statement = order_by_sort(
            statement, query.sort, _SORT_COLUMNS, default="firstName", tiebreaker=Employee.id.asc()
        )
        page = paginate(self._session, statement, query, EmployeeListItem)
        return EmployeeDirectoryPage(
            items=page.items,
            total=page.total,
            page=page.page,
            page_size=page.page_size,
            counts=self._counts(query),
        )

    def _counts(self, query: EmployeeQuery) -> EmployeeCounts:
        """Card totals for the same search and dropdowns, ignoring the selected card."""
        statement = _narrow(
            select(
                func.count().label("all_employees"),
                _count_value(Employee.is_active == True).label("active"),  # noqa: E712
                _count_value(Employee.status == "Notice").label("notice"),
                _count_value(Employee.status == "Exited").label("exited"),
                _count_value(Employee.is_active == False).label("archived"),  # noqa: E712
            ).select_from(Employee),
            query,
            apply_lifecycle=False,
        )
        row = self._session.execute(statement).mappings().one()
        return EmployeeCounts(
            all_employees=row["all_employees"],
            active=row["active"],
            probation=0,
            notice=row["notice"],
            exited=row["exited"],
            archived=row["archived"],
        )

    def get(self, employee_id: int) -> Employee | None:
        return self._session.get(Employee, employee_id)

    def profile(self, employee_id: int) -> EmployeeProfile | None:
        return self._session.scalar(select(EmployeeProfile).where(EmployeeProfile.employee_id == employee_id).limit(1))

    def latest_photo(self, employee_id: int) -> Attachment | None:
        return self._session.scalar(
            select(Attachment)
            .where(
                Attachment.entity_type == "core.employee",
                Attachment.entity_id == employee_id,
                Attachment.category == "Photo",
                Attachment.is_active == True,  # noqa: E712
            )
            .order_by(Attachment.id.desc())
            .limit(1)
        )

    def retire_photos(self, employee_id: int) -> None:
        rows = self._session.scalars(
            select(Attachment).where(
                Attachment.entity_type == "core.employee",
                Attachment.entity_id == employee_id,
                Attachment.category == "Photo",
                Attachment.is_active == True,  # noqa: E712
            )
        )
        for row in rows:
            row.is_active = False

    def detail_row(self, employee_id: int) -> dict[str, Any]:
        """One employee with every field EmployeeDetail needs; the employee must exist."""
        statement = (
            _list_select()
            .add_columns(
                Employee.company_id,
                Employee.reporting_manager_id,
                Employee.date_of_exit,
                Employee.mobile_platform,
                EmployeeProfile.personal_email,
                EmployeeProfile.current_address,
                EmployeeProfile.permanent_address,
                EmployeeProfile.emergency_contact_name,
                EmployeeProfile.emergency_contact_phone,
                Employee.row_version,
            )
            .where(Employee.id == employee_id)
        )
        return dict(self._session.execute(statement).mappings().one())

    def employment_history(self, employee_id: int) -> list[EmploymentEvent]:
        rows = self._session.execute(
            select(
                EmploymentHistory.id,
                EmploymentHistory.event_type,
                EmploymentHistory.effective_date,
                EmploymentHistory.remarks,
            )
            .where(EmploymentHistory.employee_id == employee_id, EmploymentHistory.is_active == True)  # noqa: E712
            .order_by(EmploymentHistory.effective_date.desc(), EmploymentHistory.id.desc())
        ).mappings()
        return [EmploymentEvent.model_validate(row) for row in rows]

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
