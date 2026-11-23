"""Face attendance punches: challenge, online / offline punch, and the accept / review / reject rules."""

import base64
import json
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import AttendanceAudit, AttendancePunch, Employee, EmployeeAttendancePolicy
from trishul_api.main import create_app
from trishul_api.modules.hr.face_attendance.engine import FaceAnalysis
from trishul_api.modules.hr.face_attendance.protect import FaceVault
from trishul_api.modules.hr.face_attendance.punches import Facts, Thresholds, decide
from trishul_api.modules.hr.face_attendance.router import get_face_engine, get_face_vault
from trishul_api.modules.hr.face_attendance.rules import india_date
from trishul_api.modules.hr.face_attendance.service import utc_now

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "core.employee",
    "hr.face_model",
    "hr.employee_face",
    "hr.work_location",
    "hr.attendance_policy",
    "hr.employee_attendance_policy",
    "hr.employee_attendance_location",
    "hr.attendance_challenge",
    "hr.attendance_punch",
    "hr.attendance_audit",
]
BASE = "/api/v1/hr/attendance"
EMPLOYEE = 20
KEY = bytes(range(32))
OFFICE = (20.296059, 85.824539)
LIMITS = Thresholds(match=0.363, review=0.30, max_score_gap=0.10, max_gps_accuracy_m=100)


def _vector(seed: int) -> np.ndarray:
    v = np.random.default_rng(seed).normal(size=128).astype(np.float32)
    return v / np.linalg.norm(v)


def _near(target: np.ndarray, score: float) -> np.ndarray:
    """A unit vector whose cosine with ``target`` is ``score``."""
    other = _vector(99)
    other = other - np.dot(other, target) * target
    other /= np.linalg.norm(other)
    result: np.ndarray = (score * target + np.sqrt(1 - score**2) * other).astype(np.float32)
    return result


class FakeEngine:
    def __init__(self) -> None:
        self.vector: np.ndarray | None = _vector(1)
        self.faces = 1

    def analyse(self, image: bytes) -> FaceAnalysis:
        vector = self.vector if self.faces == 1 else None
        return FaceAnalysis(self.faces, 0.9, 150, 200.0, 120.0, vector, b"\xff\xd8\xffpunch")


# --- the rules (pure) ---------------------------------------------------------------------


def _facts(**overrides: Any) -> Facts:
    values: dict[str, Any] = {
        "face_count": 1,
        "server_score": 0.8,
        "challenge_result": "Passed",
        "gps_accuracy_m": 15.0,
    }
    return Facts(**(values | overrides))


def test_decide_present_when_everything_passes() -> None:
    assert decide(_facts(), LIMITS) == ("Present", [])


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"server_score": 0.2}, "does not match"),
        ({"face_count": 0, "server_score": None}, "No face"),
        ({"face_count": 2, "server_score": None}, "More than one face"),
        ({"is_mock_location": True}, "fake-location"),
        ({"challenge_result": "Failed"}, "check failed"),
        ({"nonce_problem": "The face check took too long."}, "too long"),
    ],
)
def test_decide_rejects(overrides: dict[str, Any], reason: str) -> None:
    status, reasons = decide(_facts(**overrides), LIMITS)
    assert status == "Rejected" and reason in " ".join(reasons)


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"server_score": 0.33}, "not certain"),
        ({"device_score": 0.5}, "differ"),
        ({"gps_accuracy_m": 250.0}, "GPS signal was weak"),
        ({"has_location": False}, "No GPS"),
        ({"geofence_required": True, "inside_geofence": False}, "outside the office"),
        ({"challenge_result": "Not done"}, "not completed"),
        ({"offline": True, "offline_auto_accept": False}, "checked by HR"),
        ({"offline": True, "clock_ahead": True}, "clock was ahead"),
        ({"offline": True, "offline_too_old": True}, "too late"),
    ],
)
def test_decide_sends_doubtful_punches_to_review(overrides: dict[str, Any], reason: str) -> None:
    status, reasons = decide(_facts(**overrides), LIMITS)
    assert status == "Pending" and reason in " ".join(reasons)


def test_rejection_wins_over_review() -> None:
    status, reasons = decide(_facts(server_score=0.1, gps_accuracy_m=500.0), LIMITS)
    assert status == "Rejected" and reasons == ["The face does not match the registered face."]  # only the rejection


