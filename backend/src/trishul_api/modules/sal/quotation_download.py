"""Short-lived download links for generated quotation PDFs (used by the mobile app).

The PDF is written once per request under backend/var/generated/quotations with a random name (never in a web
root), and the link is a signed token: HMAC-SHA256 over the file id, the download name and the expiry. Anyone
holding an unexpired link can fetch that one file; nothing else is reachable with it. Files older than a day
are deleted whenever a new link is made.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from trishul_api.common.errors import NotFound

_ROOT = Path(__file__).resolve().parents[4] / "var" / "generated" / "quotations"
_KEEP_SECONDS = 24 * 3600
# Used when TRISHUL_DOWNLOAD_SIGNING_KEY is not set: links then stop working when the API restarts.
_PROCESS_KEY = secrets.token_bytes(32)

INVALID_LINK = "This download link is invalid or has expired."


@dataclass(frozen=True)
class DownloadLink:
    token: str
    file_name: str
    expires_at: int  # unix seconds


@dataclass(frozen=True)
class DownloadFile:
    content: bytes
    file_name: str


def _key(configured: str) -> bytes:
    return configured.encode() if configured else _PROCESS_KEY


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(key: bytes, body: str) -> str:
    return _b64(hmac.new(key, body.encode(), hashlib.sha256).digest())


def _sweep() -> None:
    if not _ROOT.is_dir():
        return
    cutoff = time.time() - _KEEP_SECONDS
    for path in _ROOT.glob("*.pdf"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass  # in use or already gone: the next sweep tries again


def create(pdf: bytes, file_name: str, signing_key: str, valid_seconds: int) -> DownloadLink:
    """Stores the PDF and returns the signed token that fetches it until it expires."""
    _ROOT.mkdir(parents=True, exist_ok=True)
    _sweep()
    file_id = uuid4().hex
    (_ROOT / f"{file_id}.pdf").write_bytes(pdf)
    expires_at = int(time.time()) + valid_seconds
    body = _b64(json.dumps({"f": file_id, "n": file_name, "e": expires_at}, separators=(",", ":")).encode())
    return DownloadLink(f"{body}.{_sign(_key(signing_key), body)}", file_name, expires_at)


def fetch(token: str, signing_key: str) -> DownloadFile:
    """The stored PDF for a valid, unexpired token; NotFound otherwise (the reason is not revealed)."""
    body, _, signature = token.partition(".")
    if not body or not hmac.compare_digest(signature, _sign(_key(signing_key), body)):
        raise NotFound(INVALID_LINK)
    try:
        claims = json.loads(_unb64(body))
        file_id, name, expires_at = str(claims["f"]), str(claims["n"]), int(claims["e"])
    except (ValueError, KeyError, TypeError) as error:
        raise NotFound(INVALID_LINK) from error
    path = (_ROOT / f"{file_id}.pdf").resolve()
    if expires_at < time.time() or _ROOT.resolve() not in path.parents or not path.is_file():
        raise NotFound(INVALID_LINK)
    return DownloadFile(path.read_bytes(), name)
