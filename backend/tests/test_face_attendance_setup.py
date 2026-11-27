"""Face attendance phase 1: work locations, policies, employee assignment and the employee's day."""

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import AttendanceAudit, EmployeeAttendancePolicy
from trishul_api.main import create_app
from trishul_api.modules.hr.face_attendance.rules import Geofence, distance_m, india_date, nearest_geofence
from trishul_api.modules.hr.face_attendance.service import utc_now

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "hr.department",
    "core.employee",
    "hr.face_model",
    "hr.employee_face",
    "hr.work_location",
    "hr.attendance_policy",
    "hr.employee_attendance_policy",
    "hr.employee_attendance_location",
    "hr.attendance_punch",
    "hr.attendance_audit",
]
HR_PERMS = frozenset({"hr.attendance.manage", "hr.attendance.mark"})
EMPLOYEE = 20
BASE = "/api/v1/hr/attendance"


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=1, code="TRISHUL", legal_name="Trishul Pvt Ltd")
    insert_row(engine, "core.branch", id=1, company_id=1, code="BBS", name="Bhubaneswar")
    insert_row(
        engine,
        "core.employee",
        id=EMPLOYEE,
        company_id=1,
        branch_id=1,
        employee_code="E020",
        first_name="Anita",
        status="Active",
        is_active=True,
    )
    insert_row(
        engine, "hr.attendance_policy", id=1, code="OFFICE", name="Office staff", mode="Office", challenge="Blink"
    )
    insert_row(engine, "hr.attendance_policy", id=2, code="FIELD", name="Field staff", mode="Field", challenge="Blink")
    return engine


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test", auth_mode="dev", dev_username="tester", _env_file=None)


def _client(settings: Settings, db: Engine, **user: object) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(**({"id": 1, "employee_id": EMPLOYEE, "permissions": HR_PERMS} | user))
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current:
            set_audit_context(current, user_id=1, source="Web", ip_address="127.0.0.1")
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    yield from _client(settings, db)


def _office(client: TestClient, **extra: object) -> dict[str, Any]:
    body = {"name": "Bhubaneswar office", "branchId": 1, "latitude": "20.296059", "longitude": "85.824539"} | extra
    response = client.post(f"{BASE}/work-locations", json=body)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


# --- rules ---------------------------------------------------------------------------


def test_india_date_rolls_over_at_ist_midnight() -> None:
    assert india_date(datetime(2026, 11, 20, 18, 29)) == date(2026, 11, 20)
    assert india_date(datetime(2026, 11, 20, 18, 30)) == date(2026, 11, 21)


def test_nearest_geofence_picks_the_closest_and_checks_its_radius() -> None:
    office = Geofence(id=1, latitude=20.296059, longitude=85.824539, radius_m=150)
    far = Geofence(id=2, latitude=20.462521, longitude=85.882988, radius_m=500)
    hit = nearest_geofence(20.296959, 85.824539, [far, office])  # ~100 m north of the office
    assert hit is not None and hit.work_location_id == 1 and hit.inside
    assert 95 < hit.distance_m < 105
    outside = nearest_geofence(20.299059, 85.824539, [office])  # ~334 m
    assert outside is not None and not outside.inside
    assert nearest_geofence(20.0, 85.0, []) is None
    assert distance_m(0, 0, 0, 0) == 0


# --- work locations ----------------------------------------------------------------------


def test_work_location_defaults_to_150_m_and_is_audited(client: TestClient, db: Engine) -> None:
    created = _office(client)
    assert created["radiusM"] == 150 and created["branchName"] == "Bhubaneswar" and created["isActive"]

    updated = client.patch(
        f"{BASE}/work-locations/{created['id']}", json={"radiusM": 200}, headers={"If-Match": created["rowVersion"]}
    )
    assert updated.status_code == 200 and updated.json()["radiusM"] == 200

    # A rowVersion that is no longer the row's (someone else saved in between) is refused, not overwritten.
    # (SQLite doesn't bump row_version on UPDATE as SQL Server does, so a different value stands in for it.)
    stale = client.patch(
        f"{BASE}/work-locations/{created['id']}", json={"radiusM": 300}, headers={"If-Match": "AAAAAAAAAAA="}
    )
    assert stale.status_code == 409
    assert client.patch(f"{BASE}/work-locations/{created['id']}", json={"radiusM": 300}).status_code == 428

    with Session(db) as s:
        actions = s.scalars(select(AttendanceAudit.action).where(AttendanceAudit.entity == "location")).all()
    assert actions == ["Created", "Updated"]


