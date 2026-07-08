from __future__ import annotations

import os
import time
from threading import Lock

from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, tuple[float, int]] = {}
        self._lock = Lock()

    def check(self, *, key: str, max_requests: int, window_seconds: int) -> int:
        now = time.monotonic()
        with self._lock:
            window_start, count = self._buckets.get(key, (now, 0))
            elapsed = now - window_start
            if elapsed >= window_seconds:
                window_start = now
                count = 0
            if count >= max_requests:
                retry_after = max(1, int(window_seconds - elapsed))
                return retry_after
            self._buckets[key] = (window_start, count + 1)
            return 0

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()


rate_limiter = InMemoryRateLimiter()


async def require_public_rate_limit(request: Request) -> None:
    if not _bool_from_env("CHANNEL_PUBLIC_RATE_LIMIT_ENABLED", True):
        return
    max_requests = _int_from_env("CHANNEL_PUBLIC_RATE_LIMIT_MAX", 60)
    window_seconds = _int_from_env("CHANNEL_PUBLIC_RATE_LIMIT_WINDOW_SECONDS", 60)
    client_host = request.client.host if request.client else "unknown"
    key = f"{client_host}:{request.url.path}"
    retry_after = rate_limiter.check(
        key=key,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="public ingress rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


def _bool_from_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_from_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default
