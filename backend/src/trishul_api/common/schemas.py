import base64
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Base for response bodies and query models: snake_case in Python, camelCase in JSON.

    In OpenAPI, response fields with defaults are still required (responses always include them),
    so the generated TypeScript types aren't needlessly optional."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        json_schema_serialization_defaults_required=True,
    )


class InputModel(ApiModel):
    """Base for request bodies. Unknown fields are rejected, so a client can't set fields the
    endpoint doesn't offer (branchId, approvedByUserId, ...): OWASP API3, mass assignment.
    Strings are trimmed; use Decimal for money, never float."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _as_utc(value: datetime) -> datetime:
    # DATETIME2 columns hold UTC (SYSUTCDATETIME) but come back without a zone.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


UtcDateTime = Annotated[datetime, AfterValidator(_as_utc)]
"""A UTC timestamp, serialised with its offset so browsers convert it to local time correctly."""

RowVersion = Annotated[bytes, PlainSerializer(lambda v: base64.b64encode(v).decode("ascii"), return_type=str)]
"""SQL Server ROWVERSION, sent to clients as base64 and returned in If-Match on updates."""


class PageQuery(ApiModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)
    sort: str | None = Field(None, max_length=40, description="Field name; prefix with '-' for descending.")
    search: str | None = Field(None, max_length=100)


class Page[T](ApiModel):
    items: list[T]
    total: int
    page: int
    page_size: int
