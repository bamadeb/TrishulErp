"""Leave types and policies. Approval and balances are not part of this phase."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import sqlite_engine

TABLES = [
    "core.app_user",
    "hr.leave_type",
    "hr.leave_type_setting",
    "hr.leave_policy",
    "hr.leave_policy_line",
]
TYPES = "/api/v1/hr/leave/types"
POLICIES = "/api/v1/hr/leave/policies"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    return engine


def _client(settings: Settings, db: Engine, permissions: frozenset[str]) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    api.dependency_overrides[get_current_user] = lambda: make_user(id=1, permissions=permissions)

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current:
            set_audit_context(current, user_id=1, source="Web", ip_address="127.0.0.1")
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    yield from _client(settings, db, frozenset({"hr.leave.view", "hr.leave.manage"}))


def _type_body() -> dict[str, object]:
    return {
        "code": "cl",
        "name": "Casual Leave",
        "description": "Short personal leave",
        "annualQuota": "8.0",
        "isPaid": True,
        "halfDayAllowed": True,
        "accrualApplicable": False,
    }


def test_a_leave_type_and_policy_are_saved(client: TestClient) -> None:
    created = client.post(TYPES, json=_type_body())
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["code"] == "CL"
    assert body["description"] == "Short personal leave"
    assert body["halfDayAllowed"] is True
    leave_type_id = body["id"]

    duplicate = client.post(TYPES, json=_type_body())
    assert duplicate.status_code == 409

    policy = client.post(
        POLICIES,
        json={
            "name": "Service staff",
            "employeeType": "Permanent",
            "appliesDuringProbation": False,
            "negativeBalanceAllowed": False,
            "effectiveFrom": "2026-04-01",
            "lines": [{"leaveTypeId": leave_type_id, "annualEntitlement": "8.0", "accrualFrequency": "Yearly"}],
        },
    )
    assert policy.status_code == 201, policy.text
    saved = policy.json()
    assert saved["lines"][0]["leaveTypeCode"] == "CL"
    assert saved["lines"][0]["annualEntitlement"] == "8.0"

    changed = client.patch(
        f"{POLICIES}/{saved['id']}",
        headers={"If-Match": f'"{saved["rowVersion"]}"'},
        json={
            "name": "Service staff",
            "employeeType": "Permanent",
            "effectiveFrom": "2026-04-01",
            "lines": [{"leaveTypeId": leave_type_id, "annualEntitlement": "10.0", "accrualFrequency": "Monthly"}],
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["lines"][0]["annualEntitlement"] == "10.0"
    assert changed.json()["lines"][0]["accrualFrequency"] == "Monthly"


def test_a_caller_without_permission_is_rejected(settings: Settings, db: Engine) -> None:
    guest = next(_client(settings, db, frozenset()))
    assert guest.get(TYPES).status_code == 403
    guest.close()
