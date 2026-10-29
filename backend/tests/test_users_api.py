"""User management through the API: route → service → repository → SQL (SQLite) → audit log, with a
fake identity provider that records what would happen in Cognito."""

from collections.abc import Iterator
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.auth.identity import AccountExists, CreatedAccount, Delivery, SignInStatus
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import AppUser, AuditLog, Employee
from trishul_api.main import create_app
from trishul_api.modules.core.users.repository import UserRepository

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.app_user",
    "core.role",
    "core.user_role",
    "core.branch",
    "core.principal",
    "core.user_principal_access",
    "core.employee",
    "hr.department",
    "hr.designation",
    "core.audit_log",
]
ADMIN, TEAM_LEAD = 1, 2
PUNE, MUMBAI = 1, 2
ATLAS, TATA = 1, 2
ACTOR_ID = 1
RAHUL, SNEHA, LEFT = 10, 11, 12  # employees


class FakeIdentity:
    """Records calls; behaves like Cognito for the cases the service handles."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.accounts: dict[str, str] = {"admin@trishul.co": "sub-admin"}
        self.disabled: set[str] = set()
        self.subject_override: str | None = None

    def create_account(self, email: str, delivery: Delivery) -> CreatedAccount:
        self.calls.append(("create", email, delivery))
        if email in self.accounts:
            raise AccountExists("exists")
        self.accounts[email] = self.subject_override or f"sub-{email}"
        return CreatedAccount(self.accounts[email], "Temp#Pass12345" if delivery == "show" else None)

    def find_subject(self, email: str) -> str | None:
        return self.accounts.get(email)

    def delete_account(self, email: str) -> None:
        self.calls.append(("delete", email))
        self.accounts.pop(email, None)

    def status(self, email: str) -> SignInStatus:
        if email in self.disabled:
            return "disabled"
        return "password-change-required" if email in self.accounts else "missing"

    def disable(self, email: str) -> None:
        self.calls.append(("disable", email))
        self.disabled.add(email)

    def enable(self, email: str) -> None:
        self.calls.append(("enable", email))
        self.disabled.discard(email)

    def reset_password(self, email: str, delivery: Delivery) -> str | None:
        self.calls.append(("reset", email, delivery))
        return "Temp#Reset12345" if delivery == "show" else None


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.role", id=ADMIN, code="ADMIN", name="Administrator")
    insert_row(engine, "core.role", id=TEAM_LEAD, code="TEAM_LEAD", name="Service Team Lead")
    insert_row(engine, "core.branch", id=PUNE, code="PUN", name="Pune")
    insert_row(engine, "core.branch", id=MUMBAI, code="MUM", name="Mumbai")
    insert_row(engine, "core.principal", id=ATLAS, code="ATLAS_COPCO", name="Atlas Copco")
    insert_row(engine, "core.principal", id=TATA, code="TATA_HITACHI", name="Tata Hitachi")
    insert_row(engine, "core.app_user", id=ACTOR_ID, username="admin@trishul.co", cognito_sub="sub-admin")
    insert_row(engine, "hr.department", id=1, code="SVC", name="Service")
    insert_row(engine, "hr.designation", id=1, code="TL", name="Team Lead", department_id=1)
    employee = {"company_id": 1, "branch_id": PUNE, "employee_type": "Permanent"}
    insert_row(
        engine,
        "core.employee",
        id=RAHUL,
        employee_code="E010",
        first_name="Rahul",
        last_name="Patil",
        mobile="9822000010",
        department_id=1,
        designation_id=1,
        **employee,
    )
    insert_row(engine, "core.employee", id=SNEHA, employee_code="E011", first_name="Sneha", **employee)
    insert_row(engine, "core.employee", id=LEFT, employee_code="E012", first_name="Old", is_active=False, **employee)
    return engine


@pytest.fixture
def identity() -> FakeIdentity:
    return FakeIdentity()


@pytest.fixture
def client(settings: Settings, db: Engine, identity: FakeIdentity) -> Iterator[TestClient]:
    app = create_app(settings, engine=db, identity_provider=identity)
    api = app.state.api_v1
    actor = make_user(
        id=ACTOR_ID,
        roles=frozenset({"ADMIN"}),
        permissions=frozenset({"core.user.view", "core.user.manage"}),
        branch_ids=None,
        principal_ids=None,
    )
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:  # SQLite has no SESSION_CONTEXT; same audit context as get_db
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=ACTOR_ID, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


URL = "/api/v1/core/users"


def create(client: TestClient, **changes: Any) -> httpx.Response:
    body = {
        "email": "Rahul.Patil@Trishul.co",
        "mobile": "9876543210",
        "defaultBranchId": PUNE,
        "roles": [{"roleId": TEAM_LEAD, "branchId": PUNE}],
        "principalIds": [ATLAS],
    } | changes
    return client.post(URL, json=body)


def if_match(user: dict[str, Any]) -> dict[str, str]:
    return {"If-Match": f'"{user["rowVersion"]}"'}


def test_create_sends_an_invitation_and_saves_roles_and_brands(client: TestClient, identity: FakeIdentity) -> None:
    response = create(client)
    assert response.status_code == 201, response.text
    user = response.json()
    assert user["username"] == "rahul.patil@trishul.co"  # sign-in names are lower case
    assert response.headers["location"] == f"users/{user['id']}"
    assert [(r["roleCode"], r["branchName"]) for r in user["roles"]] == [("TEAM_LEAD", "Pune")]
    assert user["principalIds"] == [ATLAS]
    assert user["signInStatus"] == "password-change-required"
    assert user["temporaryPassword"] is None
    assert identity.calls == [("create", "rahul.patil@trishul.co", "email")]


def test_create_can_return_a_temporary_password(client: TestClient) -> None:
    user = create(client, delivery="show").json()
    assert user["temporaryPassword"] == "Temp#Pass12345"


def test_duplicate_email_is_rejected_before_cognito(client: TestClient, identity: FakeIdentity) -> None:
    assert create(client).status_code == 201
    second = create(client, email="rahul.patil@trishul.co")
    assert second.status_code == 409
    assert second.json()["detail"] == "A user with this email already exists."
    assert len([c for c in identity.calls if c[0] == "create"]) == 1


def test_unknown_role_is_rejected_before_cognito(client: TestClient, identity: FakeIdentity) -> None:
    response = create(client, roles=[{"roleId": 99}])
    assert response.status_code == 400
    assert "roles" in response.json()["errors"]
    assert identity.calls == []


def test_invalid_input_is_rejected(client: TestClient) -> None:
    assert create(client, email="not-an-email").status_code == 422
    assert create(client, mobile="12345").status_code == 422
    assert create(client, roles=[]).status_code == 422
    assert create(client, isActive=False).status_code == 422  # unknown fields are refused


def test_a_failed_save_removes_the_new_cognito_account(
    client: TestClient, identity: FakeIdentity, monkeypatch: pytest.MonkeyPatch
) -> None:
    # As SQL Server's unique index would when two admins add the same email at the same moment.
    def duplicate(_self: UserRepository) -> None:
        raise IntegrityError("INSERT core.app_user", None, Exception("UX_core_app_user_username"))

    monkeypatch.setattr(UserRepository, "flush", duplicate)
    response = create(client)
    assert response.status_code == 409
    assert ("delete", "rahul.patil@trishul.co") in identity.calls
    assert "rahul.patil@trishul.co" not in identity.accounts


def test_create_round_trips_the_row_version(client: TestClient) -> None:
    created = create(client).json()
    fetched = client.get(f"{URL}/{created['id']}").json()
    assert created["rowVersion"] == fetched["rowVersion"]


def test_list_search_and_status_filter(client: TestClient) -> None:
    create(client)
    create(client, email="sneha@trishul.co", roles=[{"roleId": ADMIN}])
    everyone = client.get(URL).json()
    assert everyone["total"] == 3
    found = client.get(URL, params={"search": "sneha"}).json()["items"]
    assert [(u["username"], [r["roleCode"] for r in u["roles"]]) for u in found] == [("sneha@trishul.co", ["ADMIN"])]
    by_role = client.get(URL, params={"roleId": TEAM_LEAD}).json()["items"]
    assert [u["username"] for u in by_role] == ["rahul.patil@trishul.co"]
    assert client.get(URL, params={"status": "inactive"}).json()["total"] == 0


def test_update_replaces_roles_and_brands_with_a_row_version_check(client: TestClient) -> None:
    user = create(client).json()
    url = f"{URL}/{user['id']}"
    change = {"roles": [{"roleId": ADMIN}], "principalIds": [ATLAS, TATA], "mobile": None}

    assert client.patch(url, json=change).status_code == 428  # If-Match missing
    stale = {"If-Match": '"AAAAAAAAAAA="'}
    assert client.patch(url, json=change, headers=stale).status_code == 409

    response = client.patch(url, json=change, headers=if_match(user))
    assert response.status_code == 200, response.text
    updated = response.json()
    assert [(r["roleCode"], r["branchId"]) for r in updated["roles"]] == [("ADMIN", None)]
    assert updated["principalIds"] == [ATLAS, TATA]
    assert updated["mobile"] is None
    assert updated["defaultBranchId"] == PUNE  # not sent, so unchanged


def test_deactivate_blocks_sign_in_and_activate_restores_it(client: TestClient, identity: FakeIdentity) -> None:
    user = create(client).json()
    deactivated = client.post(f"{URL}/{user['id']}/deactivate")
    assert deactivated.status_code == 200
    assert deactivated.json()["isActive"] is False
    assert deactivated.json()["signInStatus"] == "disabled"
    assert ("disable", user["username"]) in identity.calls
    assert user["id"] not in [u["id"] for u in client.get(URL).json()["items"]]  # default filter: active

    activated = client.post(f"{URL}/{user['id']}/activate").json()
    assert activated["isActive"] is True
    assert ("enable", user["username"]) in identity.calls


def test_users_cannot_deactivate_themselves(client: TestClient) -> None:
    response = client.post(f"{URL}/{ACTOR_ID}/deactivate")
    assert response.status_code == 400
    assert response.json()["detail"] == "You can't deactivate your own account."


def test_reset_password(client: TestClient, identity: FakeIdentity) -> None:
    user = create(client).json()
    url = f"{URL}/{user['id']}/reset-password"
    shown = client.post(url, json={"delivery": "show"}).json()
    assert shown["temporaryPassword"] == "Temp#Reset12345"
    emailed = client.post(url, json={"delivery": "email"}).json()
    assert emailed["temporaryPassword"] is None
    assert ("reset", user["username"], "email") in identity.calls

    client.post(f"{URL}/{user['id']}/deactivate")
    assert client.post(url, json={"delivery": "email"}).status_code == 400  # inactive users first


def test_unknown_user_is_404(client: TestClient) -> None:
    assert client.get(f"{URL}/999").status_code == 404
    assert client.post(f"{URL}/999/deactivate").status_code == 404


def test_changes_are_audited(client: TestClient, db: Engine) -> None:
    create(client)
    with Session(db) as session:
        entries = {(row.entity_type, row.action) for row in session.scalars(select(AuditLog))}
    assert {
        ("core.app_user", "Insert"),
        ("core.user_role", "Insert"),
        ("core.user_principal_access", "Insert"),
    } <= entries


def test_a_linked_employee_supplies_names_and_phone(client: TestClient) -> None:
    created = create(client, employeeId=RAHUL, mobile=None)
    assert created.status_code == 201, created.text
    user = created.json()
    assert (user["employeeCode"], user["firstName"], user["lastName"]) == ("E010", "Rahul", "Patil")
    assert user["displayName"] == "Rahul Patil"
    assert (user["designation"], user["department"]) == ("Team Lead", "Service")
    assert (user["mobile"], user["phone"]) == (None, "9822000010")  # no own mobile, so the employee's

    [listed] = client.get(URL, params={"search": "E010"}).json()["items"]
    assert (listed["id"], listed["firstName"], listed["phone"]) == (user["id"], "Rahul", "9822000010")

    url = f"{URL}/{user['id']}"
    own = client.patch(url, json={"mobile": "9123456780"}, headers=if_match(user)).json()
    assert own["phone"] == "9123456780"  # the user's own mobile wins
    unlinked = client.patch(url, json={"employeeId": None}, headers=if_match(own)).json()
    assert (unlinked["employeeId"], unlinked["firstName"], unlinked["displayName"]) == (
        None,
        None,
        "rahul.patil@trishul.co",
    )


def test_an_employee_can_be_linked_to_one_user_only(client: TestClient, identity: FakeIdentity) -> None:
    rahul = create(client, employeeId=RAHUL).json()
    second = create(client, email="other@trishul.co", employeeId=RAHUL)
    assert second.status_code == 409
    assert second.json()["detail"] == "This employee is already linked to user rahul.patil@trishul.co."
    assert ("create", "other@trishul.co", "email") not in identity.calls  # refused before Cognito

    sneha = create(client, email="sneha@trishul.co", employeeId=SNEHA).json()
    moved = client.patch(f"{URL}/{sneha['id']}", json={"employeeId": RAHUL}, headers=if_match(sneha))
    assert moved.status_code == 409
    same = client.patch(f"{URL}/{rahul['id']}", json={"employeeId": RAHUL}, headers=if_match(rahul))
    assert same.status_code == 200  # re-saving your own link is fine


def test_unknown_or_inactive_employee_is_rejected(client: TestClient, identity: FakeIdentity) -> None:
    for employee_id in (999, LEFT):
        response = create(client, employeeId=employee_id)
        assert response.status_code == 400
        assert "employeeId" in response.json()["errors"]
    assert identity.calls == []


def test_employee_picker_searches_active_employees_and_shows_links(client: TestClient) -> None:
    url = "/api/v1/core/users/employee-options"
    rahul = create(client, employeeId=RAHUL).json()
    options = client.get(url).json()
    assert [(e["employeeCode"], e["linkedUserId"]) for e in options] == [("E010", rahul["id"]), ("E011", None)]
    found = client.get(url, params={"search": "sneha"}).json()
    assert [e["firstName"] for e in found] == ["Sneha"]
    assert found[0]["branchName"] == "Pune"


def test_existence_checks_are_valid_sql_server_syntax() -> None:
    # The tests run on SQLite, which accepts `SELECT EXISTS(...)`; SQL Server does not. The repository's
    # existence checks must compile to the `SELECT TOP 1 ... WHERE ...` form, with no EXISTS in the SELECT.
    statements = [
        select(AppUser.id).where(AppUser.username == "x").limit(1),
        select(AppUser.id).where(AppUser.cognito_sub == "x").limit(1),
        select(Employee.id).where(Employee.id == 1, Employee.is_active).limit(1),
    ]
    for statement in statements:
        sql = str(statement.compile(dialect=mssql.dialect())).upper()  # type: ignore[no-untyped-call]
        assert sql.startswith("SELECT TOP"), sql
        assert "EXISTS (" not in sql, sql


def test_roles_for_the_form(client: TestClient) -> None:
    roles = client.get("/api/v1/core/roles").json()
    assert [r["code"] for r in roles] == ["ADMIN", "TEAM_LEAD"]  # sorted by name
