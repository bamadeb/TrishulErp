import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from trishul_api.auth.access import resolve_scope
from trishul_api.auth.tokens import Identity
from trishul_api.auth.user_repository import UserRepository


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    display_name: str
    email: str | None
    default_branch_id: int | None
    roles: frozenset[str]
    permissions: frozenset[str]
    branch_ids: frozenset[int] | None
    """Branches the user may work in; None means all."""
    principal_ids: frozenset[int] | None
    """Brands the user may see; None means all."""

    def can(self, *codes: str) -> bool:
        return any(code in self.permissions for code in codes)

    def can_use_branch(self, branch_id: int) -> bool:
        return self.branch_ids is None or branch_id in self.branch_ids

    def can_see_principal(self, principal_id: int) -> bool:
        return self.principal_ids is None or principal_id in self.principal_ids


UserLoader = Callable[[Identity], CurrentUser | None]


def load_user(repo: UserRepository, identity: Identity) -> CurrentUser | None:
    """The user with roles, permissions, branches and brands. None if unknown or locked."""
    account = repo.account(identity)
    if account is None:
        return None
    grants = repo.role_grants(account.id)
    scope = resolve_scope(grants, repo.principal_ids(account.id), repo.branches_served_by)
    return CurrentUser(
        id=account.id,
        username=account.username,
        display_name=account.display_name,
        email=account.email,
        default_branch_id=account.default_branch_id,
        roles=frozenset(grant.role for grant in grants),
        permissions=repo.permissions(account.id),
        branch_ids=scope.branch_ids,
        principal_ids=scope.principal_ids,
    )


def database_user_loader(engine: Engine) -> UserLoader:
    def load(identity: Identity) -> CurrentUser | None:
        with Session(engine) as session:
            return load_user(UserRepository(session), identity)

    return load


class UserDirectory:
    """Caches signed-in users for a short time so each API call doesn't re-read their roles.
    A locked account loses access within ttl_seconds."""

    def __init__(self, loader: UserLoader, ttl_seconds: float) -> None:
        self._loader = loader
        self._ttl = ttl_seconds
        self._cache: dict[Identity, tuple[float, CurrentUser | None]] = {}
        self._lock = threading.Lock()

    def get(self, identity: Identity) -> CurrentUser | None:
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(identity)
        if cached and cached[0] > now:
            return cached[1]
        user = self._loader(identity)
        with self._lock:
            self._cache[identity] = (now + self._ttl, user)
        return user

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
