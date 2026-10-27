"""User management: core.app_user, its roles and brands, and its sign-in account (Cognito).

The sign-in account is changed first; if saving to the database then fails, a newly created account is
deleted again, so the two never drift apart.
"""

import logging
from collections.abc import Collection
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.auth.identity import AccountExists, CreatedAccount, Delivery, IdentityProvider, SignInStatus
from trishul_api.auth.users import UserDirectory
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.db.models import AppUser, UserPrincipalAccess, UserRole
from trishul_api.modules.core.users.repository import UserRepository
from trishul_api.modules.core.users.schemas import (
    PasswordResetResult,
    RoleGrantInput,
    UserCreate,
    UserCreated,
    UserDetail,
    UserUpdate,
)

logger = logging.getLogger(__name__)

DEV_SUBJECT_PREFIX = "dev:"
_DUPLICATE = "Another user already has this email or employee."


class UserService:
    def __init__(self, db: Session, identity: IdentityProvider, directory: UserDirectory) -> None:
        self._db = db
        self._repo = UserRepository(db)
        self._identity = identity
        self._directory = directory

    def get(self, user_id: int) -> UserDetail:
        return self._detail(self._require(user_id))

    def create(self, actor: CurrentUser, data: UserCreate) -> UserCreated:
        email = str(data.email).strip().lower()
        if self._repo.username_exists(email):
            raise AlreadyExists("A user with this email already exists.")
        roles = _unique_grants(data.roles)
        self._check_references(roles, data.principal_ids, data.default_branch_id)
        if data.employee_id is not None:
            self._check_employee(data.employee_id)

        account, adopted = self._create_account(email, data.delivery)
        try:
            user = AppUser(
                username=email,
                email=email,
                employee_id=data.employee_id,
                mobile=data.mobile,
                cognito_sub=account.subject,
                default_branch_id=data.default_branch_id,
                created_by_user_id=actor.id,
            )
            self._repo.add(user)
            self._repo.flush()
            self._replace_roles(user, roles)
            self._replace_principals(user, data.principal_ids)
            self._db.commit()
        except Exception as error:
            self._db.rollback()
            if not adopted:
                self._undo_account(email)
            if isinstance(error, IntegrityError):
                raise AlreadyExists(_DUPLICATE) from error
            raise
        detail = self._detail(user)
        # dict(detail), not model_dump(): dumping would serialize rowVersion to base64 and the response
        # would encode it a second time.
        return UserCreated(**dict(detail), temporary_password=account.temporary_password)

    def update(self, actor: CurrentUser, user_id: int, expected_row_version: bytes, data: UserUpdate) -> UserDetail:
        user = self._require(user_id)
        check_row_version(user.row_version, expected_row_version)
        changed = data.model_fields_set
        roles = _unique_grants(data.roles) if data.roles is not None else None
        self._check_references(
            roles or [],
            data.principal_ids or [],
            data.default_branch_id if "default_branch_id" in changed else None,
        )
        if "employee_id" in changed:
            if data.employee_id is not None:
                self._check_employee(data.employee_id, user.id)
            user.employee_id = data.employee_id
        if "mobile" in changed:
            user.mobile = data.mobile
        if "default_branch_id" in changed:
            user.default_branch_id = data.default_branch_id
        if roles is not None:
            self._replace_roles(user, roles)
        if data.principal_ids is not None:
            self._replace_principals(user, data.principal_ids)
        self._touch(user, actor)  # also moves row_version on when only roles / brands changed
        try:
            self._db.commit()
        except IntegrityError as error:  # another admin linked the same employee at the same moment
            self._db.rollback()
            raise AlreadyExists(_DUPLICATE) from error
        self._directory.clear()  # new roles and display name apply from the next request
        return self._detail(user)

    def deactivate(self, actor: CurrentUser, user_id: int) -> UserDetail:
        user = self._require(user_id)
        if user.id == actor.id:
            raise ApiError("You can't deactivate your own account.")
        if user.is_active:
            if _has_account(user):
                self._identity.disable(user.username)  # blocks sign-in, ends sessions
            user.is_active = False
            self._touch(user, actor)
            self._db.commit()
            self._directory.clear()  # API access ends now, not when the cache expires
        return self._detail(user)

    def activate(self, actor: CurrentUser, user_id: int) -> UserDetail:
        user = self._require(user_id)
        if not user.is_active:
            if _has_account(user):
                self._identity.enable(user.username)
            user.is_active = True
            self._touch(user, actor)
            self._db.commit()
            self._directory.clear()
        return self._detail(user)

    def reset_password(self, actor: CurrentUser, user_id: int, delivery: Delivery) -> PasswordResetResult:
        user = self._require(user_id)
        if not user.is_active:
            raise ApiError("Activate the user before resetting the password.")
        if not _has_account(user):
            raise ApiError("This is a development user; it has no password.")
        password = self._identity.reset_password(user.username, delivery)
        logger.info("Password reset for user %s by user %s (%s)", user.id, actor.id, delivery)
        return PasswordResetResult(
            delivery=delivery, temporary_password=password, sign_in_status=self._identity.status(user.username)
        )

    # ------------------------------------------------------------------ helpers

    def _require(self, user_id: int) -> AppUser:
        user = self._repo.get(user_id)
        if user is None:
            raise NotFound("User not found.")
        return user

    def _detail(self, user: AppUser) -> UserDetail:
        status: SignInStatus = self._identity.status(user.username) if _has_account(user) else "development"
        item = self._repo.list_item(user.id)
        item.roles = self._repo.grants_by_user([user.id]).get(user.id, [])
        return UserDetail(
            **dict(item),
            default_branch_id=user.default_branch_id,
            principal_ids=sorted(row.principal_id for row in self._repo.principal_rows(user.id)),
            sign_in_status=status,
            row_version=user.row_version,
        )

    def _create_account(self, email: str, delivery: Delivery) -> tuple[CreatedAccount, bool]:
        """(account, adopted). An account left over from an earlier failed attempt is reused."""
        try:
            return self._identity.create_account(email, delivery), False
        except AccountExists:
            subject = self._identity.find_subject(email)
            if subject is None or self._repo.subject_in_use(subject):
                raise
            logger.info("Linking existing sign-in account %s to a new ERP user", email)
            return CreatedAccount(subject=subject, temporary_password=None), True

    def _undo_account(self, email: str) -> None:
        try:
            self._identity.delete_account(email)
        except Exception:
            logger.exception("Could not remove sign-in account %s after a failed create", email)

    def _check_employee(self, employee_id: int, user_id: int | None = None) -> None:
        if not self._repo.employee_is_active(employee_id):
            raise ApiError(
                "This employee doesn't exist or is inactive.",
                errors={"employeeId": [f"Unknown employee {employee_id}"]},
            )
        other = self._repo.user_linked_to(employee_id)
        if other is not None and other.id != user_id:
            raise AlreadyExists(f"This employee is already linked to user {other.username}.")

    def _check_references(
        self, roles: Collection[RoleGrantInput], principal_ids: Collection[int], default_branch_id: int | None
    ) -> None:
        errors: dict[str, list[str]] = {}
        if missing := self._repo.missing_roles({grant.role_id for grant in roles}):
            errors["roles"] = [f"Unknown role ids: {sorted(missing)}"]
        branches = {grant.branch_id for grant in roles if grant.branch_id is not None}
        if default_branch_id is not None:
            branches.add(default_branch_id)
        if missing := self._repo.missing_branches(branches):
            errors["branches"] = [f"Unknown branch ids: {sorted(missing)}"]
        if missing := self._repo.missing_principals(set(principal_ids)):
            errors["principalIds"] = [f"Unknown brand ids: {sorted(missing)}"]
        if errors:
            raise ApiError("Some of the selected roles, branches or brands don't exist.", errors=errors)

    def _replace_roles(self, user: AppUser, wanted: Collection[RoleGrantInput]) -> None:
        keys = {(grant.role_id, grant.branch_id) for grant in wanted}
        current = self._repo.role_rows(user.id)
        for row in current:
            if (row.role_id, row.branch_id) not in keys:
                self._repo.delete(row)
        existing = {(row.role_id, row.branch_id) for row in current}
        for role_id, branch_id in sorted(keys - existing, key=str):
            self._repo.add(UserRole(app_user_id=user.id, role_id=role_id, branch_id=branch_id))

    def _replace_principals(self, user: AppUser, wanted: Collection[int]) -> None:
        current = self._repo.principal_rows(user.id)
        for row in current:
            if row.principal_id not in wanted:
                self._repo.delete(row)
        for principal_id in sorted(set(wanted) - {row.principal_id for row in current}):
            self._repo.add(UserPrincipalAccess(app_user_id=user.id, principal_id=principal_id))

    @staticmethod
    def _touch(user: AppUser, actor: CurrentUser) -> None:
        user.updated_at = datetime.now(UTC).replace(tzinfo=None)
        user.updated_by_user_id = actor.id


def _has_account(user: AppUser) -> bool:
    """Development users (cognito_sub "dev:...") have no account in the identity provider."""
    return not user.cognito_sub.startswith(DEV_SUBJECT_PREFIX)


def _unique_grants(grants: Collection[RoleGrantInput]) -> list[RoleGrantInput]:
    seen: dict[tuple[int, int | None], RoleGrantInput] = {}
    for grant in grants:
        seen.setdefault((grant.role_id, grant.branch_id), grant)
    return list(seen.values())
