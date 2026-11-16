"""Odisha policy configuration. Credits are calculated, not written onto balances."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import Employee, LeaveBalance, LeavePolicy
from trishul_api.main import create_app
from trishul_api.modules.hr.leave.calculation import add_calendar_months, earned_leave_days
from trishul_api.modules.hr.leave.mine_repository import _policy_fits

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.app_user",
    "core.company",
    "core.region",
    "core.branch",
    "core.employee",
    "hr.department",
    "hr.leave_type",
    "hr.leave_type_setting",
    "hr.leave_policy",
    "hr.leave_policy_line",
    "hr.leave_policy_assignment",
    "hr.leave_balance",
    "hr.attendance",
    "hr.leave_attendance_class",
    "hr.leave_weekly_rest_grant",
]
POLICIES = "/api/v1/hr/leave/policies"
_ONE = Decimal("1")
_TWENTY = 20


def _credit(eligibility: str, worked: str, joining: date | None = None, rule: str = "NONE") -> Decimal:
    return earned_leave_days(
        eligibility_days=Decimal(eligibility),
        days_worked=Decimal(worked),
        credit_days=_ONE,
        per_days=_TWENTY,
        minimum_qualifying_days=240,
        joining=joining,
        attendance_year=2025,
        joining_rule=rule,
    )


def test_earned_leave_uses_the_240_day_test_and_counts_deemed_days_apart_from_work() -> None:
    assert _credit("239", "239") == Decimal("0.0")
    assert _credit("240", "240") == Decimal("12.0")
    assert _credit("240", "200") == Decimal("10.0")
    joined = date(2025, 7, 1)
    assert _credit("122", "122", joined, "TWO_THIRDS_REMAINDER") == Decimal("0.0")
    assert _credit("123", "123", joined, "TWO_THIRDS_REMAINDER") == Decimal("6.0")


def test_weekly_rest_deadline_is_three_calendar_months() -> None:
    assert add_calendar_months(date(2026, 1, 31), 3) == date(2026, 4, 30)


def test_an_explicit_policy_does_not_match_by_group_or_location() -> None:
    policy = LeavePolicy(
        assignment_mode="EXPLICIT", employee_type=None, department_id=None, branch_id=None, state_id=None
    )
    employee = Employee(employee_type="Permanent", department_id=1, branch_id=1)
    assert _policy_fits(policy, employee, 1) is False


@contextmanager
def _client(settings: Settings, engine: Engine) -> Iterator[TestClient]:
    app = create_app(settings, engine=engine)
    api = app.state.api_v1
    api.dependency_overrides[get_current_user] = lambda: make_user(
        id=1, permissions=frozenset({"hr.leave.view", "hr.leave.manage"})
    )

    def session() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as current:
            set_audit_context(current, user_id=1, source="Web", ip_address="127.0.0.1")
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_fixed_policies_keep_their_defaults_and_formula_rejects_a_typed_day_count(settings: Settings) -> None:
    engine = sqlite_engine(TABLES)
    with _client(settings, engine) as client:
        leave_type = client.post("/api/v1/hr/leave/types", json={"code": "EL", "name": "Earned Leave"}).json()
        fixed = client.post(
            POLICIES,
            json={
                "name": "Existing",
                "effectiveFrom": "2026-04-01",
                "lines": [{"leaveTypeId": leave_type["id"], "annualEntitlement": "8.0", "accrualFrequency": "Yearly"}],
            },
        )
        assert fixed.status_code == 201, fixed.text
        saved = fixed.json()
        assert saved["yearBasis"] == "FINANCIAL"
        assert saved["assignmentMode"] == "AUTOMATIC"
        assert saved["lines"][0]["calculationMethod"] == "FIXED"
        refused = client.post(
            POLICIES,
            json={
                "name": "Flat twelve",
                "effectiveFrom": "2027-01-01",
                "lines": [{
                    "leaveTypeId": leave_type["id"],
                    "annualEntitlement": "12.0",
                    "calculationMethod": "FORMULA",
                    "creditDays": "1",
                    "qualifyingDaysPerCredit": 20,
                    "minimumQualifyingDays": 240,
                }],
            },
        )
        assert refused.status_code == 422, refused.text


def test_an_inactive_explicit_policy_is_not_assigned_and_creates_no_balance(settings: Settings) -> None:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=1, code="TT", legal_name="Trishul")
    insert_row(engine, "core.region", id=1, code="OD", name="Odisha", warehouse_id=1)
    insert_row(engine, "core.branch", id=1, company_id=1, code="BAM", name="Berhampur", region_id=1, state_id=1)
    insert_row(
        engine, "core.employee", id=10, company_id=1, employee_code="EMP0010", first_name="Asha", last_name="Das",
        branch_id=1, status="Active", is_active=True,
    )
    with _client(settings, engine) as client:
        leave_type = client.post("/api/v1/hr/leave/types", json={"code": "SL", "name": "Sick Leave"}).json()
        created = client.post(
            POLICIES,
            json={
                "name": "Odisha Private Company Leave Policy",
                "yearBasis": "CALENDAR",
                "assignmentMode": "EXPLICIT",
                "isActive": False,
                "effectiveFrom": "2027-01-01",
                "lines": [{
                    "leaveTypeId": leave_type["id"],
                    "annualEntitlement": "15.0",
                    "calculationMethod": "ELIGIBILITY",
                    "minimumServiceMonths": 12,
                    "benefitClass": "STATUTORY",
                    "documentRequired": True,
                }],
            },
        )
        assert created.status_code == 201, created.text
        policy_id = created.json()["id"]
        assigned = client.post(
            f"{POLICIES}/{policy_id}/assign",
            json={"employeeId": 10, "effectiveFrom": "2027-01-01"},
        )
        assert assigned.status_code == 400, assigned.text
        assert client.get(f"{POLICIES}/{policy_id}/assignments").json() == []
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(LeaveBalance)) == 0
