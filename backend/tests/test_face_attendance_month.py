"""GET /hr/attendance/me/month: the employee's own calendar, with the same day status as Daily Attendance."""

from collections.abc import Iterator
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.main import create_app
from trishul_api.modules.hr.face_attendance.rules import IST_OFFSET, india_date
from trishul_api.modules.hr.face_attendance.service import utc_now

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "hr.department",
    "core.employee",
    "hr.shift",
    "hr.employee_shift",
    "hr.holiday",
    "hr.leave_request",
    "hr.biometric_device",
    "hr.biometric_punch_log",
    "hr.attendance_punch",
    "hr.work_location",
]
EMPLOYEE = 20
BASE = "/api/v1/hr/attendance/me/month"


def _previous_month() -> tuple[int, int]:
    first = india_date(utc_now()).replace(day=1)
    prev = first - timedelta(days=1)
    return prev.year, prev.month


def _weekday_in(year: int, month: int, start_day: int) -> date:
    """The first Monday-to-Saturday on or after start_day (Sunday is the default weekly off)."""
    day = date(year, month, start_day)
    while day.weekday() == 6:
        day += timedelta(days=1)
    return day


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=1, code="TRISHUL", legal_name="Trishul Pvt Ltd")
    insert_row(engine, "core.branch", id=1, company_id=1, code="BDK", name="Bhadrak")
    insert_row(engine, "hr.department", id=1, code="SVC", name="Service")
    insert_row(
        engine,
        "core.employee",
        id=EMPLOYEE,
        company_id=1,
        branch_id=1,
        department_id=1,
        employee_code="EMP0009",
        first_name="Parsuram",
        status="Active",
        is_active=True,
    )
    return engine


@pytest.fixture
def client(db: Engine) -> Iterator[TestClient]:
    settings = Settings(environment="test", auth_mode="dev", dev_username="t", _env_file=None)
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(id=5, employee_id=EMPLOYEE, permissions=frozenset({"hr.attendance.mark"}))
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current:
            set_audit_context(current, user_id=5, source="Android", ip_address="127.0.0.1")
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _punch(db: Engine, uuid: str, kind: str, india_time: datetime) -> None:
    insert_row(
        db,
        "hr.attendance_punch",
        client_uuid=uuid,
        employee_id=EMPLOYEE,
        punch_type=kind,
        attendance_date=india_time.date(),
        effective_at=india_time - IST_OFFSET,
        time_trust="Server",
        capture_mode="Online",
        status="Present",
    )


def test_a_past_month_has_every_day_with_present_off_day_and_absent(client: TestClient, db: Engine) -> None:
    year, month = _previous_month()
    worked = _weekday_in(year, month, 10)
    _punch(db, "in-1", "In", datetime.combine(worked, datetime.min.time()).replace(hour=9, minute=2))
    _punch(db, "out-1", "Out", datetime.combine(worked, datetime.min.time()).replace(hour=18, minute=5))

    response = client.get(BASE, params={"year": year, "month": month})
    assert response.status_code == 200, response.text
    body = response.json()
    days = {d["date"]: d for d in body["days"]}
    last_day = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    assert len(body["days"]) == last_day and body["days"][0]["date"] == f"{year}-{month:02d}-01"

    present = days[str(worked)]
    assert present["status"] == "Present"
    assert present["firstIn"].startswith(f"{worked}T09:02:00") and present["firstIn"].endswith("+05:30")
    assert present["lastOut"].startswith(f"{worked}T18:05:00")
    assert present["workingHours"]

    sunday = next(d for d in (date(year, month, n) for n in range(1, 8)) if d.weekday() == 6)
    assert days[str(sunday)]["status"] == "Off Day"
    assert body["totals"]["Present"] == 1 and body["totals"]["Off Day"] >= 4
    assert body["totals"].get("Absent", 0) >= 15


def test_future_month_is_empty_and_the_current_month_stops_today(client: TestClient) -> None:
    today = india_date(utc_now())
    future = date(today.year + 1, 1, 1)
    assert client.get(BASE, params={"year": future.year, "month": 1}).json()["days"] == []

    current = client.get(BASE, params={"year": today.year, "month": today.month}).json()
    assert len(current["days"]) == today.day and current["days"][-1]["date"] == str(today)


def test_bad_month_and_no_employee_link(client: TestClient, db: Engine) -> None:
    assert client.get(BASE, params={"year": 2026, "month": 13}).status_code == 422
    settings = Settings(environment="test", auth_mode="dev", dev_username="t", _env_file=None)
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    api.dependency_overrides[get_current_user] = lambda: make_user(
        id=9, employee_id=None, permissions=frozenset({"hr.attendance.mark"})
    )

    def session() -> Iterator[Session]:
        with Session(db) as current:
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as other:
        assert other.get(BASE, params={"year": 2026, "month": 11}).status_code == 403