# --- the API ------------------------------------------------------------------------------------


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
        is_active=True,
    )
    insert_row(
        engine,
        "hr.face_model",
        id=1,
        code="sface",
        kind="Face",
        version="2021dec",
        vector_size=128,
        default_match_threshold=0.363,
        default_review_threshold=0.3,
        is_current=True,
    )
    insert_row(
        engine,
        "hr.attendance_policy",
        id=1,
        code="OFFICE",
        name="Office",
        mode="Office",
        challenge="Blink and turn",
        max_score_gap=0.1,
        max_gps_accuracy_m=100,
        allow_offline=True,
        offline_auto_accept=True,
        max_offline_hours=72,
        challenge_on_check_out=False,
    )
    insert_row(
        engine,
        "hr.attendance_policy",
        id=2,
        code="FIELD",
        name="Field",
        mode="Field",
        challenge="Blink",
        max_score_gap=0.1,
        max_gps_accuracy_m=100,
        allow_offline=False,
        offline_auto_accept=True,
        max_offline_hours=72,
        challenge_on_check_out=False,
    )
    insert_row(
        engine,
        "hr.work_location",
        id=1,
        name="Bhubaneswar office",
        branch_id=1,
        latitude=OFFICE[0],
        longitude=OFFICE[1],
        radius_m=150,
    )
    insert_row(
        engine,
        "hr.employee_attendance_policy",
        id=1,
        employee_id=EMPLOYEE,
        policy_id=1,
        from_date=india_date(utc_now()) - timedelta(days=30),
    )
    insert_row(engine, "hr.employee_attendance_location", employee_attendance_policy_id=1, work_location_id=1)
    return engine


@pytest.fixture
def vault(tmp_path: Path) -> FaceVault:
    return FaceVault(KEY, root=tmp_path)


@pytest.fixture
def engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def registered(db: Engine, vault: FaceVault) -> None:
    insert_row(
        db,
        "hr.employee_face",
        id=1,
        employee_id=EMPLOYEE,
        status="Active",
        face_model_id=1,
        face_vector=vault.seal_vector(_vector(1)),
    )


@pytest.fixture
def client(db: Engine, engine: FakeEngine, vault: FaceVault) -> Iterator[TestClient]:
    settings = Settings(environment="test", auth_mode="dev", dev_username="tester", _env_file=None)
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(id=5, employee_id=EMPLOYEE, permissions=frozenset({"hr.attendance.mark"}))
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current:
            set_audit_context(current, user_id=5, source="Android", ip_address="127.0.0.1")
            yield current

    api.dependency_overrides[get_db] = session
    api.dependency_overrides[get_face_engine] = lambda: engine
    api.dependency_overrides[get_face_vault] = lambda: vault
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


_counter = iter(range(1, 10_000))


def _punch(
    client: TestClient, punch_type: str = "In", offline: bool = False, frame: bytes | None = None, **evidence: Any
) -> Any:
    body: dict[str, Any] = {
        "clientUuid": f"uuid-{next(_counter):06d}",
        "punchType": punch_type,
        "challengeResult": "Passed",
        "latitude": OFFICE[0],
        "longitude": OFFICE[1],
        "gpsAccuracyM": 12,
        "deviceScore": 0.99,
    }
    if not offline and "nonce" not in evidence:
        started = client.post(f"{BASE}/challenges", json={"punchType": punch_type})
        assert started.status_code == 201, started.text
        body["nonce"] = started.json()["nonce"]
    body |= evidence
    body = {k: v for k, v in body.items() if v is not None}
    data = frame or f"\xff\xd8\xff-{body['clientUuid']}".encode("latin-1")
    path = f"{BASE}/punches/offline" if offline else f"{BASE}/punches"
    return client.post(path, data={"evidence": json.dumps(body)}, files=[("frames", ("f.jpg", data, "image/jpeg"))])


def test_challenge_needs_a_registered_face(client: TestClient) -> None:
    response = client.post(f"{BASE}/challenges", json={"punchType": "In"})
    assert response.status_code == 403 and "not registered" in response.json()["detail"]


@pytest.mark.usefixtures("registered")
def test_challenge_asks_blink_and_a_random_turn_on_check_in_and_only_blink_on_check_out(client: TestClient) -> None:
    check_in = client.post(f"{BASE}/challenges", json={"punchType": "In"}).json()
    assert check_in["challenge"] in ("Blink, then turn left", "Blink, then turn right")
    assert len(check_in["nonce"]) >= 40 and "turn your head" in check_in["instruction"]
    assert client.post(f"{BASE}/challenges", json={"punchType": "Out"}).json()["challenge"] == "Blink"


