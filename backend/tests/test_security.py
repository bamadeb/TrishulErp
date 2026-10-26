import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from trishul_api.common.schemas import InputModel


def test_api_responses_carry_security_headers(client: TestClient) -> None:
    headers = client.get("/api/v1/me").headers  # 401, still protected
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["strict-transport-security"].startswith("max-age=")
    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert headers["cache-control"] == "no-store"
    assert headers["x-frame-options"] == "DENY"


def test_swagger_ui_is_allowed_to_load(client: TestClient) -> None:
    headers = client.get("/api/v1/docs").headers
    assert "content-security-policy" not in headers
    assert headers["x-content-type-options"] == "nosniff"


def test_cors_allows_only_configured_origins(client: TestClient) -> None:
    preflight = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}
    allowed = client.options("/api/v1/me", headers={"Origin": "http://localhost:4200", **preflight})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:4200"
    denied = client.options("/api/v1/me", headers={"Origin": "https://evil.example.com", **preflight})
    assert "access-control-allow-origin" not in denied.headers


class CreateThing(InputModel):
    customer_id: int
    remarks: str | None = None


def test_input_models_reject_unknown_fields() -> None:
    # A client must not be able to set fields the endpoint doesn't offer (OWASP API3).
    with pytest.raises(ValidationError, match="branchId"):
        CreateThing.model_validate({"customerId": 1, "branchId": 99})


def test_input_models_accept_camel_case_and_trim_strings() -> None:
    thing = CreateThing.model_validate({"customerId": 1, "remarks": "  urgent  "})
    assert (thing.customer_id, thing.remarks) == (1, "urgent")
