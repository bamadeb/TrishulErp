"""Face registration: quality checks, duplicate-face check, two-person approval, removal, audited photo."""

import base64
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import AttendanceAudit, EmployeeFace
from trishul_api.main import create_app
from trishul_api.modules.hr.face_attendance.engine import (
    DEFAULT_MODELS_DIR,
    DETECTOR_FILE,
    RECOGNIZER_FILE,
    FaceAnalysis,
    ImageUnreadable,
    similarity,
)
from trishul_api.modules.hr.face_attendance.faces import quality_problems
from trishul_api.modules.hr.face_attendance.protect import FaceDataKeyMissing, FaceVault, load_key
from trishul_api.modules.hr.face_attendance.router import get_face_engine, get_face_vault

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = ["core.company", "core.branch", "core.employee", "hr.face_model", "hr.employee_face", "hr.attendance_audit"]
BASE = "/api/v1/hr/attendance"
KEY = bytes(range(32))
HR_PERMS = frozenset({"hr.face.register", "hr.face.approve", "hr.attendance.photo.view"})
JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


def _vector(seed: int) -> np.ndarray:
    v = np.random.default_rng(seed).normal(size=128).astype(np.float32)
    return v / np.linalg.norm(v)


def good(seed: int) -> FaceAnalysis:
    return FaceAnalysis(1, 0.93, 180, 300.0, 120.0, _vector(seed), b"\xff\xd8\xffstored-jpeg")


