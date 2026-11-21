"""Biometric integration foundation: devices, punch dedupe, disabled sync."""

from collections.abc import Iterator
from datetime import datetime

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.db.models import BiometricPunchLog, BiometricSyncLog
from trishul_api.main import create_app
from trishul_api.modules.hr.biometric.config import BiometricSettings
from trishul_api.modules.hr.biometric.service import BiometricService
from trishul_api.secrets import SecretProvider, StaticSecretFetcher

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "hr.department",
    "hr.designation",
    "core.employee",
    "core.app_user",
    "hr.biometric_device",
    "hr.biometric_employee_mapping",
    "hr.biometric_sync_log",
    "hr.biometric_punch_log",
]
EMPLOYEE = 20
PERMS = frozenset({"hr.biometric.view", "hr.biometric.manage", "hr.biometric.sync"})


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=1, code="TRISHUL", legal_name="Trishul Pvt Ltd")
    insert_row(engine, "core.branch", id=1, company_id=1, code="HO", name="Head office")
    insert_row(engine, "hr.department", id=1, code="HR", name="Human Resources")
    insert_row(engine, "hr.designation", id=1, code="EXE", name="Executive", grade="L2", department_id=1)
    insert_row(
        engine,
        "core.employee",
        id=EMPLOYEE,
        company_id=1,
        branch_id=1,
        department_id=1,
        designation_id=1,
        employee_code="E020",
        first_name="Anita",
        employee_type="Permanent",
        status="Active",
        is_active=True,
    )
    return engine


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        auth_mode="dev",
        dev_username="tester",
        biometric_sync_enabled=False,
        _env_file=None,
    )


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    secrets = SecretProvider(StaticSecretFetcher({"biometric/essl-dev": "{}"}), ttl_seconds=60)
    app = create_app(settings, engine=db, secret_provider=secrets)
    api = app.state.api_v1
    actor = make_user(id=1, permissions=PERMS)
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current:
            set_audit_context(current, user_id=1, source="Web", ip_address="127.0.0.1")
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _create_device(client: TestClient, **changes: object) -> httpx.Response:
    body: dict[str, object] = {
        "code": "GATE-01",
        "name": "Main gate",
        "vendor": "ESSL",
        "locationName": "HO lobby",
        "credentialSecretName": "biometric/essl-dev",
        "baseUrl": "https://example.invalid/essl",
        "isSyncEnabled": False,
    }
    body.update(changes)
    return client.post("/api/v1/hr/biometric/devices", json=body)


def test_create_and_list_devices(client: TestClient) -> None:
    created = _create_device(client)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["code"] == "GATE-01"
    assert body["isSyncEnabled"] is False
    assert body["credentialSecretName"] == "biometric/essl-dev"
    listed = client.get("/api/v1/hr/biometric/devices")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == body["id"]


def test_duplicate_device_code_rejected(client: TestClient) -> None:
    assert _create_device(client).status_code == 201
    again = _create_device(client, name="Other")
    assert again.status_code == 409


