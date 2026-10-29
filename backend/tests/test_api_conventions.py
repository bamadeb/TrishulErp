"""Every endpoint follows the API standard (docs/Trishul_API_Standards.md).

The rules are checked on the OpenAPI document, so they hold for the API as clients see it. A new
endpoint that breaks one fails here with the rule and the endpoint named.
"""

import re
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from trishul_api.auth import get_current_user
from trishul_api.config import Settings
from trishul_api.main import create_api_v1

from .conftest import make_user

MODULES = {"core", "svc", "inv", "pur", "sal", "pre", "hr", "acc", "int", "rpt", "trk"}
TOP_LEVEL_PATHS = {"/me"}  # the signed-in user; everything else lives under a module prefix
SEGMENT = re.compile(r"^(?:[a-z0-9]+(?:-[a-z0-9]+)*|\{[a-z][a-zA-Z0-9]*\})$")  # kebab-case, {camelCase}
CAMEL_CASE = re.compile(r"^[a-z][a-zA-Z0-9]*$")
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
STANDARD_ERRORS = {"401", "403", "422", "500"}
PROBLEM_REF = "#/components/schemas/ProblemDetails"


def _document() -> dict[str, Any]:
    settings = Settings(environment="test", auth_mode="dev", dev_username="tester", _env_file=None)
    return create_api_v1(settings).openapi()


DOCUMENT = _document()
ROWS: list[tuple[str, str, dict[str, Any]]] = [
    (path, method, operation) for path, methods in DOCUMENT["paths"].items() for method, operation in methods.items()
]
OPERATIONS = [pytest.param(*row, id=f"{row[1].upper()} {row[0]}") for row in ROWS]


def is_item_path(path: str) -> bool:
    return path.rstrip("/").split("/")[-1].startswith("{")


def is_action_path(path: str) -> bool:
    """POST /svc/service-calls/{callId}/assign: a business action on one record."""
    segments = path.strip("/").split("/")
    return len(segments) >= 3 and segments[-2].startswith("{") and not segments[-1].startswith("{")


def schema_of(operation: dict[str, Any], status: str) -> dict[str, Any]:
    content = operation["responses"].get(status, {}).get("content", {})
    schema: dict[str, Any] = content.get("application/json", {}).get("schema", {})
    return schema


