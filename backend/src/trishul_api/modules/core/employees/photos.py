"""Employee photos stored as files and recorded in core.attachment.

The table's s3_key column is the file name. This API has no S3 bucket configured, so the bytes
live under backend/var/attachments and the row points at that key.
"""

import base64
import re
from pathlib import Path

from trishul_api.common.errors import ApiError

_ROOT = Path(__file__).resolve().parents[5] / "var" / "attachments"
_DATA_URL = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\s]+)$")
_MAX_BYTES = 2 * 1024 * 1024


def decode_photo(value: str) -> tuple[bytes, str]:
    """Bytes and content type from a browser data URL. Rejects anything that is not a small image."""
    match = _DATA_URL.match(value.strip())
    if match is None:
        raise ApiError("The photo must be a JPG or PNG.")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except ValueError as error:
        raise ApiError("The photo must be a JPG or PNG.") from error
    if not raw or len(raw) > _MAX_BYTES:
        raise ApiError("The photo must be 2 MB or smaller.")
    return raw, match.group(1)


def store_photo(employee_id: int, raw: bytes) -> str:
    """Writes the file and returns the key stored in core.attachment.s3_key."""
    key = f"employees/{employee_id}/photo.jpg"
    path = _ROOT / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return key


def read_photo(key: str) -> bytes | None:
    path = _ROOT / key
    if not path.is_file():
        return None
    return path.read_bytes()


def data_url(content_type: str, raw: bytes) -> str:
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{content_type};base64,{encoded}"
