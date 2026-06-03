"""Client-side rate limiting for Kite Connect.

Kite enforces per-endpoint rate limits (roughly: ~10 req/sec across general GET
endpoints, lower for quote/historical, and order placement capped at 200/min).
We throttle proactively with token buckets so we never trip the server-side
limit. Buckets are thread-safe because KiteTicker callbacks run on their own
threads.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import StrEnum
from threading import Lock

# Tolerance for floating-point comparisons when checking available tokens.
_EPSILON = 1e-9


class RateCategory(StrEnum):
    """Endpoint families with distinct Kite rate limits."""

    general = "general"
    quote = "quote"
    historical = "historical"
    order = "order"


# Sustained rate (requests/sec) and burst capacity per category. Conservative
# defaults aligned with the brief; tune in one place if Kite changes limits.
_DEFAULT_LIMITS: dict[RateCategory, tuple[float, float]] = {
    RateCategory.general: (10.0, 10.0),
    RateCategory.quote: (1.0, 1.0),
    RateCategory.historical: (3.0, 3.0),
    # 200 orders/minute sustained, small burst.
    RateCategory.order: (200.0 / 60.0, 10.0),
}


class TokenBucket:
    """A thread-safe token bucket.

    Tokens refill continuously at ``rate`` per second up to ``capacity``.
    ``acquire`` blocks (sleeping) until enough tokens are available. ``time_func``
    and ``sleep_func`` are injectable so the behaviour is deterministic in tests.
    """

    def __init__(
        self,
        rate: float,
        capacity: float,
        *,
        time_func: Callable[[], float] = time.monotonic,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.rate = rate
        self.capacity = capacity
        self._time = time_func
        self._sleep = sleep_func
        self._tokens = capacity
        self._last = time_func()
        self._lock = Lock()

    def _refill(self) -> None:
        now = self._time()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last = now

    def acquire(self, tokens: float = 1.0) -> None:
        """Block until ``tokens`` are available, then consume them."""
        if tokens > self.capacity:
            raise ValueError(
                f"cannot acquire {tokens} tokens from a bucket of capacity {self.capacity}"
            )
        with self._lock:
            while True:
                self._refill()
                # Compare with a small tolerance: refilling after a sleep can
                # leave the bucket a hair under `tokens` due to floating-point
                # error (e.g. 100.1 - 100 == 0.0999...), which would otherwise
                # spin this loop forever on ever-shrinking deficits.
                if self._tokens + _EPSILON >= tokens:
                    self._tokens = max(0.0, self._tokens - tokens)
                    return
                deficit = tokens - self._tokens
                self._sleep(deficit / self.rate)


class RateLimiter:
    """Routes calls to a per-category :class:`TokenBucket`."""

    def __init__(
        self,
        limits: dict[RateCategory, tuple[float, float]] | None = None,
        *,
        time_func: Callable[[], float] = time.monotonic,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        limits = limits or _DEFAULT_LIMITS
        self._buckets = {
            category: TokenBucket(rate, capacity, time_func=time_func, sleep_func=sleep_func)
            for category, (rate, capacity) in limits.items()
        }

    def acquire(self, category: RateCategory, tokens: float = 1.0) -> None:
        """Block until a slot is available for ``category``."""
        self._buckets[category].acquire(tokens)
