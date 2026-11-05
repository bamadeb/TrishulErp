"""Where document bytes live.

core.attachment.s3_key is the storage key. This API has no S3 bucket configured yet, so the bytes sit
under backend/var/attachments (the same place as employee photos). Only this module touches the disk:
moving to S3 later means changing these three functions, not the callers.
"""

import re
from pathlib import Path
from uuid import uuid4

from trishul_api.common.errors import ApiError

_ROOT = Path(__file__).resolve().parents[5] / "var" / "attachments"

MAX_BYTES = 10 * 1024 * 1024

# extension -> (content type, magic bytes the file must start with)
ALLOWED: dict[str, tuple[str, tuple[bytes, ...]]] = {
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
}

_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def clean_file_name(name: str | None) -> str:
    """The base name only, without path or control characters, at most 200 characters."""
    base = _UNSAFE.sub("_", (name or "").replace("\\", "/").rsplit("/", 1)[-1]).strip(" .")
    if not base:
        raise ApiError("The file needs a name.")
    stem, dot, ext = base.rpartition(".")
    return (stem[: 199 - len(ext)] + dot + ext) if dot and len(base) > 200 else base[:200]


def validate_file(file_name: str, raw: bytes) -> str:
    """Content type of an acceptable file. Only PDF, JPG and PNG up to 10 MB; the bytes must match the
    extension, so a renamed executable is refused."""
    extension = Path(file_name).suffix.lower()
    if extension not in ALLOWED:
        raise ApiError("Only PDF, JPG, JPEG and PNG files can be uploaded.")
    if not raw:
        raise ApiError("The file is empty.")
    if len(raw) > MAX_BYTES:
        raise ApiError("The file must be 10 MB or smaller.")
    content_type, signatures = ALLOWED[extension]
    if not raw.startswith(signatures):
        raise ApiError(f"The file content is not a valid {extension.lstrip('.').upper()}.")
    return content_type


def store(entity_type: str, entity_id: int, file_name: str, raw: bytes) -> str:
    """Writes the file under a generated name (never the client's) and returns its storage key."""
    safe_type = re.sub(r"[^A-Za-z0-9_.-]", "_", entity_type)
    key = f"documents/{safe_type}/{entity_id}/{uuid4().hex}{Path(file_name).suffix.lower()}"
    path = _ROOT / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return key


def read(key: str) -> bytes | None:
    path = (_ROOT / key).resolve()
    if _ROOT.resolve() not in path.parents or not path.is_file():
        return None
    return path.read_bytes()


def remove(key: str) -> None:
    path = (_ROOT / key).resolve()
    if _ROOT.resolve() in path.parents and path.is_file():
        path.unlink()
