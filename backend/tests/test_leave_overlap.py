"""Centralized leave overlap and duplicate validation."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import LeaveBalance, LeaveRequest
from trishul_api.main import create_app
from trishul_api.modules.hr.leave.overlap import conflict_message

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
    "hr.leave_request",
    "hr.employment_history",
    "hr.employee_shift",
    "hr.holiday",
]
MINE = "/api/v1/hr/leave/mine"
REQUESTS = "/api/v1/hr/leave/requests"


@dataclass
class _Span:
    id: int
    leave_type_id: int
    from_date: date
    to_date: date
    is_half_day: bool
    status: str
    days: Decimal


def test_conflict_message_allows_complementary_half_days() -> None:
    day = date(2026, 12, 7)
    existing = [
        _Span(1, 1, day, day, True, "Pending", Decimal("0.5")),
    ]
    assert (
        conflict_message(
            leave_type_id=1,
            from_date=day,
            to_date=day,
            is_half_day=True,
            existing=existing,
            type_names={1: "Casual Leave"},
        )
        is None
    )


def test_conflict_message_blocks_third_half_day_and_full_day() -> None:
    day = date(2026, 12, 7)
    existing = [
        _Span(1, 1, day, day, True, "Pending", Decimal("0.5")),
        _Span(2, 2, day, day, True, "Approved", Decimal("0.5")),
    ]
    message = conflict_message(
        leave_type_id=1,
        from_date=day,
        to_date=day,
        is_half_day=True,
        existing=existing,
        type_names={1: "Casual Leave", 2: "Annual Leave"},
    )
    assert message is not None
    assert "Overlapping leave" in message
    assert "07-Dec-2026" in message

    full = conflict_message(
        leave_type_id=1,
        from_date=day,
        to_date=day,
        is_half_day=False,
        existing=existing[:1],
        type_names={1: "Casual Leave"},
    )
    assert full is not None
    assert "LV-0001" in full


def test_conflict_message_ignores_rejected_and_cancelled() -> None:
    day = date(2026, 12, 7)
    existing = [
        _Span(1, 1, day, day, False, "Rejected", Decimal("1.0")),
        _Span(2, 1, day, day, False, "Cancelled", Decimal("1.0")),
    ]
    assert (
        conflict_message(
            leave_type_id=1,
            from_date=day,
            to_date=day,
            is_half_day=False,
            existing=existing,
            type_names={1: "Casual Leave"},
        )
        is None
    )


def test_conflict_message_duplicate_exact_match() -> None:
    day = date(2026, 12, 7)
    existing = [_Span(9, 1, day, day, False, "Pending", Decimal("1.0"))]
    message = conflict_message(
        leave_type_id=1,
        from_date=day,
        to_date=day,
        is_half_day=False,
        existing=existing,
        type_names={1: "Casual Leave"},
    )
    assert message is not None
    assert message.startswith("Duplicate submission")
    assert "LV-0009" in message


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    monday = _next_monday(date.today())
    year = monday.year if monday.month >= 4 else monday.year - 1
    insert_row(engine, "core.company", id=1, code="TT", legal_name="Trishul")
    insert_row(engine, "core.region", id=1, code="OD", name="Odisha", warehouse_id=1)
    insert_row(engine, "core.branch", id=1, company_id=1, code="BAM", name="Berhampur", region_id=1, state_id=1)
    insert_row(engine, "hr.department", id=1, code="SVC", name="Service")
    insert_row(engine, "hr.designation", id=1, code="SE", name="Service Engineer", department_id=1)
    insert_row(engine, "hr.leave_type", id=1, code="CL", name="Casual Leave", is_paid=True, is_active=True)
    insert_row(engine, "hr.leave_type", id=2, code="AL", name="Annual Leave", is_paid=True, is_active=True)
    insert_row(
        engine,
        "hr.leave_policy",
        id=1,
        name="Staff",
        applies_during_probation=True,
        is_active=True,
        effective_from=date(year, 4, 1),
    )
    insert_row(
        engine,
        "hr.leave_policy_line",
        leave_policy_id=1,
        leave_type_id=1,
        annual_entitlement="12.0",
        accrual_frequency="Yearly",
        is_active=True,
    )
    insert_row(
        engine,
        "hr.leave_policy_line",
        leave_policy_id=1,
        leave_type_id=2,
        annual_entitlement="15.0",
        accrual_frequency="Yearly",
        is_active=True,
        exclude_boundary_holidays=False,
    )
    insert_row(
        engine,
        "core.employee",
        id=12,
        company_id=1,
        employee_code="EMP0012",
        first_name="Mina",
        last_name="Rao",
        branch_id=1,
        department_id=1,
        designation_id=1,
        employee_type="Permanent",
        status="Active",
        is_active=True,
    )
    insert_row(
        engine,
        "core.employee",
        id=10,
        company_id=1,
        employee_code="EMP0010",
        first_name="Asha",
        last_name="Das",
        branch_id=1,
        department_id=1,
        designation_id=1,
        reporting_manager_id=12,
        employee_type="Permanent",
        status="Active",
        is_active=True,
        date_of_joining=date(2019, 4, 15),
    )
    insert_row(engine, "core.app_user", id=10, username="asha", email="asha@example.com", employee_id=10, is_active=True)
    insert_row(engine, "core.app_user", id=12, username="mina", email="mina@example.com", employee_id=12, is_active=True)
    insert_row(
        engine,
        "hr.leave_balance",
        employee_id=10,
        leave_type_id=1,
        leave_year=year,
        opening="5.0",
        accrued="0",
        availed="0",
        encashed="0",
        closing="5.0",
        is_active=True,
    )
    insert_row(
        engine,
        "hr.leave_balance",
        employee_id=10,
        leave_type_id=2,
        leave_year=year,
        opening="15.0",
        accrued="0",
        availed="0",
        encashed="0",
        closing="15.0",
        is_active=True,
    )
    return engine


def test_api_allows_reapply_after_reject_and_blocks_partial_overlap(settings: Settings, db: Engine) -> None:
    monday = _next_monday(date.today())
    tuesday = monday + timedelta(days=1)
    with _client(settings, db, frozenset({"hr.leave.view", "hr.leave.apply"}), 10) as (client, sign_in):
        first = client.post(f"{MINE}/requests", json=_leave(1, monday, "First"))
        assert first.status_code == 201, first.text
        request_id = first.json()["requestId"]

        sign_in(12, frozenset({"hr.leave.approve"}))
        rejected = client.post(f"{REQUESTS}/{request_id}/reject", json={"remarks": "Reschedule"})
        assert rejected.status_code == 200, rejected.text

        sign_in(10, frozenset({"hr.leave.view", "hr.leave.apply"}))
        reapply = client.post(f"{MINE}/requests", json=_leave(1, monday, "Retry after reject"))
        assert reapply.status_code == 201, reapply.text
        second_id = reapply.json()["requestId"]

        week_start = monday + timedelta(days=7)
        range_leave = client.post(
            f"{MINE}/requests",
            json=_leave(1, week_start, "Week", to_date=week_start + timedelta(days=2)),
        )
        assert range_leave.status_code == 201, range_leave.text

        partial = client.post(
            f"{MINE}/requests",
            json=_leave(1, week_start + timedelta(days=1), "Partial", to_date=week_start + timedelta(days=3)),
        )
        assert partial.status_code == 400
        assert "Overlapping leave" in partial.json()["detail"]
        assert "LV-" in partial.json()["detail"]

        sign_in(12, frozenset({"hr.leave.approve"}))
        approved = client.post(f"{REQUESTS}/{second_id}/approve")
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "Approved"

        # Concurrent conflict at approval: a second pending on same day should block finalize.
        sign_in(10, frozenset({"hr.leave.view", "hr.leave.apply"}))
        competing = client.post(f"{MINE}/requests", json=_leave(1, tuesday, "Competing"))
        assert competing.status_code == 201, competing.text
        competing_id = competing.json()["requestId"]

        # Seed another approved leave on tuesday via direct insert, then revalidate approve.
        insert_row(
            db,
            "hr.leave_request",
            id=500,
            employee_id=10,
            leave_type_id=1,
            from_date=tuesday,
            to_date=tuesday,
            is_half_day=False,
            days="1.0",
            status="Approved",
            reason="Already approved",
            is_active=True,
            created_by_user_id=10,
            acted_at=datetime.now(UTC).replace(tzinfo=None),
            approver_user_id=12,
        )
        sign_in(12, frozenset({"hr.leave.approve"}))
        blocked = client.post(f"{REQUESTS}/{competing_id}/approve")
        assert blocked.status_code == 400
        detail = blocked.json()["detail"]
        assert "Duplicate submission" in detail or "Overlapping leave" in detail

        with Session(db) as session:
            pending = session.get(LeaveRequest, competing_id)
            assert pending is not None and pending.status == "Pending"
            balance = session.scalar(
                select(LeaveBalance).where(LeaveBalance.employee_id == 10, LeaveBalance.leave_type_id == 1)
            )
            assert balance is not None
            # Only the approved monday request deducted once.
            assert balance.availed == Decimal("1.0")


def test_api_allows_two_half_days_same_date(settings: Settings, db: Engine) -> None:
    monday = _next_monday(date.today())
    with _client(settings, db, frozenset({"hr.leave.view", "hr.leave.apply"}), 10) as (client, _sign_in):
        first = client.post(
            f"{MINE}/requests",
            json={
                "leaveTypeId": 1,
                "fromDate": monday.isoformat(),
                "toDate": monday.isoformat(),
                "isHalfDay": True,
                "halfDayPart": "First half",
                "reason": "Morning leave",
            },
        )
        assert first.status_code == 201, first.text
        second = client.post(
            f"{MINE}/requests",
            json={
                "leaveTypeId": 1,
                "fromDate": monday.isoformat(),
                "toDate": monday.isoformat(),
                "isHalfDay": True,
                "halfDayPart": "Second half",
                "reason": "Afternoon leave",
            },
        )
        assert second.status_code == 201, second.text
        third = client.post(
            f"{MINE}/requests",
            json={
                "leaveTypeId": 1,
                "fromDate": monday.isoformat(),
                "toDate": monday.isoformat(),
                "isHalfDay": True,
                "halfDayPart": "First half",
                "reason": "Too much",
            },
        )
        assert third.status_code == 400
        assert "Overlapping leave" in third.json()["detail"]


def test_day_count_blocks_conflict_and_excludes_own_request(settings: Settings, db: Engine) -> None:
    monday = _next_monday(date.today())
    with _client(settings, db, frozenset({"hr.leave.view", "hr.leave.apply"}), 10) as (client, _sign_in):
        created = client.post(f"{MINE}/requests", json=_leave(1, monday, "Booked"))
        assert created.status_code == 201, created.text
        request_id = created.json()["requestId"]

        blocked = client.post(
            f"{MINE}/day-count",
            json={
                "leaveTypeId": 2,
                "fromDate": monday.isoformat(),
                "toDate": monday.isoformat(),
                "isHalfDay": False,
            },
        )
        assert blocked.status_code == 400
        assert "Overlapping leave" in blocked.json()["detail"]
        assert f"LV-{request_id:04d}" in blocked.json()["detail"]

        allowed = client.post(
            f"{MINE}/day-count",
            json={
                "leaveTypeId": 1,
                "fromDate": monday.isoformat(),
                "toDate": monday.isoformat(),
                "isHalfDay": False,
                "excludeRequestId": request_id,
            },
        )
        assert allowed.status_code == 200, allowed.text
        assert Decimal(allowed.json()["days"]) == Decimal("1.0")

        foreign = client.post(
            f"{MINE}/day-count",
            json={
                "leaveTypeId": 1,
                "fromDate": monday.isoformat(),
                "toDate": monday.isoformat(),
                "isHalfDay": False,
                "excludeRequestId": 99999,
            },
        )
        assert foreign.status_code == 404


def _leave(leave_type_id: int, day: date, reason: str, to_date: date | None = None) -> dict[str, object]:
    end = to_date or day
    return {
        "leaveTypeId": leave_type_id,
        "fromDate": day.isoformat(),
        "toDate": end.isoformat(),
        "isHalfDay": False,
        "reason": reason,
    }


def _next_monday(day: date) -> date:
    return day + timedelta(days=(7 - day.weekday()) % 7 or 7)


@contextmanager
def _client(
    settings: Settings, db: Engine, permissions: frozenset[str], employee_id: int
) -> Iterator[tuple[TestClient, object]]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    current = {"user": make_user(id=employee_id, employee_id=employee_id, permissions=permissions)}
    api.dependency_overrides[get_current_user] = lambda: current["user"]

    def sign_in(next_employee_id: int, next_permissions: frozenset[str]) -> None:
        current["user"] = make_user(
            id=next_employee_id, employee_id=next_employee_id, permissions=next_permissions
        )

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current_session:
            set_audit_context(
                current_session, user_id=current["user"].id, source="Web", ip_address="127.0.0.1"
            )
            yield current_session

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client, sign_in