def resolve(schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    resolved: dict[str, Any] = DOCUMENT["components"]["schemas"][ref.rsplit("/", 1)[-1]] if ref else schema
    return resolved


def is_list_response(operation: dict[str, Any]) -> bool:
    schema = schema_of(operation, "200")
    return schema.get("type") == "array" or schema.get("$ref", "").rsplit("/", 1)[-1].startswith("Page")


def expected(path: str, method: str, operation: dict[str, Any]) -> tuple[str | None, str]:
    """(required function-name prefix, success status) for this kind of endpoint."""
    if method == "get":
        if is_item_path(path):
            return "get_", "200"
        return ("list_" if is_list_response(operation) else "get_"), "200"
    if method == "post":
        return (None, "200") if is_action_path(path) else ("create_", "201")
    if method in ("put", "patch"):
        return "update_", "200"
    if method == "delete":
        return "delete_", "204"
    raise AssertionError(f"method {method.upper()} is not allowed; use GET, POST, PUT, PATCH or DELETE")


@pytest.mark.parametrize(("path", "method", "operation"), OPERATIONS)
def test_url_shape(path: str, method: str, operation: dict[str, Any]) -> None:
    segments = path.strip("/").split("/")
    assert path in TOP_LEVEL_PATHS or segments[0] in MODULES, (
        f"{path}: must start with a module prefix ({', '.join(sorted(MODULES))})"
    )
    for segment in segments:
        assert SEGMENT.match(segment), f"{path}: '{segment}' must be kebab-case, or a {{camelCase}} parameter"


@pytest.mark.parametrize(("path", "method", "operation"), OPERATIONS)
def test_function_name_and_status(path: str, method: str, operation: dict[str, Any]) -> None:
    prefix, success = expected(path, method, operation)
    name = operation["operationId"]
    assert SNAKE_CASE.match(name), f"{name}: function names are snake_case"
    if prefix:
        assert name.startswith(prefix), f"{method.upper()} {path}: name the function {prefix}..., not {name}"
    assert success in operation["responses"], f"{method.upper()} {path}: success status must be {success}"
    assert operation.get("summary"), f"{method.upper()} {path}: add summary= (shown in Swagger)"


def test_function_names_are_unique() -> None:
    names = [operation["operationId"] for _, _, operation in ROWS]
    assert len(names) == len(set(names)), "function names become client function names: keep them unique"


@pytest.mark.parametrize(("path", "method", "operation"), OPERATIONS)
def test_errors_are_documented_as_problem_details(path: str, method: str, operation: dict[str, Any]) -> None:
    responses = operation["responses"]
    required = set(STANDARD_ERRORS)
    if is_item_path(path) or is_action_path(path):
        required.add("404")  # responses=NOT_FOUND_RESPONSE
    if method in ("put", "patch", "delete"):
        required |= {"409", "428"}  # responses=CONCURRENCY_RESPONSES, with If-Match / rowVersion
    for status in sorted(required):
        assert status in responses, f"{method.upper()} {path}: document {status}"
        assert schema_of(operation, status).get("$ref") == PROBLEM_REF, (
            f"{method.upper()} {path}: {status} must use ProblemDetails"
        )


@pytest.mark.parametrize(("path", "method", "operation"), OPERATIONS)
def test_parameters(path: str, method: str, operation: dict[str, Any]) -> None:
    params = operation.get("parameters", [])
    for param in params:
        assert param["in"] in ("path", "query"), (
            f"{path}: '{param['name']}' header parameters are sent by the client interceptor, not per endpoint"
        )
        assert CAMEL_CASE.match(param["name"]), f"{path}: parameter '{param['name']}' must be camelCase"
    if is_list_response(operation) and schema_of(operation, "200").get("type") != "array":
        names = {p["name"] for p in params}
        assert {"page", "pageSize"} <= names, f"{path}: paged lists take a query model extending PageQuery"


@pytest.mark.parametrize(("path", "method", "operation"), OPERATIONS)
def test_request_bodies(path: str, method: str, operation: dict[str, Any]) -> None:
    body = operation.get("requestBody")
    if method in ("get", "delete"):
        assert body is None, f"{method.upper()} {path}: no request body"
        return
    if method in ("put", "patch") or (method == "post" and not is_action_path(path)):
        assert body is not None, f"{method.upper()} {path}: needs a request body"
    if body:
        schema = resolve(body["content"]["application/json"]["schema"])
        assert schema.get("additionalProperties") is False, (
            f"{method.upper()} {path}: request bodies extend InputModel (unknown fields rejected)"
        )


PROTECTED = [pytest.param(*row, id=f"{row[1].upper()} {row[0]}") for row in ROWS if "x-access" not in row[2]]


@pytest.mark.parametrize(("path", "method", "operation"), PROTECTED)
def test_every_endpoint_requires_a_permission(
    path: str, method: str, operation: dict[str, Any], api: FastAPI, client: TestClient
) -> None:
    """A signed-in user without permissions gets 403 everywhere, except on endpoints marked with
    openapi_extra=SIGNED_IN_USERS."""
    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset())
    url = "/api/v1" + re.sub(r"\{[^}]+\}", "1", path)
    response = client.request(method.upper(), url, json={} if method in ("post", "put", "patch") else None)
    assert response.status_code == 403, (
        f"{method.upper()} {path}: add dependencies=[Depends(require_permission(...))], "
        "or openapi_extra=SIGNED_IN_USERS if every signed-in user may call it"
    )
