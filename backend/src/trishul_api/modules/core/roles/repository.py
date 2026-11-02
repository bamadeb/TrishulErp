from collections.abc import Collection
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import Session

from trishul_api.db.models import AppUser, Permission, Role, RolePermission, UserRole
from trishul_api.modules.core.roles.schemas import PermissionItem, RoleListItem, RoleQuery


def _user_count() -> ColumnElement[int]:
    """Active users holding the role (on any branch)."""
    return (
        select(func.count(func.distinct(UserRole.app_user_id)))
        .join(AppUser, AppUser.id == UserRole.app_user_id)
        .where(UserRole.role_id == Role.id, UserRole.is_active, AppUser.is_active)
        .correlate(Role)
        .scalar_subquery()
    )


def _permission_count() -> ColumnElement[int]:
    return (
        select(func.count(RolePermission.id))
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id == Role.id, RolePermission.is_active, Permission.is_active)
        .correlate(Role)
        .scalar_subquery()
    )


def _list_select() -> Select[*tuple[Any, ...]]:
    """Columns of RoleListItem."""
    return select(
        Role.id,
        Role.code,
        Role.name,
        Role.description,
        Role.is_system,
        Role.is_active,
        _user_count().label("user_count"),
        _permission_count().label("permission_count"),
    )


class RoleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ reads

    def search(self, query: RoleQuery) -> list[RoleListItem]:
        statement = _list_select()
        if query.status != "all":
            statement = statement.where(Role.is_active == (query.status == "active"))
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Role.code.contains(term, autoescape=True),
                    Role.name.contains(term, autoescape=True),
                    Role.description.contains(term, autoescape=True),
                )
            )
        rows = self._session.execute(statement.order_by(Role.name, Role.id)).mappings()
        return [RoleListItem.model_validate(row) for row in rows]

    def get(self, role_id: int) -> Role | None:
        return self._session.get(Role, role_id)

    def detail_row(self, role_id: int) -> dict[str, Any]:
        """One role with every field RoleDetail needs; the role must exist."""
        statement = (
            _list_select().add_columns(Role.created_at, Role.updated_at, Role.row_version).where(Role.id == role_id)
        )
        row = dict(self._session.execute(statement).mappings().one())
        row["permission_codes"] = list(
            self._session.scalars(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role_id, RolePermission.is_active, Permission.is_active)
                .order_by(Permission.code)
            )
        )
        return row

    def permissions(self) -> list[PermissionItem]:
        rows = self._session.execute(
            select(Permission.id, Permission.code, Permission.module, Permission.description)
            .where(Permission.is_active)
            .order_by(Permission.module, Permission.code)
        ).mappings()
        return [PermissionItem.model_validate(row) for row in rows]

    def permission_ids(self, codes: Collection[str]) -> dict[str, int]:
        """Active permissions among `codes`, by code."""
        if not codes:
            return {}
        rows = self._session.execute(
            select(Permission.code, Permission.id).where(Permission.code.in_(codes), Permission.is_active)
        )
        return {code: permission_id for code, permission_id in rows}

    def grants(self, role_id: int) -> list[RolePermission]:
        """Every core.role_permission row of the role, active or not."""
        return list(self._session.scalars(select(RolePermission).where(RolePermission.role_id == role_id)))

    def code_owner(self, code: str) -> int | None:
        """The id of the role holding this code, or None."""
        return self._session.scalar(select(Role.id).where(Role.code == code).limit(1))

    # ------------------------------------------------------------------ writes (committed by the service)

    def add(self, row: object) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()
