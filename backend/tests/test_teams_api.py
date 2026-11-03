"""Team management through the API: route -> service -> repository -> SQL (SQLite)."""

from collections.abc import Iterator
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import TeamMember
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "core.employee",
    "hr.designation",
    "core.team",
    "core.team_member",
    "core.app_user",
    "core.audit_log",
]
COMPANY, BRANCH, OTHER_BRANCH = 1, 1, 2
LEAD, ENG_A, ENG_B, ELSEWHERE, INACTIVE = 10, 11, 12, 13, 14
ACTOR_ID = 1
URL = "/api/v1/core/teams"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TRISHUL", legal_name="Trishul", trade_name="Trishul")
    insert_row(engine, "core.branch", id=BRANCH, company_id=COMPANY, code="BBSR", name="Bhubaneswar")
    insert_row(engine, "core.branch", id=OTHER_BRANCH, company_id=COMPANY, code="CTC", name="Cuttack")
    insert_row(engine, "hr.designation", id=1, code="SERVICE_ENG", name="Service Engineer")
    insert_row(engine, "hr.designation", id=2, code="TEAM_LEAD", name="Service Team Lead")
    for employee_id, first, branch, designation, active in (
        (LEAD, "Rahul", BRANCH, 2, True),
        (ENG_A, "Amit", BRANCH, 1, True),
        (ENG_B, "Bina", BRANCH, 1, True),
        (ELSEWHERE, "Chetan", OTHER_BRANCH, 1, True),
        (INACTIVE, "Dev", BRANCH, 1, False),
    ):
        insert_row(
            engine,
            "core.employee",
            id=employee_id,
            company_id=COMPANY,
            branch_id=branch,
            employee_code=f"E{employee_id}",
            first_name=first,
            last_name="Kumar",
            designation_id=designation,
            employee_type="Permanent",
            status="Active",
            is_active=active,
        )
    insert_row(engine, "core.app_user", id=ACTOR_ID, username="admin@trishul.co")
    return engine


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(
        id=ACTOR_ID, permissions=frozenset({"core.team.view", "core.team.manage"}), branch_ids=None, principal_ids=None
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
    body = {"name": "Service A", "branchId": BRANCH, "teamLeadEmployeeId": LEAD, "memberEmployeeIds": [ENG_A]} | changes
    return client.post(URL, json=body)


def if_match(team: dict[str, Any]) -> dict[str, str]:
    return {"If-Match": f'"{team["rowVersion"]}"'}


def test_create_lists_and_shows_a_team(client: TestClient) -> None:
    created = create(client)
    assert created.status_code == 201, created.text
    team = created.json()
    assert created.headers["Location"] == f"teams/{team['id']}"
    assert (team["teamType"], team["branchName"], team["teamLeadName"]) == ("Service", "Bhubaneswar", "Rahul Kumar")
    assert [m["employeeCode"] for m in team["members"]] == ["E11"]
    rows = client.get(URL).json()
    assert [(r["name"], r["memberCount"]) for r in rows] == [("Service A", 1)]


def test_members_must_be_active_employees_of_the_branch(client: TestClient) -> None:
    for members in ([ELSEWHERE], [INACTIVE]):
        rejected = create(client, memberEmployeeIds=members)
        assert rejected.status_code == 400
        assert "memberEmployeeIds" in rejected.json()["errors"]
    lead_elsewhere = create(client, teamLeadEmployeeId=ELSEWHERE)
    assert "teamLeadEmployeeId" in lead_elsewhere.json()["errors"]
    lead_as_member = create(client, memberEmployeeIds=[LEAD])
    assert lead_as_member.status_code == 400


def test_an_engineer_is_in_one_service_team_at_a_time(client: TestClient) -> None:
    assert create(client).status_code == 201
    second = create(client, name="Service B", memberEmployeeIds=[ENG_A, ENG_B])
    assert second.status_code == 400
    assert second.json()["errors"]["memberEmployeeIds"] == ["Amit Kumar is in Service A."]


def test_team_names_are_unique_per_branch(client: TestClient) -> None:
    assert create(client).status_code == 201
    assert create(client, memberEmployeeIds=[]).status_code == 409


def test_update_replaces_members_and_keeps_history(client: TestClient, db: Engine) -> None:
    team = create(client).json()
    updated = client.patch(f"{URL}/{team['id']}", json={"memberEmployeeIds": [ENG_B]}, headers=if_match(team))
    assert updated.status_code == 200, updated.text
    assert [m["employeeId"] for m in updated.json()["members"]] == [ENG_B]
    with Session(db) as s:
        rows = {(r.employee_id, r.is_active, r.to_date is not None) for r in s.scalars(select(TeamMember))}
    assert rows == {(ENG_A, False, True), (ENG_B, True, False)}  # Amit's membership ended, not deleted


def test_deactivated_team_frees_its_members(client: TestClient) -> None:
    team = create(client).json()
    assert client.post(f"{URL}/{team['id']}/deactivate").json()["isActive"] is False
    assert create(client, name="Service B").status_code == 201  # Amit can join another team now
    blocked = client.post(f"{URL}/{team['id']}/activate")
    assert blocked.status_code == 400  # but then the old team can't come back with him in it
    assert client.get(URL, params={"status": "inactive"}).json()[0]["name"] == "Service A"


def test_employee_options_are_the_branchs_active_employees(client: TestClient) -> None:
    rows = client.get(f"{URL}/employee-options", params={"branchId": BRANCH}).json()
    assert [r["employeeCode"] for r in rows] == ["E11", "E12", "E10"]
    assert rows[0]["designationCode"] == "SERVICE_ENG"
