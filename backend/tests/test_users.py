"""Access rules (who sees which branches and brands) and the signed-in user cache."""

import pytest

from trishul_api.auth.access import AccessScope, RoleGrant, resolve_scope
from trishul_api.auth.tokens import Identity
from trishul_api.auth.users import CurrentUser, UserDirectory

from .conftest import make_user

# Branch 5 is a warehouse supplying branches 6 and 7.
WAREHOUSE_SUPPLIES = {5: {6, 7}}


def served(warehouse_ids: frozenset[int]) -> set[int]:
    return {branch for w in warehouse_ids for branch in WAREHOUSE_SUPPLIES.get(w, set())}


def scope(*grants: RoleGrant, principals: tuple[int, ...] = (10,)) -> AccessScope:
    return resolve_scope(grants, principals, served)


@pytest.mark.parametrize("role", ["ADMIN", "MANAGEMENT", "ACCOUNTS"])
def test_unrestricted_roles_see_every_branch_and_brand(role: str) -> None:
    assert scope(RoleGrant("TEAM_LEAD", 1), RoleGrant(role, 1)) == AccessScope(branch_ids=None, principal_ids=None)


def test_a_role_without_a_branch_covers_all_branches_but_not_all_brands() -> None:
    result = scope(RoleGrant("BACK_OFFICE", None), RoleGrant("TEAM_LEAD", 1))
    assert result == AccessScope(branch_ids=None, principal_ids=frozenset({10}))


def test_branch_roles_cover_those_branches() -> None:
    assert scope(RoleGrant("TEAM_LEAD", 1), RoleGrant("BACK_OFFICE", 2)).branch_ids == frozenset({1, 2})


def test_a_warehouse_role_covers_the_branches_it_supplies() -> None:
    assert scope(RoleGrant("WAREHOUSE", 5)).branch_ids == frozenset({5, 6, 7})


def test_no_roles_means_no_branches() -> None:
    def must_not_query(_: frozenset[int]) -> set[int]:
        raise AssertionError("no warehouse lookup without branch roles")

    assert resolve_scope([], [], must_not_query) == AccessScope(branch_ids=frozenset(), principal_ids=frozenset())


def test_identity_needs_exactly_one_key() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        Identity()
    with pytest.raises(ValueError, match="exactly one"):
        Identity(cognito_sub="a", username="b")


class CountingLoader:
    def __init__(self, user: CurrentUser | None) -> None:
        self.user = user
        self.calls = 0

    def __call__(self, identity: Identity) -> CurrentUser | None:
        self.calls += 1
        return self.user


def test_directory_caches_users_until_the_ttl_expires() -> None:
    loader = CountingLoader(make_user())
    directory = UserDirectory(loader, ttl_seconds=60)
    identity = Identity(cognito_sub="abc")
    assert directory.get(identity) is directory.get(identity)
    assert loader.calls == 1

    expired = UserDirectory(loader, ttl_seconds=0)
    expired.get(identity)
    expired.get(identity)
    assert loader.calls == 3


def test_directory_also_caches_unknown_users() -> None:
    # Unknown or locked accounts must not cost a database round trip on every request.
    loader = CountingLoader(None)
    directory = UserDirectory(loader, ttl_seconds=60)
    assert directory.get(Identity(username="ghost")) is None
    assert directory.get(Identity(username="ghost")) is None
    assert loader.calls == 1
