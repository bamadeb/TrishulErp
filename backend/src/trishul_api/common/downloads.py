"""Response headers for a file the API hands out (documents, receipts, generated PDFs).

Only types a browser shows without running anything (PDF and raster images) are ever served inline; anything
else is a download, so a file can never render as a page on the app's origin. The file name is written as an
ASCII fallback plus RFC 5987 filename* for other scripts: a raw non-Latin-1 name in a header is a server error,
and quotes or line breaks in it could otherwise break out of the header.
"""

import re
from urllib.parse import quote

INLINE_SAFE_TYPES = frozenset({"application/pdf", "image/jpeg", "image/png", "image/gif", "image/webp"})

_UNSAFE = re.compile(r'[\x00-\x1f\x7f"\\;]')


def file_response_headers(file_name: str, content_type: str | None, *, inline: bool) -> tuple[str, dict[str, str]]:
    """(media type, headers) for returning a stored file."""
    media_type = (content_type or "").strip().lower() or "application/octet-stream"
    disposition = "inline" if inline and media_type in INLINE_SAFE_TYPES else "attachment"
    name = _UNSAFE.sub("_", file_name or "").strip() or "download"
    ascii_name = name.encode("ascii", "replace").decode("ascii").replace("?", "_")
    value = f'{disposition}; filename="{ascii_name}"'
    if ascii_name != name:
        value += f"; filename*=UTF-8''{quote(name, safe='')}"
    return media_type, {
        "Content-Disposition": value,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    }
