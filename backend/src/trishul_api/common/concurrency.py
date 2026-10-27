import base64
import binascii
from typing import Annotated

from fastapi import Header

from trishul_api.common.errors import ApiError, Conflict, PreconditionRequired


def if_match_row_version(if_match: Annotated[str | None, Header(include_in_schema=False)] = None) -> bytes:
    """Dependency for update/delete endpoints: the row_version the client loaded, from If-Match.

    Not listed per endpoint in OpenAPI: the Angular client sends it via withRowVersion(...), and the
    428 / 409 responses (CONCURRENCY_RESPONSES) document it."""
    if not if_match:
        raise PreconditionRequired("Send the record's rowVersion in the If-Match header.")
    try:
        return base64.b64decode(if_match.strip().removeprefix("W/").strip('"'), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ApiError("If-Match is not a valid rowVersion.") from exc


def check_row_version(current: bytes, expected: bytes) -> None:
    """Fail fast before applying changes; the ORM re-checks atomically in the UPDATE."""
    if current != expected:
        raise Conflict()