@pytest.mark.usefixtures("registered")
def test_check_in_then_check_out_and_a_resend_is_not_saved_twice(client: TestClient, db: Engine) -> None:
    first = _punch(client, clientUuid="same-uuid-1")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "Present" and body["message"] == "Check-in recorded."
    assert body["insideGeofence"] is True and body["workLocationName"] == "Bhubaneswar office"

    again = _punch(client, clientUuid="same-uuid-1", nonce="x" * 43)
    assert again.status_code == 200 and again.json()["alreadyReceived"] is True and again.json()["id"] == body["id"]

    wrong = _punch(client, "In")
    assert wrong.status_code == 409 and "check-out" in wrong.json()["detail"]
    assert _punch(client, "Out").json()["status"] == "Present"

    today = client.get(f"{BASE}/me/today").json()
    assert [p["punchType"] for p in today["punches"]] == ["In", "Out"] and today["nextPunchType"] == "In"
    with Session(db) as s:
        row = s.scalars(select(AttendancePunch).order_by(AttendancePunch.id)).first()
    assert row is not None and row.face_status == "Matched" and float(row.server_score or 0) > 0.99
    assert row.photo_s3_key and row.photo_s3_key.endswith(".enc") and row.time_trust == "Server"


@pytest.mark.usefixtures("registered")
def test_nonce_problems_are_rejected(client: TestClient) -> None:
    started = client.post(f"{BASE}/challenges", json={"punchType": "In"}).json()["nonce"]
    assert _punch(client, nonce=started).json()["status"] == "Present"
    # Reusing a code, or none at all (not started from the app's camera), is refused.
    assert _punch(client, "Out", nonce=started).json()["status"] == "Rejected"


@pytest.mark.usefixtures("registered")
def test_missing_nonce_is_rejected(client: TestClient) -> None:
    result = _punch(client, nonce="").json()
    assert result["status"] == "Rejected" and "camera screen" in result["statusReason"]


@pytest.mark.usefixtures("registered")
def test_face_results(client: TestClient, engine: FakeEngine) -> None:
    engine.vector = _vector(7)  # someone else
    other = _punch(client).json()
    assert other["status"] == "Rejected" and "does not match" in other["statusReason"]
    engine.vector = _near(_vector(1), 0.33)
    unsure = _punch(client).json()
    assert unsure["status"] == "Pending" and "not certain" in unsure["statusReason"]
    engine.faces = 2  # the pending check-in counts, so the next punch is a check-out
    assert "More than one face" in _punch(client, "Out").json()["statusReason"]


@pytest.mark.usefixtures("registered")
def test_location_rules(client: TestClient) -> None:
    outside = _punch(client, latitude=20.31, longitude=85.83).json()
    assert outside["status"] == "Pending" and "outside the office" in outside["statusReason"]
    assert outside["insideGeofence"] is False

    fake = _punch(client, "Out", isMockLocation=True).json()
    assert fake["status"] == "Rejected" and "fake-location" in fake["statusReason"]

    weak = _punch(client, "Out", gpsAccuracyM=300).json()
    assert weak["status"] == "Pending" and "weak" in weak["statusReason"]


@pytest.mark.usefixtures("registered")
def test_a_photo_from_an_earlier_punch_is_refused(client: TestClient) -> None:
    frame = b"\xff\xd8\xff-the-same-photo"
    assert _punch(client, frame=frame).json()["status"] == "Present"
    replay = _punch(client, "Out", frame=frame).json()
    assert replay["status"] == "Rejected" and "earlier punch" in replay["statusReason"]


@pytest.mark.usefixtures("registered")
def test_offline_punch_uses_the_phone_time_and_flags_doubtful_clocks(client: TestClient, db: Engine) -> None:
    taken = (utc_now() - timedelta(hours=2)).isoformat() + "Z"
    result = _punch(client, offline=True, deviceCapturedAt=taken)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["status"] == "Present" and body["captureMode"] == "Offline"
    assert body["effectiveAt"].startswith(taken[:16])

    ahead = _punch(
        client, "Out", offline=True, deviceCapturedAt=(utc_now() + timedelta(hours=1)).isoformat() + "Z"
    ).json()
    assert ahead["status"] == "Pending" and "clock was ahead" in ahead["statusReason"]
    old = _punch(
        client, "In", offline=True, deviceCapturedAt=(utc_now() - timedelta(hours=80)).isoformat() + "Z"
    ).json()
    assert old["status"] == "Pending" and "too late" in old["statusReason"]

    assert _punch(client, offline=True).status_code == 400  # deviceCapturedAt is required offline
    with Session(db) as s:
        trusts = set(s.scalars(select(AttendancePunch.time_trust)).all())
    assert trusts == {"Device unverified"}


@pytest.mark.usefixtures("registered")
def test_offline_not_allowed_by_policy(client: TestClient, db: Engine) -> None:
    with Session(db) as s, s.begin():
        s.execute(update(EmployeeAttendancePolicy).values(policy_id=2))
    response = _punch(client, offline=True, deviceCapturedAt=utc_now().isoformat() + "Z")
    assert response.status_code == 403 and "Offline punches are not allowed" in response.json()["detail"]