def test_work_location_rejects_a_bad_radius_and_unknown_branch(client: TestClient) -> None:
    assert (
        client.post(
            f"{BASE}/work-locations", json={"name": "X", "latitude": 1, "longitude": 1, "radiusM": 5}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{BASE}/work-locations", json={"name": "X", "latitude": 1, "longitude": 1, "branchId": 9}
        ).status_code
        == 404
    )


def test_set_up_needs_the_manage_permission(settings: Settings, db: Engine) -> None:
    for c in _client(settings, db, permissions=frozenset({"hr.attendance.mark"})):
        assert c.post(f"{BASE}/work-locations", json={"name": "X", "latitude": 1, "longitude": 1}).status_code == 403
        assert c.get(f"{BASE}/policies").status_code == 403


# --- policies ------------------------------------------------------------------------------


def test_policies_list_and_create_with_threshold_check(client: TestClient) -> None:
    codes = [p["code"] for p in client.get(f"{BASE}/policies").json()]
    assert codes == ["FIELD", "OFFICE"]

    bad = client.post(
        f"{BASE}/policies",
        json={"code": "STRICT", "name": "Strict", "mode": "Office", "matchThreshold": "0.4", "reviewThreshold": "0.5"},
    )
    assert bad.status_code == 422

    made = client.post(
        f"{BASE}/policies",
        json={
            "code": "STRICT",
            "name": "Strict",
            "mode": "Office",
            "challenge": "Blink and turn",
            "allowOffline": False,
        },
    )
    assert made.status_code == 201, made.text
    assert made.json()["maxOfflineHours"] == 72 and made.json()["allowOffline"] is False
    assert client.post(f"{BASE}/policies", json={"code": "STRICT", "name": "Again", "mode": "Field"}).status_code == 409

    match = {"If-Match": made.json()["rowVersion"]}
    patched = client.patch(
        f"{BASE}/policies/{made.json()['id']}",
        json={"reviewThreshold": "0.9", "matchThreshold": "0.5"},
        headers=match,
    )
    assert patched.status_code == 400
    ok = client.patch(f"{BASE}/policies/{made.json()['id']}", json={"maxOfflineHours": 24}, headers=match)
    assert ok.status_code == 200 and ok.json()["maxOfflineHours"] == 24


# --- employee assignment -------------------------------------------------------------------


def test_office_policy_needs_a_location_and_assignment_replaces_the_old_one(client: TestClient, db: Engine) -> None:
    office = _office(client)
    today = india_date(utc_now())

    no_location = client.post(f"{BASE}/employees/{EMPLOYEE}/policy", json={"policyId": 1, "fromDate": str(today)})
    assert no_location.status_code == 400

    first = client.post(
        f"{BASE}/employees/{EMPLOYEE}/policy",
        json={"policyId": 1, "fromDate": str(today - timedelta(days=10)), "workLocationIds": [office["id"]]},
    )
    assert first.status_code == 200, first.text
    assert [w["name"] for w in first.json()["workLocations"]] == ["Bhubaneswar office"]

    second = client.post(f"{BASE}/employees/{EMPLOYEE}/policy", json={"policyId": 2, "fromDate": str(today)})
    assert second.status_code == 200 and second.json()["policy"]["code"] == "FIELD"

    current = client.get(f"{BASE}/employees/{EMPLOYEE}/policy").json()
    assert current["policy"]["code"] == "FIELD" and current["workLocations"] == []
    with Session(db) as s:
        rows = s.scalars(select(EmployeeAttendancePolicy).order_by(EmployeeAttendancePolicy.id)).all()
    assert rows[0].to_date == today - timedelta(days=1) and rows[1].to_date is None

    counts = {p["code"]: p["employeeCount"] for p in client.get(f"{BASE}/policies").json()}
    assert counts == {"FIELD": 1, "OFFICE": 0}


def test_unknown_employee_policy_and_location_are_404(client: TestClient) -> None:
    today = str(india_date(utc_now()))
    assert client.post(f"{BASE}/employees/999/policy", json={"policyId": 2, "fromDate": today}).status_code == 404
    assert (
        client.post(f"{BASE}/employees/{EMPLOYEE}/policy", json={"policyId": 99, "fromDate": today}).status_code == 404
    )
    assert (
        client.post(
            f"{BASE}/employees/{EMPLOYEE}/policy", json={"policyId": 1, "fromDate": today, "workLocationIds": [77]}
        ).status_code
        == 404
    )
    assert client.get(f"{BASE}/employees/{EMPLOYEE}/policy").status_code == 404


