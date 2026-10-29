from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from trishul_api.auth import CurrentUser, RequestScope, get_current_user
from trishul_api.common.schemas import Page
from trishul_api.modules.core.router import get_core_repository
from trishul_api.modules.core.schemas import BranchRef, LookupValueOut, PrincipalRef
from trishul_api.modules.service.router import get_service_call_repository
from trishul_api.modules.service.schemas import (
    AssignedServiceCallListItem,
    AssignedServiceCallQuery,
    ServiceCallListItem,
    ServiceCallQuery,
)

from .conftest import make_user


class FakeCoreRepository:
    def branches(self, ids: object) -> list[BranchRef]:
        return [BranchRef(id=1, code="PUN", name="Pune")]

    def principals(self, ids: object) -> list[PrincipalRef]:
        return [PrincipalRef(id=10, code="ATLAS_COPCO", name="Atlas Copco")]

    def lookup_values(self, type_code: str) -> list[LookupValueOut] | None:
        if type_code != "CALL_SOURCE":
            return None
        return [LookupValueOut(id=1, code="PHONE", name="Phone", sort_order=1)]


class FakeServiceCallRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[RequestScope, ServiceCallQuery]] = []
        self.assigned_calls: list[tuple[int, RequestScope, AssignedServiceCallQuery]] = []

    def list_assigned(
        self, engineer_id: int, scope: RequestScope, query: AssignedServiceCallQuery
    ) -> Page[AssignedServiceCallListItem]:
        self.assigned_calls.append((engineer_id, scope, query))
        item = AssignedServiceCallListItem(
            id=1001,
            call_no="SC/25-26/04210",
            received_at=datetime(2026, 10, 23, 5, 30),
            principal_code="ATLAS_COPCO",
            customer_name="Sahyadri Pharma",
            site_name="Plant 2",
            site_address="MIDC Bhosari, Pune",
            site_latitude=18.6298,
            site_longitude=73.8470,
            machine_serial_no="API600000",
            machine_model="GA 37 VSD+",
            complaint_description="High discharge temperature",
            priority="Critical",
            is_machine_down=True,
            is_asc_priority=False,
            coverage_type="Warranty",
            current_status="Assigned",
            caller_name="Mr. Deshmukh",
            caller_phone="9800000000",
            sla_due_at=None,
            row_version=b"\x00\x00\x00\x00\x00\x00\x07\xd1",
        )
        return Page(items=[item], total=1, page=query.page, page_size=query.page_size)

    def list(self, scope: RequestScope, query: ServiceCallQuery) -> Page[ServiceCallListItem]:
        self.calls.append((scope, query))
        item = ServiceCallListItem(
            id=1001,
            call_no="SC/25-26/04210",
            received_at=datetime(2026, 10, 23, 5, 30),
            principal_code="ATLAS_COPCO",
            customer_name="Sahyadri Pharma",
            machine_serial_no="API600000",
            machine_model="GA 37 VSD+",
            complaint_description="High discharge temperature",
            priority="Critical",
            is_machine_down=True,
            is_asc_priority=False,
            coverage_type="Warranty",
            current_status="Logged",
            assigned_engineer_name=None,
            oem_call_id=None,
            sla_due_at=None,
            row_version=b"\x00\x00\x00\x00\x00\x00\x07\xd1",
        )
        return Page(items=[item], total=1, page=query.page, page_size=query.page_size)


def use_service_repo(api: FastAPI) -> FakeServiceCallRepository:
    repo = FakeServiceCallRepository()
    api.dependency_overrides[get_service_call_repository] = lambda: repo
    return repo


def test_requires_a_bearer_token(client: TestClient) -> None:
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["title"] == "Not signed in"


def test_me_returns_the_angular_auth_contract(api: FastAPI, client: TestClient, signed_in: CurrentUser) -> None:
    api.dependency_overrides[get_core_repository] = FakeCoreRepository
    body = client.get("/api/v1/me", headers={"Authorization": "Bearer x"}).json()
    assert body == {
        "id": 7,
        "username": "team.lead",
        "displayName": "Rahul Patil",
        "email": "rahul@example.com",
        "defaultBranchId": 1,
        "permissions": ["svc.call.assign"],
        "branches": [{"id": 1, "code": "PUN", "name": "Pune"}],
        "principals": [{"id": 10, "code": "ATLAS_COPCO", "name": "Atlas Copco"}],
    }


def test_lookups(api: FastAPI, client: TestClient, signed_in: CurrentUser) -> None:
    api.dependency_overrides[get_core_repository] = FakeCoreRepository
    assert client.get("/api/v1/core/lookups/CALL_SOURCE/values").json() == [
        {"id": 1, "code": "PHONE", "name": "Phone", "sortOrder": 1}
    ]
    assert client.get("/api/v1/core/lookups/NOPE/values").status_code == 404
    assert client.get("/api/v1/core/lookups/bad-code/values").status_code == 422


