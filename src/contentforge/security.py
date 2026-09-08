"""Single-operator auth + a small in-process rate limiter for the web app.

Auth is opt-in: with no ``CONTENTFORGE_API_KEY`` set (the local-dev default) every route is
open. Once a key is set, the mutating / generating routes require it in an ``X-API-Key``
header; read-only routes and the served HTML stay open so the same-origin UI keeps working.
"""

from __future__ import annotations

import os
from collections import defaultdict, deque
from time import monotonic
from typing import Optional

from fastapi import Header, HTTPException


def api_key_configured() -> bool:
    return bool(os.getenv("CONTENTFORGE_API_KEY"))


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = os.getenv("CONTENTFORGE_API_KEY")
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


def cors_origins() -> list[str]:
    raw = os.getenv("CONTENTFORGE_CORS_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return ["http://localhost:8000", "http://127.0.0.1:8000"]


class RateLimiter:
    """Sliding 60-second window, keyed (default: one global bucket)."""

    def __init__(self, max_per_minute: int) -> None:
        self.max_per_minute = max_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str = "global") -> None:
        if self.max_per_minute <= 0:
            return
        now = monotonic()
        window = self._hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.max_per_minute:
            raise HTTPException(status_code=429, detail="Rate limit exceeded; try again shortly")
        window.append(now)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


generation_limiter = RateLimiter(_int_env("CONTENTFORGE_RATE_LIMIT_PER_MIN", 10))
