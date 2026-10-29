"""Device registration/logout and the pre-sales 'assigned to me' list."""

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from trishul_api.auth import get_current_user
from trishul_api.common.schemas import Page
from trishul_api.modules.core.devices.router import get_device_service
from trishul_api.modules.presales.repository import SalesActivityRepository
from trishul_api.modules.presales.router import get_sales_activity_repository
from trishul_api.modules.presales.schemas import AssignedSalesActivityListItem, AssignedSalesActivityQuery

from .conftest import make_user
from .helpers import mssql_sql


def _device() -> SimpleNamespace:
    return SimpleNamespace(
        id=42,
        device_id="ANDROID-a1b2c3",
        platform="Android",
        app_version="1.4.0",
        push_token="fcm:xyz",
        last_seen_at=datetime(2026, 10, 28, 6, 30),
        is_active=True,
        row_version=b"\x00\x00\x00\x00\x00\x00\x07\xd1",
    )


class FakeDeviceService:
    def __init__(self) -> None:
        self.registered: list[tuple[int, Any]] = []
        self.logged_out: list[tuple[int, str]] = []

    def register(self, user: Any, data: Any) -> tuple[SimpleNamespace, bool]:
        self.registered.append((user.id, data))
        return _device(), True

    def logout(self, user: Any, device_id: str) -> SimpleNamespace:
        self.logged_out.append((user.id, device_id))
        return _device()


def use_device_service(api: FastAPI) -> FakeDeviceService:
    service = FakeDeviceService()
    api.dependency_overrides[get_device_service] = lambda: service
    return service


# ---------------------------------------------------------------- device endpoints


def test_register_device_returns_201(api: FastAPI, client: TestClient, signed_in: Any) -> None:
    service = use_device_service(api)
    response = client.post(
        "/api/v1/core/user-devices",
        json={"deviceId": "ANDROID-a1b2c3", "platform": "Android", "appVersion": "1.4.0", "pushToken": "fcm:xyz"},
    )
    assert response.status_code == 201
    assert service.registered[0][0] == signed_in.id
    body = response.json()
    assert body["deviceId"] == "ANDROID-a1b2c3"
    assert body["isActive"] is True
    assert body["rowVersion"] == "AAAAAAAAB9E="


def test_register_device_rejects_unknown_platform(api: FastAPI, client: TestClient, signed_in: Any) -> None:
    use_device_service(api)
    response = client.post("/api/v1/core/user-devices", json={"deviceId": "X", "platform": "Blackberry"})
    assert response.status_code == 422
    assert "platform" in response.json()["errors"]


def test_register_device_rejects_unknown_fields(api: FastAPI, client: TestClient, signed_in: Any) -> None:
    use_device_service(api)
    response = client.post(
        "/api/v1/core/user-devices",
        json={"deviceId": "X", "platform": "Android", "appUserId": 999},  # mass-assignment attempt
    )
    assert response.status_code == 422


def test_logout_device(api: FastAPI, client: TestClient, signed_in: Any) -> None:
    service = use_device_service(api)
    response = client.post("/api/v1/core/user-devices/ANDROID-a1b2c3/logout")
    assert response.status_code == 200
    assert service.logged_out == [(signed_in.id, "ANDROID-a1b2c3")]


# ---------------------------------------------------------------- pre-sales assigned list


class FakeSalesActivityRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[int, AssignedSalesActivityQuery]] = []

    def list_assigned(self, employee_id: int, query: AssignedSalesActivityQuery) -> Page[AssignedSalesActivityListItem]:
        self.calls.append((employee_id, query))
        item = AssignedSalesActivityListItem(
            id=77,
            activity_type="Visit",
            customer_name="Odisha Mining Corp",
            lead_name=None,
            planned_at=datetime(2026, 10, 29, 4, 30),
            started_at=None,
            ended_at=None,
            notes="Demo of EX210",
            next_follow_up_at=None,
            row_version=b"\x00\x00\x00\x00\x00\x00\x07\xd2",
        )
        return Page(items=[item], total=1, page=query.page, page_size=query.page_size)


def use_sales_repo(api: FastAPI) -> FakeSalesActivityRepository:
    repo = FakeSalesActivityRepository()
    api.dependency_overrides[get_sales_activity_repository] = lambda: repo
    return repo


def _salesperson(api: FastAPI, **overrides: object) -> Any:
    user = make_user(permissions=frozenset({"pre.activity.view.assigned"}), **overrides)
    api.dependency_overrides[get_current_user] = lambda: user
    return user


def test_assigned_activities_scope_to_the_signed_in_salesperson(api: FastAPI, client: TestClient) -> None:
    _salesperson(api, employee_id=5)
    repo = use_sales_repo(api)
    response = client.get("/api/v1/pre/sales-activities/assigned-to-me?activityType=Visit&activityType=Demo")
    assert response.status_code == 200
    employee_id, query = repo.calls[0]
    assert employee_id == 5
    assert query.activity_type == ["Visit", "Demo"]
    assert response.json()["items"][0]["customerName"] == "Odisha Mining Corp"


def test_assigned_activities_need_permission(api: FastAPI, client: TestClient) -> None:
    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset())
    use_sales_repo(api)
    assert client.get("/api/v1/pre/sales-activities/assigned-to-me").status_code == 403


def test_assigned_activities_forbid_accounts_with_no_employee(api: FastAPI, client: TestClient) -> None:
    _salesperson(api, employee_id=None)
    repo = use_sales_repo(api)
    response = client.get("/api/v1/pre/sales-activities/assigned-to-me")
    assert response.status_code == 403
    assert repo.calls == []


def test_assigned_activities_reject_unknown_type(api: FastAPI, client: TestClient) -> None:
    _salesperson(api)
    use_sales_repo(api)
    response = client.get("/api/v1/pre/sales-activities/assigned-to-me?activityType=Bogus")
    assert response.status_code == 422
    assert "activityType.0" in response.json()["errors"]


# ---------------------------------------------------------------- pre-sales query SQL


def _assigned_sql(employee_id: int, **query: Any) -> str:
    statement = SalesActivityRepository.assigned_statement(employee_id, AssignedSalesActivityQuery(**query))
    return mssql_sql(statement.offset(0).limit(20))


def test_assigned_activities_sql_scopes_to_employee() -> None:
    assert "pre.sales_activity.employee_id = 5" in _assigned_sql(5)


def test_assigned_activities_sql_defaults_to_open_field_activities() -> None:
    text = _assigned_sql(5)
    assert "pre.sales_activity.activity_type IN (N'Visit', N'Demo', N'Meeting')" in text
    assert "pre.sales_activity.ended_at IS NULL" in text


def test_assigned_activities_sql_honours_explicit_type() -> None:
    text = _assigned_sql(5, activity_type=["Demo"])
    assert "pre.sales_activity.activity_type IN (N'Demo')" in text
    assert "ended_at IS NULL" not in text