def test_create_mapping_and_list(client: TestClient) -> None:
    device_id = _create_device(client).json()["id"]
    response = client.post(
        "/api/v1/hr/biometric/mappings",
        json={
            "employeeId": EMPLOYEE,
            "biometricUserId": "BIO-100",
            "deviceId": device_id,
            "effectiveFrom": "2026-11-01",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["biometricUserId"] == "BIO-100"
    listed = client.get("/api/v1/hr/biometric/mappings", params={"employeeId": EMPLOYEE})
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_manual_sync_refuses_when_disabled_and_writes_skipped_log(client: TestClient, db: Engine) -> None:
    device_id = _create_device(client).json()["id"]
    response = client.post("/api/v1/hr/biometric/sync", json={"deviceId": device_id})
    assert response.status_code == 400, response.text
    assert "disabled" in response.json()["detail"].lower()
    with Session(db) as session:
        log = session.scalars(select(BiometricSyncLog)).one()
        assert log.status == "Skipped"
        assert log.trigger == "Manual"
        assert log.device_id == device_id
        assert log.error_message is not None
        assert "disabled" in log.error_message.lower()
    history = client.get("/api/v1/hr/biometric/sync-logs")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["status"] == "Skipped"


def test_duplicate_punch_protection_external_and_composite(db: Engine, settings: Settings) -> None:
    insert_row(
        db,
        "hr.biometric_device",
        id=1,
        code="GATE-01",
        name="Main gate",
        vendor="ESSL",
        is_sync_enabled=0,
        is_active=1,
    )
    with Session(db) as session:
        service = BiometricService(
            session,
            settings=settings,
            biometric_settings=BiometricSettings(sync_enabled=False, default_secret_id=None),
        )
        punched = datetime(2026, 11, 18, 9, 30, 0)
        assert service.insert_punch_if_new(
            device_id=1,
            biometric_user_id="BIO-100",
            punched_at=punched,
            external_punch_id="EXT-1",
            source="Manual",
        )
        session.commit()
        # Same external id is a duplicate even if the clock differs.
        assert not service.insert_punch_if_new(
            device_id=1,
            biometric_user_id="BIO-100",
            punched_at=datetime(2026, 11, 18, 10, 0, 0),
            external_punch_id="EXT-1",
            source="Manual",
        )
        # Composite fallback when no external id.
        assert service.insert_punch_if_new(
            device_id=1,
            biometric_user_id="BIO-200",
            punched_at=punched,
            external_punch_id=None,
            source="Manual",
        )
        session.commit()
        assert not service.insert_punch_if_new(
            device_id=1,
            biometric_user_id="BIO-200",
            punched_at=punched,
            external_punch_id=None,
            source="Manual",
        )
        session.commit()
        total = session.scalar(select(func.count()).select_from(BiometricPunchLog)) or 0
        assert total == 2


def test_list_punches_empty(client: TestClient) -> None:
    response = client.get("/api/v1/hr/biometric/punches")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_list_punches_returns_enriched_rows(client: TestClient, db: Engine) -> None:
    device_id = _create_device(client).json()["id"]
    assert (
        client.post(
            "/api/v1/hr/biometric/mappings",
            json={
                "employeeId": EMPLOYEE,
                "biometricUserId": "BIO-ENRICH",
                "deviceId": device_id,
                "effectiveFrom": "2026-11-01",
            },
        ).status_code
        == 201
    )
    with Session(db) as session:
        service = BiometricService(
            session,
            settings=Settings(
                environment="test",
                auth_mode="dev",
                dev_username="tester",
                biometric_sync_enabled=False,
                _env_file=None,
            ),
            biometric_settings=BiometricSettings(sync_enabled=False, default_secret_id=None),
        )
        assert service.insert_punch_if_new(
            device_id=device_id,
            biometric_user_id="BIO-ENRICH",
            punched_at=datetime(2026, 11, 20, 9, 15, 0),
            punch_type="IN",
            external_punch_id="EXT-ENRICH-1",
            source="Manual",
        )
        session.commit()

    response = client.get("/api/v1/hr/biometric/punches", params={"page": 1, "pageSize": 20})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    row = body["items"][0]
    assert row["employeeCode"] == "E020"
    assert row["employeeName"] == "Anita"
    assert row["departmentName"] == "Human Resources"
    assert row["deviceName"] == "Main gate"
    assert row["punchType"] == "IN"
    assert row["source"] == "Manual"


def test_view_forbidden_without_permission(settings: Settings, db: Engine) -> None:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    api.dependency_overrides[get_current_user] = lambda: make_user(id=2, permissions=frozenset())

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current:
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/api/v1/hr/biometric/devices")
    assert response.status_code == 403


def test_client_contract_missing_without_inventing_endpoints() -> None:
    from trishul_api.modules.hr.biometric.client import (
        BiometricApiContractMissing,
        BiometricConnectionConfig,
        EsslBiometricClient,
    )

    connection = BiometricConnectionConfig(
        base_url="https://example.invalid",
        credential_secret_name="biometric/essl-dev",
    )
    with EsslBiometricClient(connection, credentials={"token": "x"}) as client:
        with pytest.raises(BiometricApiContractMissing):
            client.fetch_punches(device_external_id=None, since=None, until=None)
        with pytest.raises(BiometricApiContractMissing):
            client.test_connection()
