"""Tracking configuration API: route -> service -> SQL (SQLite)."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

URL = "/api/v1/trk/tracking-config"
PARAMS = f"{URL}/parameters"

# (code, name, type, value, default, unit, min, max, allowed, order) as seeded by migration 0020
SEED = [
    ("movingIntervalMs", "Moving interval", "int", "3000", "3000", "ms", 500, 60000, None, 1),
    (
        "movingPriority",
        "Moving priority",
        "string",
        "HIGH_ACCURACY",
        "HIGH_ACCURACY",
        None,
        None,
        None,
        "HIGH_ACCURACY,BALANCED_POWER_ACCURACY,LOW_POWER,PASSIVE",
        2,
    ),
    ("stationaryCandidateDurationMs", "Stationary duration", "int", "180000", "180000", "ms", 10000, 3600000, None, 3),
    ("stationaryDwellRadiusMeters", "Dwell radius", "decimal", "35", "35", "m", 5, 500, None, 4),
    ("movementRecoveryDisplacementMeters", "Recovery displacement", "decimal", "25", "25", "m", 5, 500, None, 5),
    ("varianceThresholdMoving", "Variance moving", "decimal", None, None, None, 0, None, None, 6),
    ("varianceThresholdStationary", "Variance stationary", "decimal", None, None, None, 0, None, None, 7),
    ("samplingPeriodUs", "Sampling period", "int", None, None, "us", 1000, 1000000, None, 8),
]


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(["core.audit_log", "trk.tracking_config"])
    for code, name, kind, value, default, unit, low, high, allowed, order in SEED:
        insert_row(
            engine,
            "trk.tracking_config",
            code=code,
            name=name,
            value_type=kind,
            value=value,
            default_value=default,
            unit=unit,
            min_value=low,
            max_value=high,
            allowed_values=allowed,
            sort_order=order,
        )
    return engine


def client_for(settings: Settings, db: Engine, permissions: set[str]) -> TestClient:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(id=1, employee_id=5, permissions=frozenset(permissions), branch_ids=None, principal_ids=None)
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=1, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def app_user(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, {"trk.trip.manage"}) as c:  # an engineer's phone: no config permission
        yield c


@pytest.fixture
def admin(settings: Settings, db: Engine) -> Iterator[TestClient]:
    with client_for(settings, db, {"trk.config.manage"}) as c:
        yield c


def if_match(item: dict[str, Any]) -> dict[str, str]:
    return {"If-Match": f'"{item["rowVersion"]}"'}


def parameter(admin: TestClient, code: str) -> dict[str, Any]:
    return next(p for p in admin.get(PARAMS).json() if p["code"] == code)


def put(admin: TestClient, code: str, value: Any) -> Any:
    return admin.put(f"{PARAMS}/{code}", json={"value": value}, headers=if_match(parameter(admin, code)))


# ---------------------------------------------------------------- what the phone reads


def test_phone_gets_the_configured_values(app_user: TestClient) -> None:
    response = app_user.get(URL)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["movingIntervalMs"] == 3000
    assert body["movingPriority"] == "HIGH_ACCURACY"
    assert body["stationaryCandidateDurationMs"] == 180000
    assert body["stationaryDwellRadiusMeters"] == 35
    assert body["movementRecoveryDisplacementMeters"] == 25


def test_uncalibrated_values_are_null_and_listed(app_user: TestClient) -> None:
    body = app_user.get(URL).json()
    assert body["varianceThresholdMoving"] is None
    assert body["varianceThresholdStationary"] is None
    assert body["samplingPeriodUs"] is None
    assert body["calibrationPending"] == ["varianceThresholdMoving", "varianceThresholdStationary", "samplingPeriodUs"]


def test_only_sign_in_is_needed_to_read_the_configuration(settings: Settings, db: Engine) -> None:
    with client_for(settings, db, set()) as nobody:
        assert nobody.get(URL).status_code == 200


def test_version_header_lets_the_phone_skip_unchanged_configuration(app_user: TestClient, admin: TestClient) -> None:
    first = app_user.get(URL)
    etag = first.headers["etag"]
    assert etag == f'"{first.json()["version"]}"'
    assert app_user.get(URL, headers={"If-None-Match": etag}).status_code == 304
    assert put(admin, "movingIntervalMs", 5000).status_code == 200
    changed = app_user.get(URL, headers={"If-None-Match": etag})
    assert changed.status_code == 200
    assert changed.json()["movingIntervalMs"] == 5000
    assert changed.json()["version"] != first.json()["version"]


# ---------------------------------------------------------------- administration


def test_parameter_list_needs_the_config_permission(app_user: TestClient) -> None:
    assert app_user.get(PARAMS).status_code == 403


def test_administrator_sees_limits_units_and_calibration_state(admin: TestClient) -> None:
    listed = {p["code"]: p for p in admin.get(PARAMS).json()}
    assert len(listed) == 8
    interval = listed["movingIntervalMs"]
    assert (interval["unit"], interval["minValue"], interval["maxValue"], interval["isCalibrated"]) == (
        "ms",
        500,
        60000,
        True,
    )
    assert listed["movingPriority"]["allowedValues"][0] == "HIGH_ACCURACY"
    assert listed["varianceThresholdMoving"]["isCalibrated"] is False


def test_administrator_calibrates_a_threshold(admin: TestClient, app_user: TestClient) -> None:
    updated = put(admin, "varianceThresholdMoving", 0.35)
    assert updated.status_code == 200, updated.text
    assert (updated.json()["value"], updated.json()["isCalibrated"]) == ("0.35", True)
    body = app_user.get(URL).json()
    assert body["varianceThresholdMoving"] == 0.35
    assert "varianceThresholdMoving" not in body["calibrationPending"]


def test_administrator_changes_a_value_and_the_phone_sees_it(admin: TestClient, app_user: TestClient) -> None:
    assert put(admin, "stationaryDwellRadiusMeters", 40.5).json()["value"] == "40.5"
    assert put(admin, "movingPriority", "BALANCED_POWER_ACCURACY").status_code == 200
    body = app_user.get(URL).json()
    assert (body["stationaryDwellRadiusMeters"], body["movingPriority"]) == (40.5, "BALANCED_POWER_ACCURACY")


@pytest.mark.parametrize(
    ("code", "value", "message"),
    [
        ("movingIntervalMs", 100, "at least 500"),
        ("movingIntervalMs", 90000, "at most 60000"),
        ("movingIntervalMs", 2500.5, "whole number"),
        ("movingIntervalMs", "fast", "number"),
        ("stationaryDwellRadiusMeters", 2, "at least 5"),
        ("movingPriority", "TURBO", "one of"),
        ("movingPriority", 5, "text"),
        ("samplingPeriodUs", 10, "at least 1000"),
        ("varianceThresholdMoving", -1, "at least 0"),
    ],
)
def test_invalid_values_are_rejected_with_the_reason(admin: TestClient, code: str, value: Any, message: str) -> None:
    response = put(admin, code, value)
    assert response.status_code == 422
    assert message in response.json()["errors"]["value"][0]


def test_a_parameter_with_a_default_cannot_be_cleared(admin: TestClient) -> None:
    assert put(admin, "movingIntervalMs", None).status_code == 422


def test_an_uncalibrated_parameter_can_be_cleared_again(admin: TestClient, app_user: TestClient) -> None:
    put(admin, "samplingPeriodUs", 20000)
    assert app_user.get(URL).json()["samplingPeriodUs"] == 20000
    assert put(admin, "samplingPeriodUs", None).status_code == 200
    assert app_user.get(URL).json()["samplingPeriodUs"] is None


def test_unknown_parameter_is_not_found(admin: TestClient) -> None:
    response = admin.put(f"{PARAMS}/nope", json={"value": 1}, headers={"If-Match": '"AAAAAAAAB9E="'})
    assert response.status_code == 404


def test_changing_needs_the_config_permission_and_a_row_version(app_user: TestClient, admin: TestClient) -> None:
    assert (
        app_user.put(
            f"{PARAMS}/movingIntervalMs", json={"value": 4000}, headers={"If-Match": '"AAAAAAAAB9E="'}
        ).status_code
        == 403
    )
    assert admin.put(f"{PARAMS}/movingIntervalMs", json={"value": 4000}).status_code == 428


def test_unknown_fields_are_rejected(admin: TestClient) -> None:
    response = admin.put(
        f"{PARAMS}/movingIntervalMs",
        json={"value": 4000, "code": "x"},
        headers=if_match(parameter(admin, "movingIntervalMs")),
    )
    assert response.status_code == 422
