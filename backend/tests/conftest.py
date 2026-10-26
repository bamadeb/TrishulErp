from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from trishul_api.auth import CurrentUser, get_current_user
from trishul_api.config import Settings
from trishul_api.main import create_app


def make_user(**overrides: object) -> CurrentUser:
    values: dict[str, object] = {
        "id": 7,
        "username": "team.lead",
        "display_name": "Rahul Patil",
        "email": "rahul@example.com",
        "default_branch_id": 1,
        "roles": frozenset({"TEAM_LEAD"}),
        "permissions": frozenset({"svc.call.assign"}),
        "branch_ids": frozenset({1, 2}),
        "principal_ids": frozenset({10}),
    }
    values.update(overrides)
    return CurrentUser(**values)  # type: ignore[arg-type]


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test", auth_mode="dev", dev_username="tester", _env_file=None)


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    # The engine is never connected: tests replace the repositories that would use it.
    return create_app(settings, engine=create_engine("sqlite://"))


@pytest.fixture
def api(app: FastAPI) -> FastAPI:
    """The mounted /api/v1 application: dependency overrides go here, not on the root app."""
    api_v1: FastAPI = app.state.api_v1
    return api_v1


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def signed_in(api: FastAPI) -> CurrentUser:
    user = make_user()
    api.dependency_overrides[get_current_user] = lambda: user
    return user
