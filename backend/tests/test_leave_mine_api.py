"""My Leave uses the signed-in employee and the existing leave tables."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import LeaveBalance, LeavePolicy, LeavePolicyLine, LeaveRequest
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "core.region",
    "core.employee",
    "core.app_user",
    "core.approval_request",
    "core.status_history",
    "hr.department",
    "hr.designation",
    "hr.leave_type",
    "hr.leave_type_setting",
    "hr.leave_policy",
    "hr.leave_policy_line",
    "hr.leave_policy_assignment",
    "hr.leave_balance",
    "hr.leave_balance_transaction",
    "hr.leave_request",
    "hr.employment_history",
    "hr.employee_shift",
    "hr.holiday",
]
ROOT = "/api/v1/hr/leave/mine"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    monday = _next_monday(date.today())
    year = monday.year if monday.month >= 4 else monday.year - 1
    insert_row(engine, "core.company", id=1, code="TT", legal_name="Trishul")
    insert_row(engine, "core.region", id=1, code="OD", name="Odisha", warehouse_id=1)
    insert_row(engine, "core.branch", id=1, company_id=1, code="BAM", name="Berhampur", region_id=1, state_id=1)
    insert_row(engine, "hr.department", id=1, code="SVC", name="Service")
    insert_row(engine, "hr.designation", id=1, code="SSE", name="Senior Software Engineer", department_id=1)
    insert_row(engine, "hr.leave_type", id=1, code="CL", name="Casual Leave", is_paid=True, is_active=True)
    insert_row(engine, "hr.leave_type", id=2, code="LWP", name="Leave Without Pay", is_paid=False, is_active=True)
    insert_row(
        engine, "hr.leave_policy", id=1, name="Staff", applies_during_probation=True, is_active=True,
        effective_from=date(year, 4, 1),
    )
    insert_row(
        engine, "hr.leave_policy_line", leave_policy_id=1, leave_type_id=1, annual_entitlement="12.0",
        accrual_frequency="Yearly", is_active=True,
    )
    insert_row(
        engine, "hr.leave_policy_line", leave_policy_id=1, leave_type_id=2, annual_entitlement="0",
        accrual_frequency="None", is_active=True,
    )
    insert_row(
        engine, "core.employee", id=12, company_id=1, employee_code="EMP0012", first_name="Mina", last_name="Rao",
        branch_id=1, department_id=1, designation_id=1, employee_type="Permanent", status="Active", is_active=True,
    )
    insert_row(
        engine, "core.employee", id=10, company_id=1, employee_code="EMP0010", first_name="Asha", last_name="Das",
        branch_id=1, department_id=1, designation_id=1, reporting_manager_id=12, employee_type="Permanent",
        status="Active", is_active=True, date_of_joining=date(2019, 4, 15),
    )
    insert_row(
        engine, "core.employee", id=11, company_id=1, employee_code="EMP0011", first_name="Bikash", last_name="Naik",
        branch_id=1, department_id=1, employee_type="Permanent", status="Active", is_active=True,
    )
    insert_row(
        engine, "core.app_user", id=12, username="mina", email="mina@example.com", employee_id=12, is_active=True,
    )
    insert_row(
        engine, "hr.leave_balance", employee_id=10, leave_type_id=1, leave_year=year,
        opening="5.0", accrued="0", availed="0", encashed="0", closing="5.0", is_active=True,
    )
    insert_row(
        engine, "hr.holiday", branch_id=1, holiday_date=monday + timedelta(days=2), name="Office holiday",
        holiday_type="National", is_active=True,
    )
    insert_row(
        engine, "hr.leave_request", id=80, employee_id=11, leave_type_id=1, from_date=monday, to_date=monday,
        days="1.0", status="Pending", reason="Other person", is_active=True,
    )
    return engine


def test_profile_balances_and_apply_do_not_deduct_pending(settings: Settings, db: Engine) -> None:
    monday = _next_monday(date.today())
    year = monday.year if monday.month >= 4 else monday.year - 1
    with _client(settings, db, frozenset({"hr.leave.view", "hr.leave.apply"}), 10) as client:
        profile = client.get(f"{ROOT}/profile")
        assert profile.status_code == 200, profile.text
        assert profile.json()["employeeCode"] == "EMP0010"
        assert profile.json()["location"] == "Berhampur"
        assert profile.json()["employmentStatus"] == "Active"
        assert profile.json()["confirmationDate"] is None

        balances = client.get(f"{ROOT}/balances", params={"financialYear": year})
        assert balances.status_code == 200, balances.text
        casual = next(row for row in balances.json()["items"] if row["code"] == "CL")
        assert Decimal(casual["available"]) == Decimal("5.0")
        assert Decimal(casual["pending"]) == Decimal("0")
        assert casual["expired"] is None

        counted = client.post(
            f"{ROOT}/day-count",
            json={"leaveTypeId": 1, "fromDate": monday.isoformat(), "toDate": monday.isoformat(), "isHalfDay": False},
        )
        assert counted.status_code == 200, counted.text
        assert Decimal(counted.json()["days"]) == Decimal("1.0")
        half = client.post(
            f"{ROOT}/day-count",
            json={
                "leaveTypeId": 1,
                "fromDate": monday.isoformat(),
                "toDate": monday.isoformat(),
                "isHalfDay": True,
                "halfDayPart": "First half",
            },
        )
        assert half.status_code == 200, half.text
        assert Decimal(half.json()["days"]) == Decimal("0.5")

        created = client.post(f"{ROOT}/requests", json=_leave(1, monday, "Personal work"))
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["status"] == "Pending"
        assert Decimal(body["days"]) == Decimal("1.0")
        assert body["displayId"] == f"LV-{body['requestId']:04d}"
        request_id = body["requestId"]

        again = client.get(f"{ROOT}/balances", params={"financialYear": year})
        casual = next(row for row in again.json()["items"] if row["code"] == "CL")
        assert Decimal(casual["available"]) == Decimal("5.0")
        assert Decimal(casual["pending"]) == Decimal("1.0")

        duplicate = client.post(f"{ROOT}/requests", json=_leave(1, monday, "Again"))
        assert duplicate.status_code == 400
        assert "Duplicate submission" in duplicate.json()["detail"]

        overlap = client.post(
            f"{ROOT}/requests", json=_leave(1, monday, "Overlap", to_date=monday + timedelta(days=1))
        )
        assert overlap.status_code == 400
        assert "Overlapping leave" in overlap.json()["detail"]

        preview_conflict = client.post(
            f"{ROOT}/day-count",
            json={"leaveTypeId": 1, "fromDate": monday.isoformat(), "toDate": monday.isoformat(), "isHalfDay": False},
        )
        assert preview_conflict.status_code == 400
        detail = preview_conflict.json()["detail"]
        assert "Duplicate submission" in detail or "Overlapping leave" in detail

        sunday = monday - timedelta(days=1)
        weekend = client.post(f"{ROOT}/requests", json=_leave(1, sunday, "Sunday"))
        assert weekend.status_code == 400

        holiday = client.post(f"{ROOT}/requests", json=_leave(1, monday + timedelta(days=2), "Holiday"))
        assert holiday.status_code == 400

        listed = client.get(f"{ROOT}/requests", params={"financialYear": year, "search": "personal"})
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["requestId"] == request_id

        hidden = client.get(f"{ROOT}/requests/80")
        assert hidden.status_code == 404

        cancelled = client.post(f"{ROOT}/requests/{request_id}/cancel")
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "Cancelled"
        assert cancelled.json()["history"][-1]["toStatus"] == "Cancelled"

        closing, availed = _balance(db, 10, 1, year)
        assert closing == Decimal("5.0")
        assert availed == Decimal("0")


def test_approved_cancel_restores_the_balance_once(settings: Settings, db: Engine) -> None:
    monday = _next_monday(date.today())
    year = monday.year if monday.month >= 4 else monday.year - 1
    with Session(db) as session:
        balance = session.scalar(
            select(LeaveBalance).where(LeaveBalance.employee_id == 10, LeaveBalance.leave_type_id == 1)
        )
        assert balance is not None
        balance.availed = Decimal("1.0")
        balance.closing = Decimal("4.0")
        session.add(
            LeaveRequest(
                employee_id=10, leave_type_id=1, from_date=monday + timedelta(days=7),
                to_date=monday + timedelta(days=7), days=Decimal("1.0"), status="Approved",
                reason="Approved", is_active=True, created_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        session.commit()
        request_id = session.scalar(select(LeaveRequest.id).where(LeaveRequest.status == "Approved"))
    with _client(settings, db, frozenset({"hr.leave.apply"}), 10) as client:
        refused = client.post(f"{ROOT}/requests/{request_id}/cancel")
        assert refused.status_code == 403
        client.app.state.api_v1.dependency_overrides[get_current_user] = lambda: make_user(
            id=1, employee_id=10, permissions=frozenset({"hr.leave.apply", "hr.leave.manage"})
        )
        cancelled = client.post(f"{ROOT}/requests/{request_id}/cancel")
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "Cancelled"
        closing, availed = _balance(db, 10, 1, year)
        assert availed == Decimal("0")
        assert closing == Decimal("5.0")


def test_unconfirmed_employee_and_missing_link_are_rejected(settings: Settings, db: Engine) -> None:
    monday = _next_monday(date.today())
    with Session(db) as session:
        policy = session.get(LeavePolicy, 1)
        assert policy is not None
        policy.applies_during_probation = False
        session.commit()
    with _client(settings, db, frozenset({"hr.leave.apply"}), 10) as client:
        refused = client.post(f"{ROOT}/requests", json=_leave(1, monday + timedelta(days=8), "Later"))
        assert refused.status_code == 400
        assert refused.json()["detail"] == "Employee not confirmed."
    with _client(settings, db, frozenset({"hr.leave.view"}), None) as client:
        assert client.get(f"{ROOT}/profile").status_code == 404
    with _client(settings, db, frozenset(), 10) as client:
        assert client.get(f"{ROOT}/profile").status_code == 403


def test_backdate_follows_the_policy_line(settings: Settings, db: Engine) -> None:
    past = date.today() - timedelta(days=date.today().weekday() + 7)
    with Session(db) as session:
        casual = session.scalar(select(LeavePolicyLine).where(LeavePolicyLine.leave_type_id == 1))
        unpaid = session.scalar(select(LeavePolicyLine).where(LeavePolicyLine.leave_type_id == 2))
        assert casual is not None and unpaid is not None
        casual.max_backdate_days = 0
        unpaid.max_backdate_days = 0
        unpaid.backdate_requires_authorization = True
        session.commit()
    with _client(settings, db, frozenset({"hr.leave.apply"}), 10) as client:
        rejected = client.post(f"{ROOT}/requests", json=_leave(1, past, "Too early"))
        assert rejected.status_code == 400
        assert rejected.json()["detail"] == "This leave type cannot start before today."
        counted = client.post(
            f"{ROOT}/day-count",
            json={"leaveTypeId": 1, "fromDate": past.isoformat(), "toDate": past.isoformat(), "isHalfDay": False},
        )
        assert counted.status_code == 400
        assert counted.json()["detail"] == "This leave type cannot start before today."
        authorized = client.post(f"{ROOT}/requests", json=_leave(2, past, "Needs HR"))
        assert authorized.status_code == 400
        assert authorized.json()["detail"] == "Past dates for this leave type require HR authorization."


def test_hr_can_authorize_a_past_unpaid_date(settings: Settings, db: Engine) -> None:
    past = date.today() - timedelta(days=date.today().weekday() + 7)
    with Session(db) as session:
        unpaid = session.scalar(select(LeavePolicyLine).where(LeavePolicyLine.leave_type_id == 2))
        assert unpaid is not None
        unpaid.max_backdate_days = 0
        unpaid.backdate_requires_authorization = True
        session.commit()
    with _client(settings, db, frozenset({"hr.leave.apply", "hr.leave.manage"}), 10) as client:
        created = client.post(f"{ROOT}/requests", json=_leave(2, past, "HR authorized"))
        assert created.status_code == 201, created.text


def _leave(leave_type_id: int, day: date, reason: str, to_date: date | None = None) -> dict[str, object]:
    return {
        "leaveTypeId": leave_type_id,
        "fromDate": day.isoformat(),
        "toDate": (to_date or day).isoformat(),
        "isHalfDay": False,
        "reason": reason,
    }


def _next_monday(today: date) -> date:
    return today + timedelta(days=(7 - today.weekday()) % 7)


def _balance(engine: Engine, employee_id: int, leave_type_id: int, year: int) -> tuple[Decimal, Decimal]:
    with Session(engine) as session:
        row = session.scalar(
            select(LeaveBalance).where(
                LeaveBalance.employee_id == employee_id,
                LeaveBalance.leave_type_id == leave_type_id,
                LeaveBalance.leave_year == year,
            )
        )
        assert row is not None
        return row.closing, row.availed


@contextmanager
def _client(
    settings: Settings, db: Engine, permissions: frozenset[str], employee_id: int | None
) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    api.dependency_overrides[get_current_user] = lambda: make_user(
        id=1, employee_id=employee_id, permissions=permissions
    )

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current:
            set_audit_context(current, user_id=1, source="Web", ip_address="127.0.0.1")
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