# --- the employee's day ----------------------------------------------------------------------


def test_my_today_explains_why_punching_is_blocked_until_everything_is_set(client: TestClient, db: Engine) -> None:
    today = india_date(utc_now())
    body = client.get(f"{BASE}/me/today").json()
    assert body["canPunch"] is False and "policy" in body["blockedReason"]
    assert body["face"]["status"] == "Not registered" and body["nextPunchType"] == "In"

    client.post(f"{BASE}/employees/{EMPLOYEE}/policy", json={"policyId": 2, "fromDate": str(today)})
    assert "not registered" in client.get(f"{BASE}/me/today").json()["blockedReason"]

    insert_row(db, "hr.employee_face", id=1, employee_id=EMPLOYEE, status="Pending approval")
    assert "waiting for HR approval" in client.get(f"{BASE}/me/today").json()["blockedReason"]

    insert_row(
        db, "hr.employee_face", id=2, employee_id=EMPLOYEE, status="Active", created_at=utc_now() + timedelta(seconds=5)
    )
    assert "not switched on" in client.get(f"{BASE}/me/today").json()["blockedReason"]

    insert_row(db, "hr.face_model", id=1, code="buffalo_s", kind="Face", version="1.0", is_current=True)
    ready = client.get(f"{BASE}/me/today").json()
    assert ready["canPunch"] is True and ready["blockedReason"] is None
    assert ready["faceModelVersion"] == "buffalo_s 1.0" and ready["policy"]["code"] == "FIELD"


def test_my_today_lists_punches_and_offers_check_out_after_check_in(client: TestClient, db: Engine) -> None:
    now = utc_now()
    today = india_date(now)
    common = {
        "employee_id": EMPLOYEE,
        "attendance_date": today,
        "time_trust": "Server",
        "capture_mode": "Online",
    }
    insert_row(
        db,
        "hr.attendance_punch",
        id=1,
        client_uuid="a",
        punch_type="In",
        effective_at=now - timedelta(hours=3),
        status="Present",
        **common,
    )
    insert_row(
        db,
        "hr.attendance_punch",
        id=2,
        client_uuid="b",
        punch_type="Out",
        effective_at=now - timedelta(hours=1),
        status="Rejected",
        **common,
    )
    body = client.get(f"{BASE}/me/today").json()
    assert [p["punchType"] for p in body["punches"]] == ["In", "Out"]
    assert body["nextPunchType"] == "Out"  # the rejected check-out doesn't count


def test_my_today_needs_a_linked_employee(settings: Settings, db: Engine) -> None:
    for c in _client(settings, db, employee_id=None):
        assert c.get(f"{BASE}/me/today").status_code == 403


# --- Daily Attendance page (modules/hr/attendance) ---------------------------------------------


def test_daily_attendance_reads_accepted_face_punches_in_indian_time() -> None:
    from trishul_api.modules.hr.attendance.repository import AttendanceRepository

    engine = sqlite_engine(["hr.biometric_device", "hr.biometric_punch_log", "hr.attendance_punch", "hr.work_location"])
    insert_row(
        engine, "hr.work_location", id=7, name="Bhadrak office", latitude=21.0574, longitude=86.4963, radius_m=150
    )
    common = {
        "employee_id": EMPLOYEE,
        "attendance_date": date(2026, 11, 21),
        "time_trust": "Server",
        "capture_mode": "Online",
    }
    # 03:32 UTC = 09:02 in India; the rejected one must not count.
    insert_row(
        engine,
        "hr.attendance_punch",
        client_uuid="in",
        punch_type="In",
        effective_at=datetime(2026, 11, 21, 3, 32),
        status="Present",
        latitude=21.0601,
        longitude=86.4990,
        gps_accuracy_m=12.5,
        work_location_id=7,
        inside_geofence=False,
        distance_m=402.3,
        **common,
    )
    insert_row(
        engine,
        "hr.attendance_punch",
        client_uuid="x",
        punch_type="Out",
        effective_at=datetime(2026, 11, 21, 4, 0),
        status="Rejected",
        **common,
    )
    # 19:00 UTC on the 20th is 00:30 on the 21st in India: same Indian day.
    insert_row(
        engine,
        "hr.attendance_punch",
        client_uuid="late",
        punch_type="Out",
        effective_at=datetime(2026, 11, 20, 19, 0),
        status="Present",
        **common,
    )
    # 18:00 UTC on the 21st is 23:30 on the 21st; 18:31 UTC is already the 22nd.
    insert_row(
        engine,
        "hr.attendance_punch",
        client_uuid="next",
        punch_type="In",
        effective_at=datetime(2026, 11, 21, 18, 31),
        status="Present",
        **common,
    )

    with Session(engine) as s:
        repo = AttendanceRepository(s)
        start, end = repo.day_bounds(date(2026, 11, 21))
        punches = repo.punches_between(start, end)
    assert [(p.punched_at, p.punch_type, p.device_name) for p in punches] == [
        (datetime(2026, 11, 21, 0, 30), "OUT", "Mobile app (face)"),
        (datetime(2026, 11, 21, 9, 2), "IN", "Mobile app (face)"),
    ]
    # Field staff: HR sees where each punch was made (the late check-out had no GPS fix).
    where = punches[1].location
    assert where is not None and (where.latitude, where.longitude) == (21.0601, 86.499)
    assert (where.place, where.inside_office, where.distance_m, where.accuracy_m) == (
        "Bhadrak office",
        False,
        402.3,
        12.5,
    )
    assert where.fake_gps is False and punches[0].location is None

    from trishul_api.modules.hr.attendance.service import AttendanceService

    out = AttendanceService._punch_out(punches[1]).model_dump(mode="json", by_alias=True)
    assert out["location"] == {
        "latitude": 21.0601,
        "longitude": 86.499,
        "accuracyM": 12.5,
        "place": "Bhadrak office",
        "insideOffice": False,
        "distanceM": 402.3,
        "fakeGps": False,
    }
    assert out["at"] == "2026-11-21T09:02:00+05:30"