def test_service_calls_parse_query_and_scope(api: FastAPI, client: TestClient, signed_in: CurrentUser) -> None:
    repo = use_service_repo(api)
    response = client.get(
        "/api/v1/svc/service-calls?page=2&pageSize=50&sort=-slaDueAt&search=Sahyadri"
        "&status=Logged&status=Awaiting%20parts&priority=Critical",
        headers={"X-Branch-Id": "2", "X-Principal-Id": "10"},
    )
    assert response.status_code == 200

    scope, query = repo.calls[0]
    assert scope == RequestScope(branch_id=2, principal_id=10)
    assert (query.page, query.page_size, query.sort, query.search) == (2, 50, "-slaDueAt", "Sahyadri")
    assert query.status == ["Logged", "Awaiting parts"]
    assert query.priority == ["Critical"]

    body = response.json()
    assert (body["total"], body["page"], body["pageSize"]) == (1, 2, 50)
    item = body["items"][0]
    assert item["callNo"] == "SC/25-26/04210"
    assert item["receivedAt"] == "2026-10-23T05:30:00Z"
    assert item["rowVersion"] == "AAAAAAAAB9E="


def test_service_calls_default_to_the_users_branch(api: FastAPI, client: TestClient, signed_in: CurrentUser) -> None:
    repo = use_service_repo(api)
    client.get("/api/v1/svc/service-calls")
    assert repo.calls[0][0] == RequestScope(branch_id=1, principal_id=None)


def test_service_calls_reject_branches_and_brands_outside_the_users_scope(
    api: FastAPI, client: TestClient, signed_in: CurrentUser
) -> None:
    use_service_repo(api)
    assert client.get("/api/v1/svc/service-calls", headers={"X-Branch-Id": "9"}).status_code == 403
    assert client.get("/api/v1/svc/service-calls", headers={"X-Principal-Id": "99"}).status_code == 403


def test_unrestricted_users_may_pick_any_branch(api: FastAPI, client: TestClient) -> None:
    user = make_user(roles=frozenset({"ADMIN"}), branch_ids=None, principal_ids=None)
    api.dependency_overrides[get_current_user] = lambda: user
    use_service_repo(api)
    assert client.get("/api/v1/svc/service-calls", headers={"X-Branch-Id": "9"}).status_code == 200


def test_service_calls_need_a_service_permission(api: FastAPI, client: TestClient) -> None:
    user = make_user(permissions=frozenset({"sal.invoice.post"}))
    api.dependency_overrides[get_current_user] = lambda: user
    use_service_repo(api)
    response = client.get("/api/v1/svc/service-calls")
    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have permission for this action."


def test_invalid_filters_return_field_errors(api: FastAPI, client: TestClient, signed_in: CurrentUser) -> None:
    use_service_repo(api)
    response = client.get("/api/v1/svc/service-calls?status=Bogus&pageSize=1000")
    assert response.status_code == 422
    errors = response.json()["errors"]
    assert "status.0" in errors
    assert "pageSize" in errors


def _engineer(api: FastAPI, **overrides: object) -> CurrentUser:
    user = make_user(permissions=frozenset({"svc.call.view.assigned"}), **overrides)
    api.dependency_overrides[get_current_user] = lambda: user
    return user


def test_assigned_calls_scope_to_the_signed_in_engineer(api: FastAPI, client: TestClient) -> None:
    _engineer(api, employee_id=42)
    repo = use_service_repo(api)
    response = client.get(
        "/api/v1/svc/service-calls/assigned-to-me?status=Assigned&status=Trip%20started&pageSize=50",
        headers={"X-Branch-Id": "2", "X-Principal-Id": "10"},
    )
    assert response.status_code == 200
    engineer_id, scope, query = repo.assigned_calls[0]
    assert engineer_id == 42
    assert scope == RequestScope(branch_id=2, principal_id=10)
    assert query.status == ["Assigned", "Trip started"]

    item = response.json()["items"][0]
    assert item["callNo"] == "SC/25-26/04210"
    assert (item["siteLatitude"], item["siteLongitude"]) == (18.6298, 73.847)
    assert item["callerPhone"] == "9800000000"


def test_assigned_calls_need_the_assigned_view_permission(api: FastAPI, client: TestClient) -> None:
    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset({"svc.call.view"}))
    use_service_repo(api)
    assert client.get("/api/v1/svc/service-calls/assigned-to-me").status_code == 403


def test_assigned_calls_forbid_accounts_with_no_employee(api: FastAPI, client: TestClient) -> None:
    _engineer(api, employee_id=None)
    repo = use_service_repo(api)
    response = client.get("/api/v1/svc/service-calls/assigned-to-me")
    assert response.status_code == 403
    assert "not linked to a service engineer" in response.json()["detail"]
    assert repo.assigned_calls == []  # the query never runs


def test_assigned_calls_reject_an_unknown_status(api: FastAPI, client: TestClient) -> None:
    _engineer(api)
    use_service_repo(api)
    response = client.get("/api/v1/svc/service-calls/assigned-to-me?status=Bogus")
    assert response.status_code == 422
    assert "status.0" in response.json()["errors"]


def test_unknown_routes_are_problem_json(client: TestClient) -> None:
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
