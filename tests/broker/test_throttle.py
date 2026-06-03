"""Tests for the token-bucket rate limiter."""

from __future__ import annotations

import pytest

from algotrading.broker.throttle import RateCategory, RateLimiter, TokenBucket

from .conftest import FakeClock


def test_burst_up_to_capacity_does_not_sleep() -> None:
    clock = FakeClock()
    bucket = TokenBucket(rate=10, capacity=5, time_func=clock.time, sleep_func=clock.sleep)
    for _ in range(5):
        bucket.acquire()
    assert clock.sleeps == []


def test_acquire_beyond_capacity_sleeps_to_refill() -> None:
    clock = FakeClock()
    bucket = TokenBucket(rate=10, capacity=1, time_func=clock.time, sleep_func=clock.sleep)
    bucket.acquire()  # drains the single token, no sleep
    bucket.acquire()  # must wait for one token at 10/sec -> 0.1s
    assert clock.sleeps == [pytest.approx(0.1)]
    assert clock.now == pytest.approx(0.1)


def test_refill_is_capped_at_capacity() -> None:
    clock = FakeClock()
    bucket = TokenBucket(rate=10, capacity=2, time_func=clock.time, sleep_func=clock.sleep)
    clock.now += 100  # plenty of idle time, but refill must not exceed capacity
    bucket.acquire()
    bucket.acquire()
    assert clock.sleeps == []  # two tokens available
    bucket.acquire()  # third requires a real wait
    assert clock.sleeps == [pytest.approx(0.1)]


def test_acquire_more_than_capacity_raises() -> None:
    bucket = TokenBucket(rate=10, capacity=2)
    with pytest.raises(ValueError):
        bucket.acquire(3)


@pytest.mark.parametrize("bad", [{"rate": 0}, {"rate": -1}, {"capacity": 0}])
def test_invalid_bucket_params_raise(bad: dict) -> None:
    params = {"rate": 1.0, "capacity": 1.0}
    params.update(bad)
    with pytest.raises(ValueError):
        TokenBucket(**params)


def test_rate_limiter_uses_per_category_buckets() -> None:
    clock = FakeClock()
    limiter = RateLimiter(
        limits={
            RateCategory.quote: (1.0, 1.0),
            RateCategory.general: (10.0, 10.0),
        },
        time_func=clock.time,
        sleep_func=clock.sleep,
    )
    # Quote bucket (cap 1) sleeps on the second call; general bucket does not.
    limiter.acquire(RateCategory.quote)
    limiter.acquire(RateCategory.general)
    assert clock.sleeps == []
    limiter.acquire(RateCategory.quote)
    assert clock.sleeps == [pytest.approx(1.0)]
