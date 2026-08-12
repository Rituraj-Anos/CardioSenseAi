"""Minimal in-process rate limiter (sliding window).

Guards the auth endpoints against brute-force and abuse. In-memory is fine for
a single-instance demo; a multi-instance deployment would back this with Redis.
Exposed as a FastAPI dependency factory.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_buckets: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def _client_key(request: Request, scope: str) -> str:
    fwd = request.headers.get("x-forwarded-for")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")
    return f"{scope}:{ip}"


def rate_limit(scope: str, limit: int, window_seconds: int):
    """Return a dependency that allows `limit` requests per `window_seconds`."""

    def _dep(request: Request) -> None:
        from app.core.config import settings

        # Don't rate-limit the test suite (a single client hammers these
        # endpoints legitimately across many test cases).
        if settings.app_env == "test":
            return

        now = time.monotonic()
        key = _client_key(request, scope)
        with _lock:
            bucket = _buckets[key]
            cutoff = now - window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry = int(window_seconds - (now - bucket[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many requests. Try again in {retry} seconds.",
                    headers={"Retry-After": str(retry)},
                )
            bucket.append(now)

    return _dep
