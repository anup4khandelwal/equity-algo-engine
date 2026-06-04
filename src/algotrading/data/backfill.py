"""Backfill orchestration: pull instruments and historical bars from Kite and
persist them via the repositories.

This module is pure orchestration — it takes a Kite client and repositories as
arguments — so it can be unit-tested with mocks and no network or DB. The CLI
wrapper lives in ``scripts/backfill.py``.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Protocol

from .mappers import parse_bar, parse_instrument


class _Client(Protocol):
    def instruments(self, exchange: str | None = ...) -> list[dict[str, Any]]: ...
    def historical_data(
        self, instrument_token: int, from_date: Any, to_date: Any, interval: str
    ) -> list[dict[str, Any]]: ...


def date_chunks(start: date, end: date, chunk_days: int) -> list[tuple[date, date]]:
    """Split ``[start, end]`` into inclusive windows of at most ``chunk_days``.

    Kite caps the span of a single historical request (e.g. ~60 days for minute
    data), so backfills are issued window by window.
    """
    if chunk_days <= 0:
        raise ValueError("chunk_days must be positive")
    if end < start:
        raise ValueError("end must not be before start")

    windows: list[tuple[date, date]] = []
    cursor = start
    span = timedelta(days=chunk_days - 1)
    while cursor <= end:
        window_end = min(cursor + span, end)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows


def sync_instruments(client: _Client, repo: Any, exchange: str | None = None) -> int:
    """Fetch the instrument master from Kite and upsert it. Returns row count."""
    records = client.instruments(exchange) if exchange else client.instruments()
    parsed = [parse_instrument(r) for r in records]
    return repo.upsert_many(parsed)


def backfill_bars(
    client: _Client,
    repo: Any,
    instrument_token: int,
    start: date,
    end: date,
    *,
    interval: str = "minute",
    chunk_days: int = 60,
) -> int:
    """Backfill OHLC bars for one instrument over ``[start, end]``.

    Returns the total number of bars stored.
    """
    total = 0
    for window_start, window_end in date_chunks(start, end, chunk_days):
        bars = client.historical_data(instrument_token, window_start, window_end, interval)
        rows = [parse_bar(instrument_token, bar) for bar in bars]
        total += repo.upsert_bars(rows)
    return total
