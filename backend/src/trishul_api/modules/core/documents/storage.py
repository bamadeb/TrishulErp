"""Where document bytes live.

core.attachment.s3_key is the storage key. This API has no S3 bucket configured yet, so the bytes sit
under backend/var/attachments (the same place as employee photos). Only this module touches the disk:
moving to S3 later means changing these three functions, not the callers.
"""

import io
import re
import zipfile
from pathlib import Path
from uuid import uuid4

from trishul_api.common.errors import ApiError

_ROOT = Path(__file__).resolve().parents[5] / "var" / "attachments"

MAX_BYTES = 10 * 1024 * 1024
# A .docx / .xlsx is a zip: refuse one that expands to more than this (a zip bomb).
_MAX_UNPACKED_BYTES = 100 * 1024 * 1024

_OLE = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)  # legacy Word / Excel (.doc, .xls)
_ZIP = (b"PK\x03\x04",)  # Office Open XML (.docx, .xlsx)

# extension -> (content type, magic bytes the file must start with, what to call it in messages)
ALLOWED: dict[str, tuple[str, tuple[bytes, ...], str]] = {
    ".pdf": ("application/pdf", (b"%PDF-",), "PDF"),
    ".doc": ("application/msword", _OLE, "Word document"),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", _ZIP, "Word document"),
    ".xls": ("application/vnd.ms-excel", _OLE, "Excel workbook"),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", _ZIP, "Excel workbook"),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",), "JPG"),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",), "JPEG"),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",), "PNG"),
    ".gif": ("image/gif", (b"GIF87a", b"GIF89a"), "GIF"),
    ".webp": ("image/webp", (b"RIFF",), "WebP"),
}
ALLOWED_MESSAGE = (
    "Only PDF, Word (.doc, .docx), Excel (.xls, .xlsx) and image (JPG, PNG, GIF, WebP) files can be uploaded."
)

# Where the main part of each Office Open XML type lives; also how a renamed zip is told apart.
_OOXML_ROOT = {".docx": "word/", ".xlsx": "xl/"}

_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def clean_file_name(name: str | None) -> str:
    """The base name only, without path or control characters, at most 200 characters."""
    base = _UNSAFE.sub("_", (name or "").replace("\\", "/").rsplit("/", 1)[-1]).strip(" .")
    if not base:
        raise ApiError("The file needs a name.")
    stem, dot, ext = base.rpartition(".")
    return (stem[: 199 - len(ext)] + dot + ext) if dot and len(base) > 200 else base[:200]


def validate_file(file_name: str, raw: bytes) -> str:
    """Content type of an acceptable file: PDF, Word, Excel or an image, up to 10 MB. The bytes must match
    the extension (and an Office file must really be one, without macros), so a renamed program or a
    macro-enabled workbook is refused."""
    extension = Path(file_name).suffix.lower()
    if extension not in ALLOWED:
        raise ApiError(ALLOWED_MESSAGE)
    if not raw:
        raise ApiError("The file is empty.")
    if len(raw) > MAX_BYTES:
        raise ApiError("The file must be 10 MB or smaller.")
    content_type, signatures, label = ALLOWED[extension]
    invalid = ApiError(f"The file content is not a valid {label}.")
    if not raw.startswith(signatures):
        raise invalid
    if extension == ".webp" and raw[8:12] != b"WEBP":
        raise invalid
    if extension in _OOXML_ROOT:
        _check_office_open_xml(raw, _OOXML_ROOT[extension], invalid)
    return content_type


def _check_office_open_xml(raw: bytes, root: str, invalid: ApiError) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist()
            if "[Content_Types].xml" not in names or not any(n.startswith(root) for n in names):
                raise invalid
            if any(n.lower().endswith("vbaproject.bin") for n in names):
                raise ApiError("Files with macros cannot be uploaded. Save the file without macros first.")
            if sum(info.file_size for info in archive.infolist()) > _MAX_UNPACKED_BYTES:
                raise ApiError("The file is too large once unpacked.")
    except zipfile.BadZipFile as error:
        raise invalid from error


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