def test_punches_between_employee_ids_excludes_other_face_punches() -> None:
    """ESS My Attendance must not mix another employee's accepted face punches into the month view."""
    from trishul_api.modules.hr.attendance.repository import AttendanceRepository

    other = EMPLOYEE + 1
    engine = sqlite_engine(["hr.biometric_device", "hr.biometric_punch_log", "hr.attendance_punch", "hr.work_location"])
    for employee_id, uuid, hour in (
        (EMPLOYEE, "self-in", 3),
        (other, "other-in", 4),
    ):
        insert_row(
            engine,
            "hr.attendance_punch",
            client_uuid=uuid,
            employee_id=employee_id,
            attendance_date=date(2026, 11, 21),
            punch_type="In",
            effective_at=datetime(2026, 11, 21, hour, 0),
            status="Present",
            time_trust="Server",
            capture_mode="Online",
        )

    with Session(engine) as s:
        repo = AttendanceRepository(s)
        start, end = repo.day_bounds(date(2026, 11, 21))
        scoped = repo.punches_between(start, end, employee_ids={EMPLOYEE})
        everyone = repo.punches_between(start, end)

    assert [p.employee_id for p in scoped] == [EMPLOYEE]
    assert {p.employee_id for p in everyone} == {EMPLOYEE, other}


def test_employee_list_shows_policy_locations_and_face(client: TestClient, db: Engine) -> None:
    insert_row(
        db,
        "core.employee",
        id=21,
        company_id=1,
        branch_id=1,
        employee_code="E021",
        first_name="Bikash",
        status="Active",
        is_active=True,
    )
    insert_row(
        db,
        "core.employee",
        id=22,
        company_id=1,
        branch_id=1,
        employee_code="E022",
        first_name="Left",
        status="Resigned",
        is_active=True,
    )
    office = _office(client)
    today = india_date(utc_now())
    client.post(
        f"{BASE}/employees/{EMPLOYEE}/policy",
        json={"policyId": 1, "fromDate": str(today), "workLocationIds": [office["id"]]},
    )
    insert_row(db, "hr.employee_face", id=1, employee_id=EMPLOYEE, status="Active")
    insert_row(
        db,
        "hr.employee_face",
        id=2,
        employee_id=EMPLOYEE,
        status="Pending approval",
        created_at=utc_now() + timedelta(seconds=5),
    )

    rows = {r["employeeCode"]: r for r in client.get(f"{BASE}/employees").json()}
    assert set(rows) == {"E020", "E021"}  # a resigned employee is left out
    anita = rows["E020"]
    assert anita["policyCode"] == "OFFICE" and anita["workLocationNames"] == ["Bhubaneswar office"]
    assert anita["faceStatus"] == "Active" and anita["faceId"] == 1  # the Active face wins over a newer pending one
    assert anita["branchName"] == "Bhubaneswar"
    assert rows["E021"]["policyCode"] is None and rows["E021"]["faceStatus"] == "Not registered"
