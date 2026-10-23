"""Sliding window in-memory rate limiter for API endpoints."""

import collections
import logging
import threading
import time
from collections.abc import Callable

from fastapi import HTTPException, Request, Response, status

from app.core.config import settings

log = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter."""

    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._history: dict[str, collections.deque] = collections.defaultdict(
            collections.deque
        )
        self._lock = threading.Lock()

    def check(
        self, key: str, max_requests: int
    ) -> tuple[bool, int, int, int]:
        """Check if request for *key* is within *max_requests* in the sliding window.

        Returns:
            (allowed: bool, remaining: int, reset_seconds: int, limit: int)
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            queue = self._history[key]
            # Prune timestamps outside current window
            while queue and queue[0] <= window_start:
                queue.popleft()

            current_count = len(queue)
            if current_count >= max_requests:
                # Calculate when the oldest request rolls out of the window
                oldest_timestamp = queue[0]
                reset_seconds = max(1, int(oldest_timestamp + self.window_seconds - now))
                return False, 0, reset_seconds, max_requests

            # Allow request
            queue.append(now)
            remaining = max(0, max_requests - len(queue))
            reset_seconds = self.window_seconds
            return True, remaining, reset_seconds, max_requests

    def reset(self) -> None:
        """Clear all rate limit history (useful for tests)."""
        with self._lock:
            self._history.clear()


# Global rate limiter instance (60-second sliding window)
rate_limiter = SlidingWindowRateLimiter(window_seconds=60)


def get_client_ip(request: Request) -> str:
    """Extract client IP handling reverse proxy headers."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def create_rate_limiter(tier: str, limit_getter: Callable[[], int]):
    """Create a FastAPI dependency function for rate limiting."""
    async def _dependency(request: Request, response: Response) -> None:
        if not settings.enable_rate_limiting:
            return

        client_ip = get_client_ip(request)
        limit = limit_getter()
        key = f"{tier}:{client_ip}"

        allowed, remaining, reset_seconds, limit_val = rate_limiter.check(
            key=key, max_requests=limit
        )

        # Set standard rate-limit response headers
        response.headers["X-RateLimit-Limit"] = str(limit_val)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_seconds)

        if not allowed:
            log.warning(
                "Rate limit exceeded for %s on tier '%s' (limit=%d/min). Reset in %ds.",
                client_ip,
                tier,
                limit_val,
                reset_seconds,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded. You have made too many requests in this minute. "
                    f"Please try again in {reset_seconds} seconds."
                ),
                headers={"Retry-After": str(reset_seconds)},
            )

    return _dependency


# Pre-configured rate limiting dependencies
rate_limit_query = create_rate_limiter(
    tier="query",
    limit_getter=lambda: settings.rate_limit_query_per_min,
)

rate_limit_ingest = create_rate_limiter(
    tier="ingest",
    limit_getter=lambda: settings.rate_limit_ingest_per_min,
)

rate_limit_auth = create_rate_limiter(
    tier="auth",
    limit_getter=lambda: settings.rate_limit_auth_per_min,
)
