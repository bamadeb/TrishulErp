"""Leave balance board, confirmed entitlement credits, and audited adjustments."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta

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
    "core.app_user",
    "core.company",
    "core.region",
    "core.branch",
    "core.employee",
    "hr.department",
    "hr.designation",
    "hr.leave_type",
    "hr.leave_type_setting",
    "hr.leave_policy",
    "hr.leave_policy_line",
    "hr.leave_policy_assignment",
    "hr.leave_balance",
    "hr.leave_request",
    "hr.leave_balance_transaction",
    "hr.leave_entitlement_run",
    "hr.attendance",
    "hr.leave_attendance_class",
]
BOARD = "/api/v1/hr/leave/balances"


@contextmanager
def _client(settings: Settings, engine: Engine, *, manage: bool = True) -> Iterator[TestClient]:
    app = create_app(settings, engine=engine)
    api = app.state.api_v1
    permissions = {"hr.leave.view", "hr.leave.manage"} if manage else {"hr.leave.view"}
    api.dependency_overrides[get_current_user] = lambda: make_user(id=1, permissions=frozenset(permissions))

    def session() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as current:
            set_audit_context(current, user_id=1, source="Web", ip_address="127.0.0.1")
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _office(engine: Engine) -> None:
    insert_row(engine, "core.company", id=1, code="TT", legal_name="Trishul")
    insert_row(engine, "core.region", id=1, code="OD", name="Odisha", warehouse_id=1)
    insert_row(engine, "core.branch", id=1, company_id=1, code="BAM", name="Berhampur", region_id=1, state_id=1)


def _employee(engine: Engine, employee_id: int, code: str, joined: date) -> None:
    insert_row(
        engine, "core.employee", id=employee_id, company_id=1, employee_code=code,
        first_name="Asha", last_name=code, branch_id=1, status="Active", is_active=True,
        date_of_joining=joined,
    )


def _present(engine: Engine, employee_id: int, days: int) -> None:
    start = date(2026, 1, 1)
    for offset in range(days):
        insert_row(
            engine, "hr.attendance", employee_id=employee_id, attendance_date=start + timedelta(days=offset),
            source="Manual", status="Present",
        )


def test_zero_balances_stay_zero_until_generation_is_confirmed(settings: Settings) -> None:
    engine = sqlite_engine(TABLES)
    _office(engine)
    _employee(engine, 10, "EMP0010", date(2020, 1, 1))
    with _client(settings, engine) as client:
        board = client.get(BOARD, params={"year": 2027})
        assert board.status_code == 200, board.text
        body = board.json()
        assert body["summary"]["totalEmployees"] == 1
        assert body["summary"]["entitlementGenerated"] == 0
        assert body["items"][0]["el"]["balance"] == "0.0"
        assert body["items"][0]["employeeCode"] == "EMP0010"


def test_two_hundred_forty_days_credit_once_and_an_adjustment_is_audited(settings: Settings) -> None:
    engine = sqlite_engine(TABLES)
    _office(engine)
    _employee(engine, 10, "EMP0010", date(2020, 1, 1))
    _present(engine, 10, 240)
    with _client(settings, engine) as client:
        earned = client.post("/api/v1/hr/leave/types", json={"code": "EL", "name": "Earned Leave"}).json()
        sick = client.post("/api/v1/hr/leave/types", json={"code": "SL", "name": "Sick Leave"}).json()
        casual = client.post("/api/v1/hr/leave/types", json={"code": "CL", "name": "Casual Leave"}).json()
        policy = client.post(
            "/api/v1/hr/leave/policies",
            json={
                "name": "Odisha Private Company Leave Policy",
                "yearBasis": "CALENDAR",
                "assignmentMode": "EXPLICIT",
                "effectiveFrom": "2027-01-01",
                "lines": [
                    {
                        "leaveTypeId": earned["id"], "annualEntitlement": "0", "calculationMethod": "FORMULA",
                        "creditDays": "1", "qualifyingDaysPerCredit": 20, "minimumQualifyingDays": 240,
                        "joiningYearRule": "TWO_THIRDS_REMAINDER", "benefitClass": "STATUTORY",
                    },
                    {
                        "leaveTypeId": sick["id"], "annualEntitlement": "15", "calculationMethod": "ELIGIBILITY",
                        "minimumServiceMonths": 12, "benefitClass": "STATUTORY",
                    },
                    {
                        "leaveTypeId": casual["id"], "annualEntitlement": "7", "accrualFrequency": "Yearly",
                        "benefitClass": "COMPANY",
                    },
                ],
            },
        )
        assert policy.status_code == 201, policy.text
        policy_id = policy.json()["id"]
        assigned = client.post(
            f"/api/v1/hr/leave/policies/{policy_id}/assign",
            json={"employeeId": 10, "effectiveFrom": "2027-01-01"},
        )
        assert assigned.status_code == 201, assigned.text
        classified = client.put(
            "/api/v1/hr/leave/attendance-classes",
            json=[{
                "attendanceStatus": "Present", "countsForEligibility": True, "countsAsDaysWorked": True,
                "dayWeight": "1.0",
            }],
        )
        assert classified.status_code == 200, classified.text
        preview = client.post(f"{BOARD}/entitlement-preview", json={"policyId": policy_id, "year": 2027})
        assert preview.status_code == 200, preview.text
        lines = {row["code"]: row for row in preview.json()["employees"][0]["lines"]}
        assert lines["EL"]["credited"] == "12.0"
        assert lines["EL"]["daysWorked"] == "240.0"
        assert lines["SL"]["credited"] == "15.0"
        assert lines["CL"]["credited"] == "7.0"
        posted = client.post(f"{BOARD}/entitlements", json={"policyId": policy_id, "year": 2027})
        assert posted.status_code == 201, posted.text
        assert posted.json()["creditedEmployees"] == 1
        again = client.post(f"{BOARD}/entitlements", json={"policyId": policy_id, "year": 2027})
        assert again.json()["skippedDuplicates"] >= 1
        assert again.json()["creditedEmployees"] == 0
        board = client.get(BOARD, params={"year": 2027, "policyId": policy_id}).json()
        assert board["items"][0]["el"]["balance"] == "12.0"
        assert board["items"][0]["sl"]["balance"] == "15.0"
        assert board["summary"]["entitlementGenerated"] == 1
        adjusted = client.post(
            f"{BOARD}/10/adjustments",
            json={"leaveTypeId": earned["id"], "year": 2027, "days": "1.0", "reason": "Opening correction"},
        )
        assert adjusted.status_code == 200, adjusted.text
        earned_row = next(row for row in adjusted.json()["types"] if row["code"] == "EL")
        assert earned_row["closing"] == "13.0"
        assert earned_row["adjustments"] == "1.0"
        assert any(row["kind"] == "Adjustment" for row in adjusted.json()["transactions"])


def test_short_service_and_low_attendance_are_review_not_a_credit(settings: Settings) -> None:
    engine = sqlite_engine(TABLES)
    _office(engine)
    _employee(engine, 11, "EMP0011", date(2026, 8, 1))
    _present(engine, 11, 239)
    with _client(settings, engine) as client:
        earned = client.post("/api/v1/hr/leave/types", json={"code": "EL", "name": "Earned Leave"}).json()
        sick = client.post("/api/v1/hr/leave/types", json={"code": "SL", "name": "Sick Leave"}).json()
        policy = client.post(
            "/api/v1/hr/leave/policies",
            json={
                "name": "Review policy",
                "yearBasis": "CALENDAR",
                "assignmentMode": "EXPLICIT",
                "effectiveFrom": "2027-01-01",
                "lines": [
                    {
                        "leaveTypeId": earned["id"], "annualEntitlement": "0", "calculationMethod": "FORMULA",
                        "creditDays": "1", "qualifyingDaysPerCredit": 20, "minimumQualifyingDays": 240,
                    },
                    {
                        "leaveTypeId": sick["id"], "annualEntitlement": "15", "calculationMethod": "ELIGIBILITY",
                        "minimumServiceMonths": 12,
                    },
                ],
            },
        ).json()
        client.post(
            f"/api/v1/hr/leave/policies/{policy['id']}/assign",
            json={"employeeId": 11, "effectiveFrom": "2027-01-01"},
        )
        client.put(
            "/api/v1/hr/leave/attendance-classes",
            json=[{
                "attendanceStatus": "Present", "countsForEligibility": True, "countsAsDaysWorked": True,
                "dayWeight": "1",
            }],
        )
        preview = client.post(f"{BOARD}/entitlement-preview", json={"policyId": policy["id"], "year": 2027})
        assert preview.status_code == 200, preview.text
        person = preview.json()["employees"][0]
        lines = {row["code"]: row for row in person["lines"]}
        assert lines["EL"]["credited"] == "0.0"
        assert lines["SL"]["credited"] == "0.0"
        assert person["requiresReview"] is True
        posted = client.post(f"{BOARD}/entitlements", json={"policyId": policy["id"], "year": 2027})
        assert posted.json()["creditedEmployees"] == 0
        board = client.get(BOARD, params={"year": 2027}).json()
        assert board["items"][0]["el"]["balance"] == "0.0"


def test_an_inactive_policy_and_a_viewer_cannot_generate(settings: Settings) -> None:
    engine = sqlite_engine(TABLES)
    _office(engine)
    _employee(engine, 10, "EMP0010", date(2020, 1, 1))
    with _client(settings, engine) as client:
        leave_type = client.post("/api/v1/hr/leave/types", json={"code": "CL", "name": "Casual Leave"}).json()
        policy = client.post(
            "/api/v1/hr/leave/policies",
            json={
                "name": "Paused", "effectiveFrom": "2027-01-01", "isActive": False,
                "lines": [{"leaveTypeId": leave_type["id"], "annualEntitlement": "7"}],
            },
        ).json()
        refused = client.post(f"{BOARD}/entitlement-preview", json={"policyId": policy["id"], "year": 2027})
        assert refused.status_code == 400, refused.text
    with _client(settings, engine, manage=False) as client:
        refused = client.post(f"{BOARD}/entitlements", json={"policyId": 1, "year": 2027})
        assert refused.status_code == 403, refused.text
