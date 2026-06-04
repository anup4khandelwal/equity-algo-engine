"""Aggregate live ticks into fixed-interval OHLC bars.

KiteTicker delivers ticks, but strategies consume bars. ``BarBuilder`` buckets
ticks by time and emits a completed :class:`Bar` when the bucket rolls over.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from algotrading.strategies.base import Bar


@dataclass
class _Bucket:
    start: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class BarBuilder:
    """Builds per-instrument OHLC bars from a tick stream."""

    def __init__(self, interval_seconds: int = 60) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.interval = interval_seconds
        self._buckets: dict[int, _Bucket] = {}

    def _floor(self, ts: datetime) -> datetime:
        seconds = ts.hour * 3600 + ts.minute * 60 + ts.second
        floored = seconds - (seconds % self.interval)
        return ts.replace(
            hour=floored // 3600,
            minute=(floored % 3600) // 60,
            second=floored % 60,
            microsecond=0,
        )

    def add_tick(
        self, instrument_token: int, price: float, ts: datetime, volume: int = 0
    ) -> Bar | None:
        """Add a tick; return a completed bar when the bucket rolls over."""
        start = self._floor(ts)
        bucket = self._buckets.get(instrument_token)

        if bucket is None:
            self._buckets[instrument_token] = _Bucket(start, price, price, price, price, volume)
            return None

        if start > bucket.start:
            completed = self._to_bar(instrument_token, bucket)
            self._buckets[instrument_token] = _Bucket(start, price, price, price, price, volume)
            return completed

        bucket.high = max(bucket.high, price)
        bucket.low = min(bucket.low, price)
        bucket.close = price
        bucket.volume += volume
        return None

    def flush(self) -> list[Bar]:
        """Emit and clear all in-progress bars (e.g. at session end)."""
        bars = [self._to_bar(token, bucket) for token, bucket in self._buckets.items()]
        self._buckets.clear()
        return bars

    @staticmethod
    def _to_bar(token: int, bucket: _Bucket) -> Bar:
        return Bar(
            instrument_token=token,
            time=bucket.start,
            open=bucket.open,
            high=bucket.high,
            low=bucket.low,
            close=bucket.close,
            volume=int(bucket.volume),
        )