@pytest.mark.usefixtures("registered")
def test_bad_evidence_and_frames(client: TestClient) -> None:
    bad = client.post(
        f"{BASE}/punches", data={"evidence": "{not json"}, files=[("frames", ("f.jpg", b"x", "image/jpeg"))]
    )
    assert bad.status_code == 400
    half = client.post(
        f"{BASE}/punches",
        data={"evidence": json.dumps({"clientUuid": "uuid-half-1", "punchType": "In", "latitude": 20.1})},
        files=[("frames", ("f.jpg", b"x", "image/jpeg"))],
    )
    assert half.status_code == 400
    many = [("frames", (f"{i}.jpg", b"\xff\xd8\xff" + bytes([i]), "image/jpeg")) for i in range(4)]
    body = {"clientUuid": "uuid-many-1", "punchType": "In", "nonce": "n"}
    assert client.post(f"{BASE}/punches", data={"evidence": json.dumps(body)}, files=many).status_code == 400


# --- review queue, photo, template ------------------------------------------------------------


def _as(client: TestClient, **user: Any) -> None:
    api = client.app.state.api_v1  # type: ignore[attr-defined]
    actor = make_user(**user)
    api.dependency_overrides[get_current_user] = lambda: actor


@pytest.mark.usefixtures("registered")
def test_hr_reviews_a_pending_punch_and_the_employee_cannot(client: TestClient, db: Engine) -> None:
    pending = _punch(client, latitude=20.31, longitude=85.83).json()
    assert pending["status"] == "Pending"
    assert client.get(f"{BASE}/punches?status=Pending").status_code == 403  # an employee has no queue

    _as(client, id=9, employee_id=None, permissions=frozenset({"hr.attendance.manage", "hr.attendance.photo.view"}))
    queue = client.get(f"{BASE}/punches?status=Pending").json()
    assert [p["id"] for p in queue] == [pending["id"]]
    assert queue[0]["employeeCode"] == "E020" and queue[0]["hasPhoto"] is True and queue[0]["insideGeofence"] is False

    assert (
        client.post(f"{BASE}/punches/{pending['id']}/review", json={"decision": "Present", "remarks": ""}).status_code
        == 422
    )
    done = client.post(
        f"{BASE}/punches/{pending['id']}/review", json={"decision": "Present", "remarks": "Client site visit"}
    )
    assert done.status_code == 200 and done.json()["status"] == "Present" and done.json()["reviewedByUserId"] == 9
    assert (
        client.post(
            f"{BASE}/punches/{pending['id']}/review", json={"decision": "Rejected", "remarks": "again"}
        ).status_code
        == 409
    )

    photo = client.get(f"{BASE}/punches/{pending['id']}/photo")
    assert photo.status_code == 200 and photo.content == b"\xff\xd8\xffpunch"
    with Session(db) as s:
        actions = s.scalars(select(AttendanceAudit.action).order_by(AttendanceAudit.id)).all()
    assert actions == ["Reviewed", "Photo viewed"]


@pytest.mark.usefixtures("registered")
def test_reviewer_cannot_decide_their_own_punch(client: TestClient) -> None:
    pending = _punch(client, latitude=20.31, longitude=85.83).json()
    _as(client, id=5, employee_id=EMPLOYEE, permissions=frozenset({"hr.attendance.manage"}))
    response = client.post(f"{BASE}/punches/{pending['id']}/review", json={"decision": "Present", "remarks": "mine"})
    assert response.status_code == 403


@pytest.mark.usefixtures("registered")
def test_team_lead_sees_only_their_team(client: TestClient, db: Engine) -> None:
    _punch(client)
    _as(client, id=11, employee_id=77, permissions=frozenset({"hr.attendance.view.team"}))
    assert client.get(f"{BASE}/punches").json() == []
    with Session(db) as s, s.begin():
        s.execute(update(Employee).where(Employee.id == EMPLOYEE).values(reporting_manager_id=77))
    assert len(client.get(f"{BASE}/punches").json()) == 1


@pytest.mark.usefixtures("registered")
def test_my_face_template_is_my_own_vector_and_logged(client: TestClient, db: Engine) -> None:
    body = client.get(f"{BASE}/me/face-template").json()
    vector = np.frombuffer(base64.b64decode(body["vector"]), dtype="<f4")
    assert body["vectorSize"] == 128 and np.allclose(vector, _vector(1), atol=1e-6)
    assert body["modelCode"] == "sface" and float(body["matchThreshold"]) == pytest.approx(0.363)
    with Session(db) as s:
        assert s.scalars(select(AttendanceAudit.action)).all() == ["Template downloaded"]
