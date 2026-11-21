"""Companies & brands management through the API (SQLite)."""

from collections.abc import Iterator

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

URL = "/api/v1/core/brands"
ACTOR_ID = 1


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(["core.company", "core.principal", "core.audit_log"])
    insert_row(engine, "core.company", id=1, code="BYDI", legal_name="BYD India Pvt Ltd", trade_name="BYD India")
    insert_row(engine, "core.company", id=2, code="KAAS", legal_name="Kaashi Ltd")
    insert_row(engine, "core.principal", id=1, code="BYD", name="BYD", company_id=1)
    return engine


def make_client(settings: Settings, db: Engine, permissions: frozenset[str]) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(id=ACTOR_ID, permissions=permissions, branch_ids=None, principal_ids=None)
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=ACTOR_ID, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    yield from make_client(settings, db, frozenset({"core.brand.manage"}))


@pytest.fixture
def outsider(settings: Settings, db: Engine) -> Iterator[TestClient]:
    yield from make_client(settings, db, frozenset({"core.customer.view"}))


def test_needs_the_manage_permission(outsider: TestClient) -> None:
    assert outsider.get(URL).status_code == 403


def test_company_dropdown_options(client: TestClient) -> None:
    companies = client.get(f"{URL}/form-options").json()["companies"]
    assert [c["name"] for c in companies] == ["BYD India", "Kaashi Ltd"]


def test_add_change_and_deactivate_a_brand(client: TestClient) -> None:
    assert client.get(URL).json()[0]["companyName"] == "BYD India"

    created = client.post(URL, json={"code": "kaashi", "name": "Kaashi", "companyId": 2})
    assert created.status_code == 201
    brand = created.json()
    assert (brand["code"], brand["companyName"]) == ("KAASHI", "Kaashi Ltd")

    headers = {"If-Match": f'"{brand["rowVersion"]}"'}
    changed = client.patch(f"{URL}/{brand['id']}", json={"companyId": None}, headers=headers)
    assert changed.status_code == 200, changed.text
    assert changed.json()["companyName"] is None

    off = client.post(f"{URL}/{brand['id']}/deactivate")
    assert off.status_code == 200 and off.json()["isActive"] is False
    assert client.post(f"{URL}/{brand['id']}/activate").json()["isActive"] is True


def test_company_must_exist(client: TestClient) -> None:
    assert client.post(URL, json={"code": "x", "name": "X", "companyId": 99}).status_code == 400


def test_brand_code_must_be_unique(client: TestClient) -> None:
    assert client.post(URL, json={"code": "byd", "name": "Other"}).status_code == 409


def test_add_a_company_for_the_dropdown(client: TestClient) -> None:
    body = {"code": "kss", "legalName": "Kasi Sales & Services", "tradeName": " "}
    created = client.post(f"{URL}/companies", json=body)
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "Kasi Sales & Services"
    names = [c["name"] for c in client.get(f"{URL}/form-options").json()["companies"]]
    assert "Kasi Sales & Services" in names
    assert client.post(f"{URL}/companies", json={"code": "KSS", "legalName": "Again"}).status_code == 409


def test_inspection_report_switch(client: TestClient) -> None:
    brand = client.post(URL, json={"code": "kaashi", "name": "Kaashi"}).json()
    assert brand["inspectionReportRequired"] is True  # new brands need the full report

    headers = {"If-Match": f'"{brand["rowVersion"]}"'}
    off = client.patch(f"{URL}/{brand['id']}", json={"inspectionReportRequired": False}, headers=headers)
    assert off.status_code == 200, off.text
    assert off.json()["inspectionReportRequired"] is False
