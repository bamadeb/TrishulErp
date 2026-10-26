"""HTTP security headers for every API response (docs/Trishul_Backend_Implementation_Guide.md, section 6)."""

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

_ALWAYS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
# JSON responses never need to run scripts or be framed; ERP data must not sit in shared caches.
_API_ONLY = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}


def install_security_headers(app: FastAPI, *, docs_paths: tuple[str, ...]) -> None:
    """docs_paths (Swagger UI and its OpenAPI document) skip the strict CSP so the page can load."""

    @app.middleware("http")
    async def security_headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for name, value in _ALWAYS.items():
            response.headers.setdefault(name, value)
        if not request.url.path.startswith(docs_paths):
            for name, value in _API_ONLY.items():
                response.headers.setdefault(name, value)
        return response
