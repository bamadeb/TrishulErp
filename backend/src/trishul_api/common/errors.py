"""Errors are returned as RFC 7807 problem details, the shape the Angular error interceptor reads."""

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

PROBLEM_JSON = "application/problem+json"


class ApiError(Exception):
    status = 400
    title = "Bad request"
    default_detail: str | None = None

    def __init__(self, detail: str | None = None, errors: dict[str, list[str]] | None = None) -> None:
        self.detail = detail or self.default_detail
        self.errors = errors
        super().__init__(self.detail or self.title)


class Unauthorized(ApiError):
    status = 401
    title = "Not signed in"


class Forbidden(ApiError):
    status = 403
    title = "Not allowed"


class NotFound(ApiError):
    status = 404
    title = "Not found"


class Conflict(ApiError):
    """The record changed after the client loaded it (row_version mismatch)."""

    status = 409
    title = "Record changed"
    default_detail = "Another user changed this record after you opened it. Reload it and try again."


class PreconditionRequired(ApiError):
    status = 428
    title = "If-Match header required"


def problem(status: int, title: str, detail: str | None = None, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {"status": status, "title": title}
    if detail:
        body["detail"] = detail
    body.update({k: v for k, v in extra.items() if v is not None})
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return problem(exc.status, exc.title, exc.detail, errors=exc.errors)

    @app.exception_handler(StaleDataError)
    async def _stale(request: Request, _: StaleDataError) -> JSONResponse:
        # The ORM's row_version check failed during UPDATE: same answer as check_row_version.
        return await _api_error(request, Conflict())

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors: dict[str, list[str]] = {}
        for error in exc.errors():
            # Drop the 'body' / 'query' prefix so keys match the client's field names.
            field = ".".join(str(part) for part in error["loc"][1:]) or str(error["loc"][0])
            errors.setdefault(field, []).append(error["msg"])
        return problem(422, "Please check the form", "Some values are not valid.", errors=errors)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        trace_id = uuid.uuid4().hex
        logger.exception("Unhandled error %s on %s %s", trace_id, request.method, request.url.path, exc_info=exc)
        return problem(500, "Server error", "Something went wrong. Please try again.", traceId=trace_id)
