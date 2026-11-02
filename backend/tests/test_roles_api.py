"""Role management through the API: route -> service -> repository -> SQL (SQLite)."""

from collections.abc import Iterator
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.auth.user_repository import UserRepository
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import RolePermission
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.role",
    "core.permission",
    "core.role_permission",
    "core.user_role",
    "core.app_user",
    "core.audit_log",
]
ADMIN, TEAM_LEAD = 1, 2
CALL_VIEW, CALL_ASSIGN, ROLE_MANAGE, OLD = 1, 2, 3, 4
ACTOR_ID, ENGINEER = 1, 2
URL = "/api/v1/core/roles"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.role", id=ADMIN, code="ADMIN", name="Administrator", is_system=True)
    insert_row(engine, "core.role", id=TEAM_LEAD, code="TEAM_LEAD", name="Service Team Lead", is_system=True)
    for permission_id, code, module, active in (
        (CALL_VIEW, "svc.call.view", "Service", True),
        (CALL_ASSIGN, "svc.call.assign", "Service", True),
        (ROLE_MANAGE, "core.role.manage", "Core", True),
        (OLD, "old.retired", "Core", False),
    ):
        insert_row(engine, "core.permission", id=permission_id, code=code, module=module, is_active=active)
    for role_id, permission_id in (
        (ADMIN, CALL_VIEW),
        (ADMIN, CALL_ASSIGN),
        (ADMIN, ROLE_MANAGE),
        (TEAM_LEAD, CALL_VIEW),
    ):
        insert_row(engine, "core.role_permission", role_id=role_id, permission_id=permission_id)
    insert_row(engine, "core.app_user", id=ACTOR_ID, username="admin@trishul.co")
    insert_row(engine, "core.app_user", id=ENGINEER, username="engineer@trishul.co")
    insert_row(engine, "core.user_role", app_user_id=ACTOR_ID, role_id=ADMIN)
    return engine


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(
        id=ACTOR_ID,
        permissions=frozenset({"core.role.view", "core.role.manage"}),
        branch_ids=None,
        principal_ids=None,
    )
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=ACTOR_ID, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def create(client: TestClient, **changes: Any) -> httpx.Response:
    body = {
        "code": "AREA_MANAGER",
        "name": "Area manager",
        "description": "Looks after several branches",
        "permissionCodes": ["svc.call.view", "svc.call.assign"],
    } | changes
    return client.post(URL, json=body)


def if_match(role: dict[str, Any]) -> dict[str, str]:
    return {"If-Match": f'"{role["rowVersion"]}"'}


def test_create_with_permissions(client: TestClient) -> None:
    response = create(client)
    assert response.status_code == 201, response.text
    role = response.json()
    assert response.headers["location"] == f"roles/{role['id']}"
    assert (role["code"], role["name"], role["isSystem"], role["isActive"]) == (
        "AREA_MANAGER",
        "Area manager",
        False,
        True,
    )
    assert role["permissionCodes"] == ["svc.call.assign", "svc.call.view"]
    assert role["permissionCount"] == 2


def test_create_rejects_duplicates_bad_codes_and_unknown_permissions(client: TestClient) -> None:
    assert create(client).status_code == 201
    assert create(client).status_code == 409
    assert create(client, code="TEAM_LEAD").status_code == 409
    assert create(client, code="area manager").status_code == 422
    unknown = create(client, code="X_ROLE", permissionCodes=["svc.call.view", "nope", "old.retired"])
    assert unknown.status_code == 400
    assert len(unknown.json()["errors"]["permissionCodes"]) == 2  # inactive permissions can't be granted


def test_list_counts_users_and_permissions_and_filters(client: TestClient, db: Engine) -> None:
    insert_row(db, "core.user_role", app_user_id=ENGINEER, role_id=TEAM_LEAD)
    roles = {r["code"]: r for r in client.get(URL).json()}
    assert (roles["ADMIN"]["userCount"], roles["ADMIN"]["permissionCount"]) == (1, 3)
    assert (roles["TEAM_LEAD"]["userCount"], roles["TEAM_LEAD"]["permissionCount"]) == (1, 1)
    assert [r["code"] for r in client.get(URL, params={"search": "team"}).json()] == ["TEAM_LEAD"]

    created = create(client).json()
    client.post(f"{URL}/{created['id']}/deactivate")
    assert "AREA_MANAGER" not in [r["code"] for r in client.get(URL).json()]  # active by default
    assert [r["code"] for r in client.get(URL, params={"status": "inactive"}).json()] == ["AREA_MANAGER"]


def test_update_replaces_the_permission_list(client: TestClient, db: Engine) -> None:
    role = client.get(f"{URL}/{TEAM_LEAD}").json()
    url = f"{URL}/{TEAM_LEAD}"
    change = {"name": "Team lead", "permissionCodes": ["svc.call.assign"]}

    assert client.patch(url, json=change).status_code == 428
    assert client.patch(url, json=change, headers={"If-Match": '"AAAAAAAAAAA="'}).status_code == 409

    updated = client.patch(url, json=change, headers=if_match(role))
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Team lead"
    assert updated.json()["permissionCodes"] == ["svc.call.assign"]
    # The old grant is switched off, not deleted, so the audit trail keeps it.
    with Session(db) as session:
        rows = {
            r.permission_id: r.is_active
            for r in session.scalars(select(RolePermission).where(RolePermission.role_id == TEAM_LEAD))
        }
    assert rows == {CALL_VIEW: False, CALL_ASSIGN: True}

    # Granting it again reuses the same row.
    again = client.patch(url, json={"permissionCodes": ["svc.call.view"]}, headers=if_match(updated.json()))
    assert again.json()["permissionCodes"] == ["svc.call.view"]


def test_admin_keeps_role_management(client: TestClient) -> None:
    admin = client.get(f"{URL}/{ADMIN}").json()
    response = client.patch(f"{URL}/{ADMIN}", json={"permissionCodes": ["svc.call.view"]}, headers=if_match(admin))
    assert response.status_code == 400
    assert "permissionCodes" in response.json()["errors"]


def test_built_in_roles_cannot_be_deactivated(client: TestClient) -> None:
    assert client.post(f"{URL}/{TEAM_LEAD}/deactivate").status_code == 400
    created = create(client).json()
    assert client.post(f"{URL}/{created['id']}/deactivate").json()["isActive"] is False
    assert client.post(f"{URL}/{created['id']}/activate").json()["isActive"] is True


def test_a_deactivated_role_grants_nothing(client: TestClient, db: Engine) -> None:
    created = create(client).json()
    insert_row(db, "core.user_role", app_user_id=ENGINEER, role_id=created["id"])
    with Session(db) as session:
        assert UserRepository(session).permissions(ENGINEER) == {"svc.call.view", "svc.call.assign"}
    client.post(f"{URL}/{created['id']}/deactivate")
    with Session(db) as session:
        repo = UserRepository(session)
        assert repo.permissions(ENGINEER) == frozenset()
        assert repo.role_grants(ENGINEER) == []


def test_get_unknown_is_404_and_permissions_are_listed(client: TestClient) -> None:
    assert client.get(f"{URL}/999").status_code == 404
    permissions = client.get("/api/v1/core/permissions").json()
    assert [p["code"] for p in permissions] == ["core.role.manage", "svc.call.assign", "svc.call.view"]
    assert permissions[0]["module"] == "Core"