class FakeEngine:
    """Returns the analysis queued for the next photo."""

    def __init__(self) -> None:
        self.next: FaceAnalysis | Exception = good(1)

    def analyse(self, image: bytes) -> FaceAnalysis:
        if isinstance(self.next, Exception):
            raise self.next
        return self.next


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=1, code="TRISHUL", legal_name="Trishul Pvt Ltd")
    insert_row(engine, "core.branch", id=1, company_id=1, code="BBS", name="Bhubaneswar")
    for eid, code, name in [(20, "E020", "Anita"), (21, "E021", "Bikash")]:
        insert_row(
            engine,
            "core.employee",
            id=eid,
            company_id=1,
            branch_id=1,
            employee_code=code,
            first_name=name,
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
    return engine


@pytest.fixture
def engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def vault(tmp_path: Path) -> FaceVault:
    return FaceVault(KEY, root=tmp_path)


class Clients:
    def __init__(self, db: Engine, engine: FakeEngine, vault: FaceVault) -> None:
        settings = Settings(environment="test", auth_mode="dev", dev_username="tester", _env_file=None)
        self.app = create_app(settings, engine=db)
        api = self.app.state.api_v1
        self.user = make_user(id=1, employee_id=None, permissions=HR_PERMS)
        api.dependency_overrides[get_current_user] = lambda: self.user

        def session() -> Iterator[Session]:
            with Session(db, expire_on_commit=False) as current:
                set_audit_context(current, user_id=1, source="Web", ip_address="127.0.0.1")
                yield current

        api.dependency_overrides[get_db] = session
        api.dependency_overrides[get_face_engine] = lambda: engine
        api.dependency_overrides[get_face_vault] = lambda: vault
        self.http = TestClient(self.app, raise_server_exceptions=False)

    def as_user(self, user_id: int, permissions: frozenset[str] = HR_PERMS) -> None:
        self.user = make_user(id=user_id, employee_id=None, permissions=permissions)

    def register(self, employee_id: int = 20, consent: str = "true") -> Any:
        return self.http.post(
            f"{BASE}/employees/{employee_id}/face",
            files={"photo": ("face.jpg", JPEG, "image/jpeg")},
            data={"consent": consent},
        )


@pytest.fixture
def c(db: Engine, engine: FakeEngine, vault: FaceVault) -> Iterator[Clients]:
    clients = Clients(db, engine, vault)
    with clients.http:
        yield clients


# --- quality ------------------------------------------------------------------------------


def test_quality_problems_explain_each_failure() -> None:
    assert quality_problems(good(1)) == []
    assert "No face" in quality_problems(FaceAnalysis(0, None, None, None, None, None, b""))[0]
    assert "2 faces" in quality_problems(FaceAnalysis(2, 0.9, None, None, None, None, b""))[0]
    poor = FaceAnalysis(1, 0.7, 60, 10.0, 30.0, _vector(1), b"")
    problems = " ".join(quality_problems(poor))
    for word in ("not clear", "too small", "blurred", "too dark"):
        assert word in problems
    assert "too bright" in quality_problems(FaceAnalysis(1, 0.95, 150, 200.0, 240.0, _vector(1), b""))[0]


def test_register_refuses_bad_photos_and_missing_consent(c: Clients, engine: FakeEngine) -> None:
    assert c.register(consent="false").status_code == 400
    engine.next = FaceAnalysis(0, None, None, None, None, None, b"")
    response = c.register()
    assert response.status_code == 400 and "No face" in response.json()["detail"]
    engine.next = ImageUnreadable("The photo must be a JPEG or PNG image.")
    assert c.register().status_code == 400
    assert c.register(employee_id=999).status_code == 404


# --- register / approve --------------------------------------------------------------------


def test_register_then_a_different_user_approves(c: Clients, db: Engine, vault: FaceVault) -> None:
    created = c.register()
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "Pending approval" and body["employeeCode"] == "E020"
    assert body["faceModel"] == "sface 2021dec" and body["consentAt"] is not None

    # The vector and the photo are stored encrypted.
    with Session(db) as s:
        row = s.get(EmployeeFace, body["id"])
        assert row is not None and row.face_vector is not None and row.photo_s3_key is not None
    assert _vector(1).tobytes() not in row.face_vector
    assert similarity(vault.open_vector(row.face_vector), _vector(1)) > 0.9999
    stored = (vault._root / row.photo_s3_key).read_bytes()
    assert b"stored-jpeg" not in stored and vault.read_photo(row.photo_s3_key) == b"\xff\xd8\xffstored-jpeg"

    self_approval = c.http.post(f"{BASE}/faces/{body['id']}/approve")
    assert self_approval.status_code == 403

    c.as_user(2)
    approved = c.http.post(f"{BASE}/faces/{body['id']}/approve")
    assert approved.status_code == 200 and approved.json()["status"] == "Active"
    assert approved.json()["approvedByUserId"] == 2
    assert c.http.post(f"{BASE}/faces/{body['id']}/approve").status_code == 409


def test_new_registration_supersedes_pending_and_approval_supersedes_active(c: Clients, engine: FakeEngine) -> None:
    first = c.register().json()
    c.as_user(2)
    c.http.post(f"{BASE}/faces/{first['id']}/approve")
    c.as_user(1)
    engine.next = good(1)
    second = c.register().json()
    third = c.register().json()
    statuses = {f["id"]: f["status"] for f in c.http.get(f"{BASE}/faces?employeeId=20").json()}
    assert statuses == {first["id"]: "Active", second["id"]: "Superseded", third["id"]: "Pending approval"}

    c.as_user(2)
    c.http.post(f"{BASE}/faces/{third['id']}/approve")
    statuses = {f["id"]: f["status"] for f in c.http.get(f"{BASE}/faces?employeeId=20").json()}
    assert statuses[first["id"]] == "Superseded" and statuses[third["id"]] == "Active"
    assert [f["id"] for f in c.http.get(f"{BASE}/faces?status=Active").json()] == [third["id"]]


def test_a_face_already_registered_for_someone_else_is_refused(c: Clients, engine: FakeEngine) -> None:
    assert c.register(employee_id=20).status_code == 200
    engine.next = good(1)  # same person, different employee chosen
    clash = c.register(employee_id=21)
    assert clash.status_code == 400 and "E020" in clash.json()["detail"]
    engine.next = good(2)  # a different person is fine
    assert c.register(employee_id=21).status_code == 200


def test_reject_needs_a_reason(c: Clients) -> None:
    face = c.register().json()
    c.as_user(2)
    assert c.http.post(f"{BASE}/faces/{face['id']}/reject", json={"reason": ""}).status_code == 422
    rejected = c.http.post(f"{BASE}/faces/{face['id']}/reject", json={"reason": "Wearing a cap"})
    assert rejected.status_code == 200 and rejected.json()["status"] == "Rejected"
    assert rejected.json()["rejectionReason"] == "Wearing a cap"


# --- photo, removal, permissions -------------------------------------------------------------


def test_photo_view_is_audited_and_deletion_removes_face_data(c: Clients, db: Engine, vault: FaceVault) -> None:
    face = c.register().json()
    photo = c.http.get(f"{BASE}/faces/{face['id']}/photo")
    assert photo.status_code == 200 and photo.content == b"\xff\xd8\xffstored-jpeg"
    assert photo.headers["cache-control"] == "private, no-store"

    with Session(db) as s:
        key = s.get(EmployeeFace, face["id"]).photo_s3_key  # type: ignore[union-attr]
    assert c.http.delete(f"{BASE}/faces/{face['id']}").status_code == 428  # If-Match required
    match = {"If-Match": face["rowVersion"]}
    assert c.http.delete(f"{BASE}/faces/{face['id']}", headers=match).status_code == 204
    assert c.http.delete(f"{BASE}/faces/{face['id']}", headers=match).status_code == 404
    with Session(db) as s:
        row = s.get(EmployeeFace, face["id"])
        assert row is not None and row.status == "Deleted" and row.face_vector is None and row.photo_s3_key is None
        actions = s.scalars(select(AttendanceAudit.action).order_by(AttendanceAudit.id)).all()
    assert key is not None and vault.read_photo(key) is None
    assert actions == ["Registered", "Photo viewed", "Deleted"]
    assert c.http.get(f"{BASE}/faces/{face['id']}/photo").status_code == 404


def test_permissions(c: Clients) -> None:
    face = c.register().json()
    c.as_user(2, frozenset({"hr.face.register"}))
    assert c.http.post(f"{BASE}/faces/{face['id']}/approve").status_code == 403
    assert c.http.get(f"{BASE}/faces/{face['id']}/photo").status_code == 403
    c.as_user(3, frozenset({"hr.attendance.mark"}))
    assert c.register().status_code == 403
    assert c.http.get(f"{BASE}/faces").status_code == 403


def test_face_models_list(c: Clients) -> None:
    c.as_user(1, frozenset({"hr.attendance.manage"}))
    models = c.http.get(f"{BASE}/face-models").json()
    assert [(m["code"], m["isCurrent"]) for m in models] == [("sface", True)]


# --- key and vault -----------------------------------------------------------------------------


def test_face_key_is_required_and_must_be_32_bytes() -> None:
    def settings(key: str | None = None) -> Settings:
        return Settings(
            environment="test",
            auth_mode="dev",
            dev_username="t",
            _env_file=None,
            face_data_key=SecretStr(key) if key else None,
        )

    with pytest.raises(FaceDataKeyMissing):
        load_key(settings(), None)
    with pytest.raises(FaceDataKeyMissing):
        load_key(settings(base64.b64encode(b"short").decode()), None)
    assert load_key(settings(base64.b64encode(KEY).decode()), None) == KEY


def test_vault_refuses_tampered_data(vault: FaceVault) -> None:
    sealed = bytearray(vault.seal_vector(_vector(3)))
    sealed[-1] ^= 1
    with pytest.raises(Exception):  # noqa: B017 - cryptography's InvalidTag
        vault.open_vector(bytes(sealed))
    other = FaceVault(bytes(32), root=vault._root)
    with pytest.raises(Exception):  # noqa: B017
        other.open_vector(vault.seal_vector(_vector(3)))


# --- the real engine (when the model files are installed) ------------------------------------------


@pytest.mark.skipif(
    not (DEFAULT_MODELS_DIR / DETECTOR_FILE).is_file() or not (DEFAULT_MODELS_DIR / RECOGNIZER_FILE).is_file(),
    reason="face models not downloaded (scripts/download_face_models.py)",
)
def test_real_engine_finds_no_face_in_a_plain_image_and_refuses_non_images() -> None:
    import cv2

    from trishul_api.modules.hr.face_attendance.engine import load_engine

    real = load_engine()
    blank = cv2.imencode(".jpg", np.full((480, 640, 3), 128, dtype=np.uint8))[1].tobytes()
    result = real.analyse(blank)
    assert result.face_count == 0 and result.vector is None and result.jpeg.startswith(b"\xff\xd8\xff")
    with pytest.raises(ImageUnreadable):
        real.analyse(b"GIF89a not a photo")
