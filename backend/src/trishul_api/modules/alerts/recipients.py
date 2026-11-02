"""Who receives an alert: the rule's recipients turned into active users who may see the record.

A role or a named user receives the alert only if they could open the record: the same brand / branch test as
row-level security (rls.fn_can_see). People taken from the record itself (the call's assigned engineer, the
user who logged it) always receive it. The background job's own 'system' account never does.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trishul_api.db.models import AppUser, Branch, Employee, Role, UserPrincipalAccess, UserRole
from trishul_api.modules.alerts.conditions import Candidate

SYSTEM_USERNAME = "system"
_SEE_EVERYTHING = frozenset({"ADMIN", "MANAGEMENT", "ACCOUNTS"})


@dataclass(frozen=True)
class RecipientSpec:
    recipient_type: str
    role_id: int | None = None
    app_user_id: int | None = None


@dataclass
class _Access:
    roles: list[tuple[str, int | None]] = field(default_factory=list)  # (role code, branch scope)
    principals: set[int] = field(default_factory=set)


class RecipientResolver:
    """Resolves recipients for many candidates in one run, caching users' access."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._access: dict[int, _Access] = {}
        self._role_members: dict[int, list[int]] = {}
        self._parent_warehouse: dict[int, int | None] = {}
        self._engineer_users: dict[int, list[int]] = {}

    def resolve(self, specs: Iterable[RecipientSpec], candidate: Candidate) -> set[int]:
        users: set[int] = set()
        checked: set[int] = set()
        for spec in specs:
            if spec.recipient_type == "Role" and spec.role_id is not None:
                checked.update(self._members(spec.role_id))
            elif spec.recipient_type == "User" and spec.app_user_id is not None:
                checked.update(self._usable([spec.app_user_id]))
            elif spec.recipient_type == "Assigned engineer" and candidate.assigned_engineer_id is not None:
                users.update(self._engineer(candidate.assigned_engineer_id))
            elif spec.recipient_type == "Call logged by" and candidate.logged_by_user_id is not None:
                users.update(self._usable([candidate.logged_by_user_id]))
        users.update(u for u in checked if self._can_see(u, candidate.principal_id, candidate.branch_id))
        return users

    def names(self, user_ids: Iterable[int]) -> dict[int, str]:
        ids = list(set(user_ids))
        if not ids:
            return {}
        rows = self._db.execute(
            select(AppUser.id, AppUser.username, Employee.first_name, Employee.last_name)
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .where(AppUser.id.in_(ids))
        )
        return {row.id: " ".join(p for p in (row.first_name, row.last_name) if p) or row.username for row in rows}

    # ------------------------------------------------------------------ helpers

    def _usable(self, user_ids: list[int]) -> list[int]:
        return list(
            self._db.scalars(
                select(AppUser.id).where(
                    AppUser.id.in_(user_ids), AppUser.is_active, ~AppUser.is_locked, AppUser.username != SYSTEM_USERNAME
                )
            )
        )

    def _members(self, role_id: int) -> list[int]:
        if role_id not in self._role_members:
            self._role_members[role_id] = list(
                self._db.scalars(
                    select(AppUser.id)
                    .distinct()
                    .join(UserRole, UserRole.app_user_id == AppUser.id)
                    .join(Role, Role.id == UserRole.role_id)
                    .where(
                        UserRole.role_id == role_id,
                        UserRole.is_active,
                        Role.is_active,
                        AppUser.is_active,
                        ~AppUser.is_locked,
                        AppUser.username != SYSTEM_USERNAME,
                    )
                )
            )
        return self._role_members[role_id]

    def _engineer(self, employee_id: int) -> list[int]:
        if employee_id not in self._engineer_users:
            self._engineer_users[employee_id] = list(
                self._db.scalars(
                    select(AppUser.id).where(AppUser.employee_id == employee_id, AppUser.is_active, ~AppUser.is_locked)
                )
            )
        return self._engineer_users[employee_id]

    def _load_access(self, user_id: int) -> _Access:
        if user_id not in self._access:
            access = _Access()
            for code, branch_id in self._db.execute(
                select(Role.code, UserRole.branch_id)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.app_user_id == user_id, UserRole.is_active, Role.is_active)
            ):
                access.roles.append((code, branch_id))
            access.principals = set(
                self._db.scalars(
                    select(UserPrincipalAccess.principal_id).where(
                        UserPrincipalAccess.app_user_id == user_id, UserPrincipalAccess.is_active
                    )
                )
            )
            self._access[user_id] = access
        return self._access[user_id]

    def _parent(self, branch_id: int) -> int | None:
        if branch_id not in self._parent_warehouse:
            self._parent_warehouse[branch_id] = self._db.scalar(
                select(func.max(Branch.parent_warehouse_id)).where(Branch.id == branch_id)
            )
        return self._parent_warehouse[branch_id]

    def _can_see(self, user_id: int, principal_id: int | None, branch_id: int | None) -> bool:
        """Mirror of rls.fn_can_see for one user and one record."""
        access = self._load_access(user_id)
        if any(code in _SEE_EVERYTHING for code, _ in access.roles):
            return True
        if principal_id is not None and principal_id not in access.principals:
            return False
        if branch_id is None:
            return True
        parent = self._parent(branch_id)
        return any(scope is None or scope in (branch_id, parent) for _, scope in access.roles)
