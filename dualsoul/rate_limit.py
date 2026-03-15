"""In-memory sliding window rate limiter for DualSoul."""

import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse


class RateLimiter:
    """Simple in-memory sliding window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup(self, key: str):
        cutoff = time.time() - self.window
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]

    def is_limited(self, request: Request) -> bool:
        key = self._client_ip(request)
        self._cleanup(key)
        if len(self._hits[key]) >= self.max_requests:
            return True
        self._hits[key].append(time.time())
        return False


# Pre-configured limiters
_login_limiter = RateLimiter(max_requests=10, window_seconds=60)
_register_limiter = RateLimiter(max_requests=5, window_seconds=60)
_message_limiter = RateLimiter(max_requests=30, window_seconds=60)
_action_limiter = RateLimiter(max_requests=20, window_seconds=60)

_RATE_LIMIT_RESPONSE = JSONResponse(
    status_code=429,
    content={"success": False, "error": "请求过快，请稍后再试"},
)


async def check_login_rate(request: Request):
    """FastAPI dependency — rate limit login attempts."""
    if _login_limiter.is_limited(request):
        return _RATE_LIMIT_RESPONSE
    return None


async def check_register_rate(request: Request):
    """FastAPI dependency — rate limit registration attempts."""
    if _register_limiter.is_limited(request):
        return _RATE_LIMIT_RESPONSE
    return None


async def check_message_rate(request: Request):
    """FastAPI dependency — rate limit message sending (30/min)."""
    if _message_limiter.is_limited(request):
        return _RATE_LIMIT_RESPONSE
    return None


async def check_action_rate(request: Request):
    """FastAPI dependency — rate limit general actions (20/min)."""
    if _action_limiter.is_limited(request):
        return _RATE_LIMIT_RESPONSE
    return None
