"""Queries for the signed-in user. core tables are not filtered by row-level security."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth.access import RoleGrant
from trishul_api.auth.tokens import Identity
from trishul_api.db.models import (
    AppUser,
    Branch,
    Employee,
    Permission,
    Role,
    RolePermission,
    UserPrincipalAccess,
    UserRole,
)


@dataclass(frozen=True)
class Account:
    id: int
    employee_id: int | None
    username: str
    email: str | None
    default_branch_id: int | None
    display_name: str


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def account(self, identity: Identity) -> Account | None:
        """The active, unlocked app user for this sign-in identity."""
        query = (
            select(AppUser, Employee.first_name, Employee.last_name)
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .where(AppUser.is_active, ~AppUser.is_locked)
        )
        if identity.cognito_sub:
            query = query.where(AppUser.cognito_sub == identity.cognito_sub)
        else:
            query = query.where(AppUser.username == identity.username)
        row = self._session.execute(query).first()
        if row is None:
            return None
        user, first_name, last_name = row
        return Account(
            id=user.id,
            employee_id=user.employee_id,
            username=user.username,
            email=user.email,
            default_branch_id=user.default_branch_id,
            display_name=" ".join(part for part in (first_name, last_name) if part) or user.username,
        )

    def role_grants(self, user_id: int) -> list[RoleGrant]:
        rows = self._session.execute(
            select(Role.code, UserRole.branch_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.app_user_id == user_id, UserRole.is_active, Role.is_active)
        )
        return [RoleGrant(role=code, branch_id=branch_id) for code, branch_id in rows]

    def permissions(self, user_id: int) -> frozenset[str]:
        return frozenset(
            self._session.scalars(
                select(Permission.code)
                .distinct()
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .join(UserRole, UserRole.role_id == RolePermission.role_id)
                .where(
                    UserRole.app_user_id == user_id,
                    UserRole.is_active,
                    RolePermission.is_active,
                    Permission.is_active,
                )
            )
        )

    def principal_ids(self, user_id: int) -> frozenset[int]:
        return frozenset(
            self._session.scalars(
                select(UserPrincipalAccess.principal_id).where(
                    UserPrincipalAccess.app_user_id == user_id, UserPrincipalAccess.is_active
                )
            )
        )

    def branches_served_by(self, warehouse_ids: frozenset[int]) -> frozenset[int]:
        return frozenset(
            self._session.scalars(
                select(Branch.id).where(Branch.parent_warehouse_id.in_(warehouse_ids), Branch.is_active)
            )
        )
