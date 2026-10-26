"""Which branches and brands a user may work in. Pure rules, no database access.

Mirrors rls.fn_can_see (database/10_row_level_security.sql); change both together.
"""

from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass

# These roles see every brand and branch.
UNRESTRICTED_ROLES = frozenset({"ADMIN", "MANAGEMENT", "ACCOUNTS"})


@dataclass(frozen=True)
class RoleGrant:
    """A row of core.user_role: a role, on one branch or (branch_id None) on all branches."""

    role: str
    branch_id: int | None


@dataclass(frozen=True)
class AccessScope:
    branch_ids: frozenset[int] | None
    """Branches the user may work in; None means all."""
    principal_ids: frozenset[int] | None
    """Brands the user may see; None means all."""


def resolve_scope(
    grants: Collection[RoleGrant],
    principal_ids: Iterable[int],
    branches_served_by: Callable[[frozenset[int]], Iterable[int]],
) -> AccessScope:
    """branches_served_by(warehouse_ids) returns the branches those warehouses supply: a role on a
    warehouse also covers them. It is only called when the user has branch-limited roles."""
    if any(grant.role in UNRESTRICTED_ROLES for grant in grants):
        return AccessScope(branch_ids=None, principal_ids=None)
    if any(grant.branch_id is None for grant in grants):
        branch_ids = None
    else:
        granted = frozenset(grant.branch_id for grant in grants if grant.branch_id is not None)
        branch_ids = granted | frozenset(branches_served_by(granted)) if granted else frozenset()
    return AccessScope(branch_ids=branch_ids, principal_ids=frozenset(principal_ids))
