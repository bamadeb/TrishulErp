"""Employee management through the API: route -> service -> repository -> SQL (SQLite)."""

from collections.abc import Iterator
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.employee",
    "core.company",
    "core.branch",
    "hr.department",
    "hr.designation",
    "core.app_user",
]
COMPANY = 1
PUNE, MUMBAI = 1, 2
DEPT, DESIG = 1, 1
RAHUL = 10  # an existing active employee
ACTOR_ID = 1
URL = "/api/v1/core/employees"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=COMPANY, code="TRISHUL", legal_name="Trishul Pvt Ltd", trade_name="Trishul")
    insert_row(engine, "core.branch", id=PUNE, company_id=COMPANY, code="PUN", name="Pune")
    insert_row(engine, "core.branch", id=MUMBAI, company_id=COMPANY, code="MUM", name="Mumbai")
    insert_row(engine, "hr.department", id=DEPT, code="SVC", name="Service")
    insert_row(engine, "hr.designation", id=DESIG, code="TL", name="Team Lead", department_id=DEPT)
    insert_row(engine, "core.app_user", id=ACTOR_ID, username="admin@trishul.co", cognito_sub="sub-admin")
    insert_row(
        engine,
        "core.employee",
        id=RAHUL,
        company_id=COMPANY,
        branch_id=PUNE,
        employee_code="E010",
        first_name="Rahul",
        last_name="Patil",
        mobile="9822000010",
        department_id=DEPT,
        designation_id=DESIG,
        employee_type="Permanent",
        status="Active",
    )
    return engine


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(
        id=ACTOR_ID,
        permissions=frozenset({"core.employee.view", "core.employee.manage"}),
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
        "employeeCode": "E100",
        "firstName": "Nikhil",
        "lastName": "Rao",
        "mobile": "9876500100",
        "email": "nikhil@trishul.co",
        "companyId": COMPANY,
        "branchId": PUNE,
        "departmentId": DEPT,
        "designationId": DESIG,
        "employeeType": "Permanent",
    } | changes
    return client.post(URL, json=body)


def if_match(employee: dict[str, Any]) -> dict[str, str]:
    return {"If-Match": f'"{employee["rowVersion"]}"'}


def test_create_resolves_names_and_defaults(client: TestClient) -> None:
    response = create(client)
    assert response.status_code == 201, response.text
    employee = response.json()
    assert response.headers["location"] == f"employees/{employee['id']}"
    assert (employee["employeeCode"], employee["fullName"]) == ("E100", "Nikhil Rao")
    assert (employee["branchName"], employee["department"], employee["designation"]) == ("Pune", "Service", "Team Lead")
    assert employee["companyName"] == "Trishul"
    assert employee["status"] == "Active"
    assert employee["isActive"] is True
    assert employee["hasLogin"] is False and employee["userId"] is None


def test_duplicate_code_and_mobile_are_rejected(client: TestClient) -> None:
    assert create(client).status_code == 201
    assert create(client, employeeCode="E010").status_code == 409  # RAHUL's code
    dup_code = create(client, employeeCode="E100", mobile="9876500999")
    assert dup_code.status_code == 409
    dup_mobile = create(client, employeeCode="E200", mobile="9822000010")  # RAHUL's mobile
    assert dup_mobile.status_code == 409


def test_unknown_references_are_rejected_with_field_errors(client: TestClient) -> None:
    assert create(client, branchId=99).status_code == 400
    assert "branchId" in create(client, branchId=99).json()["errors"]
    assert "departmentId" in create(client, departmentId=99).json()["errors"]
    assert "companyId" in create(client, companyId=99).json()["errors"]


def test_invalid_input_is_rejected(client: TestClient) -> None:
    assert create(client, mobile="12345").status_code == 422
    assert create(client, employeeType="Ghost").status_code == 422
    assert create(client, firstName="").status_code == 422
    assert create(client, isActive=True).status_code == 422  # unknown field


def test_list_filters_by_status_branch_and_search(client: TestClient) -> None:
    create(client)  # E100 in Pune
    create(client, employeeCode="E101", mobile="9876500101", firstName="Asha", branchId=MUMBAI)
    everyone = client.get(URL).json()
    assert everyone["total"] == 3  # RAHUL + two created
    pune = client.get(URL, params={"branchId": PUNE}).json()["items"]
    assert {e["employeeCode"] for e in pune} == {"E010", "E100"}
    found = client.get(URL, params={"search": "asha"}).json()["items"]
    assert [e["firstName"] for e in found] == ["Asha"]
    assert client.get(URL, params={"status": "inactive"}).json()["total"] == 0


def test_get_one_and_unknown_is_404(client: TestClient) -> None:
    assert client.get(f"{URL}/{RAHUL}").json()["employeeCode"] == "E010"
    assert client.get(f"{URL}/999").status_code == 404


def test_update_changes_fields_with_a_row_version_check(client: TestClient) -> None:
    employee = client.get(f"{URL}/{RAHUL}").json()
    url = f"{URL}/{RAHUL}"
    change = {"branchId": MUMBAI, "designationId": None}

    assert client.patch(url, json=change).status_code == 428  # If-Match missing
    assert client.patch(url, json=change, headers={"If-Match": '"AAAAAAAAAAA="'}).status_code == 409

    updated = client.patch(url, json=change, headers=if_match(employee))
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["branchName"] == "Mumbai"
    assert body["designation"] is None
    assert body["employeeCode"] == "E010"  # not sent, unchanged


def test_update_rejects_duplicate_code_and_self_manager(client: TestClient) -> None:
    created = create(client).json()
    url = f"{URL}/{created['id']}"
    assert client.patch(url, json={"employeeCode": "E010"}, headers=if_match(created)).status_code == 409
    self_manager = client.patch(url, json={"reportingManagerId": created["id"]}, headers=if_match(created))
    assert self_manager.status_code == 400
    assert "reportingManagerId" in self_manager.json()["errors"]


def test_deactivate_and_activate(client: TestClient) -> None:
    deactivated = client.post(f"{URL}/{RAHUL}/deactivate").json()
    assert deactivated["isActive"] is False
    assert RAHUL not in [e["id"] for e in client.get(URL).json()["items"]]  # default filter is active
    activated = client.post(f"{URL}/{RAHUL}/activate").json()
    assert activated["isActive"] is True


def test_deactivate_is_blocked_while_an_active_login_exists(client: TestClient, db: Engine) -> None:
    insert_row(db, "core.app_user", id=2, username="rahul@trishul.co", cognito_sub="sub-rahul", employee_id=RAHUL)
    detail = client.get(f"{URL}/{RAHUL}").json()
    assert detail["hasLogin"] is True and detail["userId"] == 2
    blocked = client.post(f"{URL}/{RAHUL}/deactivate")
    assert blocked.status_code == 400
    assert "Deactivate the user first" in blocked.json()["detail"]


def test_form_option_lists(client: TestClient) -> None:
    assert [c["name"] for c in client.get("/api/v1/core/companies").json()] == ["Trishul"]
    assert [d["code"] for d in client.get("/api/v1/core/departments").json()] == ["SVC"]
    designations = client.get("/api/v1/core/designations").json()
    assert designations[0]["departmentId"] == DEPT
