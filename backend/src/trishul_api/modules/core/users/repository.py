from collections import defaultdict
from collections.abc import Collection
from typing import Any

from sqlalchemy import ColumnElement, Select, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Branch,
    Department,
    Designation,
    Employee,
    Principal,
    Role,
    UserPrincipalAccess,
    UserRole,
)
from trishul_api.modules.core.users.schemas import (
    EmployeeOption,
    EmployeeOptionQuery,
    RoleGrant,
    RoleOption,
    UserListItem,
    UserQuery,
)

# Employee name when linked, else the sign-in name.
_DISPLAY_NAME: ColumnElement[str] = func.coalesce(
    func.nullif(func.concat_ws(" ", Employee.first_name, Employee.last_name), ""), AppUser.username
)
_PHONE: ColumnElement[str | None] = func.coalesce(AppUser.mobile, Employee.mobile)

_SORT_COLUMNS: SortColumns = {
    "username": AppUser.username,
    "displayName": _DISPLAY_NAME,
    "employeeCode": Employee.employee_code,
    "firstName": Employee.first_name,
    "lastName": Employee.last_name,
    "createdAt": AppUser.created_at,
}


def _user_select() -> Select[*tuple[Any, ...]]:
    """Columns of UserListItem (except roles): the user and, when linked, their employee record."""
    return (
        select(
            AppUser.id,
            AppUser.username,
            AppUser.email,
            AppUser.mobile,
            _PHONE.label("phone"),
            _DISPLAY_NAME.label("display_name"),
            AppUser.employee_id,
            Employee.employee_code,
            Employee.first_name,
            Employee.last_name,
            Designation.name.label("designation"),
            Department.name.label("department"),
            AppUser.is_active,
            AppUser.is_locked,
            AppUser.created_at,
        )
        .outerjoin(Employee, Employee.id == AppUser.employee_id)
        .outerjoin(Designation, Designation.id == Employee.designation_id)
        .outerjoin(Department, Department.id == Employee.department_id)
    )


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ reads

    def search(self, query: UserQuery) -> Page[UserListItem]:
        page = paginate(self._session, self.list_statement(query), query, UserListItem)
        grants = self.grants_by_user([item.id for item in page.items])
        for item in page.items:
            item.roles = grants.get(item.id, [])
        return page

    @staticmethod
    def list_statement(query: UserQuery) -> Select[*tuple[Any, ...]]:
        statement = _user_select()
        if query.status != "all":
            statement = statement.where(AppUser.is_active == (query.status == "active"))
        if query.role_id is not None:
            statement = statement.where(
                exists().where(UserRole.app_user_id == AppUser.id, UserRole.role_id == query.role_id)
            )
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    AppUser.username.contains(term, autoescape=True),
                    AppUser.email.contains(term, autoescape=True),
                    _PHONE.contains(term, autoescape=True),
                    _DISPLAY_NAME.contains(term, autoescape=True),
                    Employee.employee_code.contains(term, autoescape=True),
                )
            )
        return order_by_sort(statement, query.sort, _SORT_COLUMNS, default="username", tiebreaker=AppUser.id.asc())

    def get(self, user_id: int) -> AppUser | None:
        return self._session.get(AppUser, user_id)

    def list_item(self, user_id: int) -> UserListItem:
        """One user as the list shows it; the user must exist."""
        row = self._session.execute(_user_select().where(AppUser.id == user_id)).mappings().one()
        return UserListItem.model_validate(row)

    def employee_options(self, query: EmployeeOptionQuery) -> list[EmployeeOption]:
        """Active employees for the user form's picker, matching the search, with the user each is linked to."""
        linked = aliased(AppUser)
        statement = (
            select(
                Employee.id,
                Employee.employee_code,
                Employee.first_name,
                Employee.last_name,
                Employee.mobile,
                Employee.email,
                Designation.name.label("designation"),
                Department.name.label("department"),
                Branch.name.label("branch_name"),
                linked.id.label("linked_user_id"),
            )
            .outerjoin(Designation, Designation.id == Employee.designation_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(Branch, Branch.id == Employee.branch_id)
            .outerjoin(linked, linked.employee_id == Employee.id)
            .where(Employee.is_active)
        )
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Employee.employee_code.contains(term, autoescape=True),
                    func.concat_ws(" ", Employee.first_name, Employee.last_name).contains(term, autoescape=True),
                    Employee.mobile.contains(term, autoescape=True),
                    Employee.email.contains(term, autoescape=True),
                )
            )
        statement = statement.order_by(Employee.first_name, Employee.last_name, Employee.id).limit(query.limit)
        return [EmployeeOption.model_validate(row) for row in self._session.execute(statement).mappings()]

    def grants_by_user(self, user_ids: Collection[int]) -> dict[int, list[RoleGrant]]:
        """Role grants for many users in one query (not one per user)."""
        if not user_ids:
            return {}
        rows = self._session.execute(
            select(
                UserRole.app_user_id,
                Role.id.label("role_id"),
                Role.code.label("role_code"),
                Role.name.label("role_name"),
                UserRole.branch_id,
                Branch.name.label("branch_name"),
            )
            .join(Role, Role.id == UserRole.role_id)
            .outerjoin(Branch, Branch.id == UserRole.branch_id)
            .where(UserRole.app_user_id.in_(user_ids), UserRole.is_active)
            .order_by(Role.name, Branch.name)
        ).mappings()
        grants: dict[int, list[RoleGrant]] = defaultdict(list)
        for row in rows:
            grants[row["app_user_id"]].append(RoleGrant.model_validate(row))
        return grants

    def role_rows(self, user_id: int) -> list[UserRole]:
        return list(self._session.scalars(select(UserRole).where(UserRole.app_user_id == user_id)))

    def principal_rows(self, user_id: int) -> list[UserPrincipalAccess]:
        return list(
            self._session.scalars(select(UserPrincipalAccess).where(UserPrincipalAccess.app_user_id == user_id))
        )

    def roles(self) -> list[RoleOption]:
        rows = self._session.execute(
            select(Role.id, Role.code, Role.name, Role.description).where(Role.is_active).order_by(Role.name)
        ).mappings()
        return [RoleOption.model_validate(row) for row in rows]

    # ------------------------------------------------------------------ checks

    def username_exists(self, username: str) -> bool:
        # select(...).limit(1), not select(exists()): SQL Server has no SELECT EXISTS(...) scalar form.
        return self._session.scalar(select(AppUser.id).where(AppUser.username == username).limit(1)) is not None

    def subject_in_use(self, subject: str) -> bool:
        return self._session.scalar(select(AppUser.id).where(AppUser.cognito_sub == subject).limit(1)) is not None

    def employee_is_active(self, employee_id: int) -> bool:
        return (
            self._session.scalar(select(Employee.id).where(Employee.id == employee_id, Employee.is_active).limit(1))
            is not None
        )

    def user_linked_to(self, employee_id: int) -> AppUser | None:
        return self._session.scalar(select(AppUser).where(AppUser.employee_id == employee_id))

    def missing_roles(self, ids: Collection[int]) -> set[int]:
        found = self._session.scalars(select(Role.id).where(Role.id.in_(ids), Role.is_active))
        return set(ids) - set(found)

    def missing_branches(self, ids: Collection[int]) -> set[int]:
        found = self._session.scalars(select(Branch.id).where(Branch.id.in_(ids), Branch.is_active))
        return set(ids) - set(found)

    def missing_principals(self, ids: Collection[int]) -> set[int]:
        found = self._session.scalars(select(Principal.id).where(Principal.id.in_(ids), Principal.is_active))
        return set(ids) - set(found)

    # ------------------------------------------------------------------ writes (committed by the service)

    def add(self, row: object) -> None:
        self._session.add(row)

    def delete(self, row: object) -> None:
        self._session.delete(row)

    def flush(self) -> None:
        self._session.flush()
