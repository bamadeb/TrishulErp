"""TTPL leave approval: Reporting Manager is the sole final approver."""

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
from trishul_api.db.models import ApprovalRequest, LeaveBalance, LeaveRequest
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
    "hr.leave_request",
    "hr.employment_history",
    "hr.employee_shift",
    "hr.holiday",
]
ROOT = "/api/v1/hr/leave"
MINE = f"{ROOT}/mine"


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
    # Grand-manager (would have been Level 2 under the old chain)
    insert_row(
        engine,
        "core.employee",
        id=13,
        company_id=1,
        employee_code="EMP0013",
        first_name="Admin",
        last_name="Boss",
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
        id=12,
        company_id=1,
        employee_code="EMP0012",
        first_name="Mina",
        last_name="Rao",
        branch_id=1,
        department_id=1,
        designation_id=1,
        reporting_manager_id=13,
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
    insert_row(engine, "core.app_user", id=13, username="admin", email="admin@example.com", employee_id=13, is_active=True)
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
    return engine


def test_apply_snapshots_only_reporting_manager(settings: Settings, db: Engine) -> None:
    monday = _next_monday(date.today())
    with _client(settings, db, frozenset({"hr.leave.view", "hr.leave.apply"}), 10) as (client, _sign_in):
        created = client.post(
            f"{MINE}/requests",
            json={
                "leaveTypeId": 1,
                "fromDate": monday.isoformat(),
                "toDate": monday.isoformat(),
                "isHalfDay": False,
                "reason": "Personal work",
            },
        )
        assert created.status_code == 201, created.text
        request_id = created.json()["requestId"]
        detail = client.get(f"{MINE}/requests/{request_id}")
        assert detail.status_code == 200, detail.text
        steps = detail.json()["approvalSteps"]
        titles = [step["title"] for step in steps]
        assert titles == ["Request Submitted", "Reporting Manager", "Approved / Rejected"]
        assert steps[1]["status"] == "Pending"
        assert steps[1]["approverName"] == "Mina Rao"
        assert steps[2]["status"] == "Upcoming"
        with Session(db) as session:
            rows = session.scalars(
                select(ApprovalRequest).where(
                    ApprovalRequest.document_type == "LEAVE_REQUEST",
                    ApprovalRequest.document_id == request_id,
                    ApprovalRequest.is_active == True,  # noqa: E712
                )
            ).all()
            assert len(rows) == 1
            assert rows[0].approval_level == 1
            assert rows[0].approver_user_id == 12


def test_reporting_manager_approve_finalizes_and_deducts(settings: Settings, db: Engine) -> None:
    monday = _next_monday(date.today())
    year = monday.year if monday.month >= 4 else monday.year - 1
    with _client(settings, db, frozenset({"hr.leave.view", "hr.leave.apply"}), 10) as (client, sign_in):
        created = client.post(
            f"{MINE}/requests",
            json={
                "leaveTypeId": 1,
                "fromDate": monday.isoformat(),
                "toDate": monday.isoformat(),
                "isHalfDay": False,
                "reason": "Personal work",
            },
        )
        assert created.status_code == 201, created.text
        request_id = created.json()["requestId"]

        sign_in(12, frozenset({"hr.leave.approve"}))
        approved = client.post(f"{ROOT}/requests/{request_id}/approve")
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "Approved"

        sign_in(10, frozenset({"hr.leave.view", "hr.leave.apply"}))
        detail = client.get(f"{MINE}/requests/{request_id}")
        titles = [step["title"] for step in detail.json()["approvalSteps"]]
        assert titles == ["Request Submitted", "Reporting Manager", "Approved"]
        assert detail.json()["approvalSteps"][1]["status"] == "Approved"
        assert detail.json()["approvalSteps"][2]["status"] == "Approved"

        with Session(db) as session:
            balance = session.scalar(
                select(LeaveBalance).where(
                    LeaveBalance.employee_id == 10,
                    LeaveBalance.leave_type_id == 1,
                    LeaveBalance.leave_year == year,
                )
            )
            assert balance is not None
            assert balance.availed == Decimal("1.0")
            assert balance.closing == Decimal("4.0")


def test_reporting_manager_reject_keeps_comments(settings: Settings, db: Engine) -> None:
    monday = _next_monday(date.today())
    with _client(settings, db, frozenset({"hr.leave.view", "hr.leave.apply"}), 10) as (client, sign_in):
        created = client.post(
            f"{MINE}/requests",
            json={
                "leaveTypeId": 1,
                "fromDate": monday.isoformat(),
                "toDate": monday.isoformat(),
                "isHalfDay": False,
                "reason": "Personal work",
            },
        )
        request_id = created.json()["requestId"]

        sign_in(12, frozenset({"hr.leave.approve"}))
        rejected = client.post(
            f"{ROOT}/requests/{request_id}/reject",
            json={"remarks": "Plan coverage first"},
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "Rejected"

        sign_in(10, frozenset({"hr.leave.view", "hr.leave.apply"}))
        detail = client.get(f"{MINE}/requests/{request_id}")
        steps = detail.json()["approvalSteps"]
        assert [step["title"] for step in steps] == ["Request Submitted", "Reporting Manager", "Rejected"]
        assert steps[1]["status"] == "Rejected"
        assert steps[1]["comments"] == "Plan coverage first"
        with Session(db) as session:
            row = session.get(LeaveRequest, request_id)
            assert row is not None and row.status == "Rejected"


def test_old_multi_level_pending_finalizes_on_rm_approve(settings: Settings, db: Engine) -> None:
    monday = _next_monday(date.today())
    year = monday.year if monday.month >= 4 else monday.year - 1
    now = datetime.now(UTC).replace(tzinfo=None)
    insert_row(
        db,
        "hr.leave_request",
        id=90,
        employee_id=10,
        leave_type_id=1,
        from_date=monday,
        to_date=monday,
        days="1.0",
        status="Pending",
        reason="Legacy multi-level",
        is_active=True,
        created_by_user_id=10,
    )
    insert_row(
        db,
        "core.approval_request",
        document_type="LEAVE_REQUEST",
        document_id=90,
        approval_level=1,
        requested_by_user_id=10,
        requested_at=now,
        approver_user_id=12,
        status="Pending",
        created_at=now,
        created_by_user_id=10,
        is_active=True,
    )
    insert_row(
        db,
        "core.approval_request",
        document_type="LEAVE_REQUEST",
        document_id=90,
        approval_level=2,
        requested_by_user_id=10,
        requested_at=now,
        approver_user_id=13,
        status="Pending",
        created_at=now,
        created_by_user_id=10,
        is_active=True,
    )

    with _client(settings, db, frozenset({"hr.leave.approve"}), 12) as (client, _sign_in):
        approved = client.post(f"{ROOT}/requests/90/approve")
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "Approved"
        with Session(db) as session:
            steps = session.scalars(
                select(ApprovalRequest).where(
                    ApprovalRequest.document_type == "LEAVE_REQUEST",
                    ApprovalRequest.document_id == 90,
                )
            ).all()
            by_level = {step.approval_level: step.status for step in steps}
            assert by_level[1] == "Approved"
            assert by_level[2] == "Cancelled"
            balance = session.scalar(
                select(LeaveBalance).where(
                    LeaveBalance.employee_id == 10,
                    LeaveBalance.leave_year == year,
                )
            )
            assert balance is not None
            assert balance.availed == Decimal("1.0")


def _next_monday(day: date) -> date:
    return day + timedelta(days=(7 - day.weekday()) % 7 or 7)


@contextmanager
def _client(
    settings: Settings, db: Engine, permissions: frozenset[str], employee_id: int
) -> Iterator[tuple[TestClient, object]]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    current = {
        "user": make_user(id=employee_id, employee_id=employee_id, permissions=permissions),
    }
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
