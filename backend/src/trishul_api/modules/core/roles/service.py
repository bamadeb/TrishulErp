"""Role management (core.role and core.role_permission): add, rename, choose permissions, activate/deactivate.

A role's code cannot change after it is created. Built-in roles (is_system) cannot be deactivated:
their codes are used by row-level security (rls.fn_can_see, auth.access) and by the alert rules.
ADMIN always keeps core.role.manage, so there is always someone who can undo a mistake here.

core.role_permission rows are switched off rather than deleted (UX_core_role_permission_k1 keeps one
row per role and permission), so the audit log shows who granted or removed what. Users' permissions
are cached for a short time; every change here clears that cache so it applies from the next request.
"""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.auth.users import UserDirectory
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.db.models import Role, RolePermission
from trishul_api.modules.core.roles.repository import RoleRepository
from trishul_api.modules.core.roles.schemas import RoleCreate, RoleDetail, RoleUpdate

ADMIN_ROLE = "ADMIN"
# Permissions the ADMIN role never loses.
ADMIN_KEEPS = frozenset({"core.role.manage"})
_DUPLICATE = "Another role already has this code."


class RoleService:
    def __init__(self, db: Session, directory: UserDirectory) -> None:
        self._db = db
        self._repo = RoleRepository(db)
        self._directory = directory

    def get(self, role_id: int) -> RoleDetail:
        self._require(role_id)
        return self._detail(role_id)

    def create(self, actor: CurrentUser, data: RoleCreate) -> RoleDetail:
        code = data.code.strip()
        owner = self._repo.code_owner(code)
        if owner is not None:
            raise AlreadyExists(f"Role code '{code}' is already in use.")
        permission_ids = self._resolve(data.permission_codes)

        role = Role(
            code=code,
            name=data.name.strip(),
            description=_clean(data.description),
            is_system=False,
            created_by_user_id=actor.id,
        )
        self._repo.add(role)
        try:
            self._repo.flush()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists(_DUPLICATE) from error
        for permission_id in permission_ids.values():
            self._repo.add(RolePermission(role_id=role.id, permission_id=permission_id, created_by_user_id=actor.id))
        role_id = role.id
        self._db.commit()
        return self._detail(role_id)

    def update(self, actor: CurrentUser, role_id: int, expected_row_version: bytes, data: RoleUpdate) -> RoleDetail:
        role = self._require(role_id)
        check_row_version(role.row_version, expected_row_version)
        changed = data.model_fields_set

        if "name" in changed and data.name:
            role.name = data.name.strip()
        if "description" in changed:
            role.description = _clean(data.description)
        if "permission_codes" in changed and data.permission_codes is not None:
            codes = set(data.permission_codes)
            if role.code == ADMIN_ROLE and not codes >= ADMIN_KEEPS:
                raise ApiError(
                    "The Administrator role must keep permission to manage roles.",
                    errors={"permissionCodes": [f"Keep {', '.join(sorted(ADMIN_KEEPS))}"]},
                )
            self._set_permissions(role, self._resolve(codes), actor)

        _touch(role, actor)  # also moves row_version, so a stale form can't overwrite the permission list
        self._db.commit()
        self._directory.clear()
        return self._detail(role_id)

    def deactivate(self, actor: CurrentUser, role_id: int) -> RoleDetail:
        role = self._require(role_id)
        if role.is_system:
            raise ApiError("Built-in roles can't be deactivated. Remove their permissions instead.")
        if role.is_active:
            role.is_active = False
            _touch(role, actor)
            self._db.commit()
            self._directory.clear()  # its users lose its permissions now
        return self._detail(role_id)

    def activate(self, actor: CurrentUser, role_id: int) -> RoleDetail:
        role = self._require(role_id)
        if not role.is_active:
            role.is_active = True
            _touch(role, actor)
            self._db.commit()
            self._directory.clear()
        return self._detail(role_id)

    # ------------------------------------------------------------------ helpers

    def _require(self, role_id: int) -> Role:
        role = self._repo.get(role_id)
        if role is None:
            raise NotFound("Role not found.")
        return role

    def _detail(self, role_id: int) -> RoleDetail:
        return RoleDetail.model_validate(self._repo.detail_row(role_id))

    def _resolve(self, codes: set[str] | list[str]) -> dict[str, int]:
        wanted = set(codes)
        found = self._repo.permission_ids(wanted)
        unknown = sorted(wanted - found.keys())
        if unknown:
            raise ApiError(
                "Some permissions don't exist.",
                errors={"permissionCodes": [f"Unknown permission {code}" for code in unknown]},
            )
        return found

    def _set_permissions(self, role: Role, wanted: dict[str, int], actor: CurrentUser) -> None:
        """Make the role grant exactly `wanted`: switch existing rows on or off, add the missing ones."""
        wanted_ids = set(wanted.values())
        now = _now()
        existing = {row.permission_id: row for row in self._repo.grants(role.id)}
        for permission_id, row in existing.items():
            should_be_active = permission_id in wanted_ids
            if row.is_active != should_be_active:
                row.is_active = should_be_active
                row.updated_at = now
                row.updated_by_user_id = actor.id
        for permission_id in wanted_ids - existing.keys():
            self._repo.add(RolePermission(role_id=role.id, permission_id=permission_id, created_by_user_id=actor.id))


def _clean(text: str | None) -> str | None:
    return (text or "").strip() or None


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _touch(role: Role, actor: CurrentUser) -> None:
    role.updated_at = _now()
    role.updated_by_user_id = actor.id
