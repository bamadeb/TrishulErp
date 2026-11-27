"""Request rate limits (OWASP API4, unrestricted resource consumption), kept in this API process's memory.

Each request counts against sliding one-window limits:
- its sign-in session (the bearer token), or its client address when it has no token;
- its client address overall, a ceiling that also stops a client from dodging the per-session limit by sending
  made-up tokens (it is high because a whole office can share one address);
- a stricter limit for the few endpoints worth guessing at (own password change, the public PDF download link).

Over a limit the answer is 429 with Retry-After. The API runs as one process behind IIS, which passes the real
client address (uvicorn --proxy-headers), so memory is the right store; several processes would need a shared
store instead. Health checks are never limited.
"""

import hashlib
import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from trishul_api.common.errors import problem


@dataclass(frozen=True)
class Limit:
    requests: int
    seconds: int


@dataclass(frozen=True)
class RateLimits:
    per_session: Limit = Limit(300, 60)
    per_anonymous_client: Limit = Limit(60, 60)
    per_client_address: Limit = Limit(3000, 60)
    # (method, path under the API prefix, matched as a prefix) -> limit per session / address.
    sensitive: tuple[tuple[str, str, Limit], ...] = (
        ("POST", "/me/password", Limit(5, 900)),
        ("GET", "/sal/quotation-downloads/", Limit(30, 60)),
    )


class SlidingWindow:
    """Timestamps of recent hits per key. Thread-safe: sync endpoints run on a thread pool."""

    _SWEEP_EVERY = 1000

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._calls = 0
        self._longest = 0

    def hit(self, key: str, limit: Limit) -> float | None:
        """Counts one request; returns the seconds to wait when the limit is already used up (not counted)."""
        now = self._clock()
        with self._lock:
            self._longest = max(self._longest, limit.seconds)
            self._calls += 1
            if self._calls % self._SWEEP_EVERY == 0:
                self._sweep(now)
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - limit.seconds:
                hits.popleft()
            if len(hits) >= limit.requests:
                return max(hits[0] + limit.seconds - now, 0.0)
            hits.append(now)
            return None

    def _sweep(self, now: float) -> None:
        # Drop keys with no hit inside the longest window, so the table doesn't grow without bound.
        stale = [key for key, hits in self._hits.items() if not hits or hits[-1] <= now - self._longest]
        for key in stale:
            del self._hits[key]


def _session_key(authorization: str) -> str | None:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    # A digest, so access tokens are not kept in memory as they are.
    return hashlib.sha256(token.strip().encode()).hexdigest()[:32]


def install_rate_limits(
    app: FastAPI, *, api_prefix: str, limits: RateLimits | None = None, window: SlidingWindow | None = None
) -> SlidingWindow:
    """Adds the limiter in front of the app. Install it before the security headers and CORS middleware so
    that a 429 still carries them."""
    limits = limits or RateLimits()
    window = window or SlidingWindow()
    sensitive = [(method, api_prefix + path, limit) for method, path, limit in limits.sensitive]

    @app.middleware("http")
    async def rate_limit(request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if request.method == "OPTIONS" or path == "/health" or path.startswith("/health/"):
            return await call_next(request)
        address = request.client.host if request.client else "unknown"
        session = _session_key(request.headers.get("authorization", ""))
        caller = f"s:{session}" if session else f"a:{address}"
        checks = [(f"ip:{address}", limits.per_client_address)]
        checks.append((caller, limits.per_session if session else limits.per_anonymous_client))
        for method, prefix, limit in sensitive:
            if request.method == method and path.startswith(prefix):
                checks.append((f"{caller}|{method} {prefix}", limit))
        for key, limit in checks:
            wait = window.hit(key, limit)
            if wait is not None:
                retry_after = max(1, math.ceil(wait))
                response = problem(429, "Too many requests", "Please wait a moment and try again.")
                response.headers["Retry-After"] = str(retry_after)
                return response
        return await call_next(request)

    return window
