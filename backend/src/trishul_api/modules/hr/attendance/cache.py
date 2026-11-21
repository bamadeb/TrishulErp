"""Short-lived in-process cache for stable attendance master data."""

from __future__ import annotations

import time
from threading import Lock
from typing import Callable, TypeVar

T = TypeVar("T")

_lock = Lock()
_store: dict[str, tuple[float, object]] = {}

# Employee / shift masters change rarely during a screen session.
DEFAULT_TTL_SECONDS = 60.0


def get_or_set(key: str, factory: Callable[[], T], *, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> T:
    now = time.monotonic()
    with _lock:
        hit = _store.get(key)
        if hit is not None and hit[0] > now:
            return hit[1]  # type: ignore[return-value]
    value = factory()
    with _lock:
        _store[key] = (now + ttl_seconds, value)
    return value


def invalidate(*prefixes: str) -> None:
    with _lock:
        if not prefixes:
            _store.clear()
            return
        for key in list(_store):
            if any(key.startswith(prefix) for prefix in prefixes):
                _store.pop(key, None)
