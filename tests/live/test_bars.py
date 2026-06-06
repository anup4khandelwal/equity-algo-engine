"""Tests for the tick -> bar aggregator."""

from __future__ import annotations

from datetime import datetime

from algotrading.live.bars import BarBuilder


def _ts(h: int, m: int, s: int) -> datetime:
    return datetime(2026, 6, 3, h, m, s)


def test_first_tick_starts_a_bucket_without_emitting() -> None:
    b = BarBuilder(interval_seconds=60)
    assert b.add_tick(1, 100.0, _ts(9, 15, 1)) is None


def test_bar_emitted_when_bucket_rolls_over() -> None:
    b = BarBuilder(interval_seconds=60)
    b.add_tick(1, 100.0, _ts(9, 15, 1))
    b.add_tick(1, 105.0, _ts(9, 15, 30))
    b.add_tick(1, 95.0, _ts(9, 15, 45))
    bar = b.add_tick(1, 101.0, _ts(9, 16, 2))  # new minute -> emits 09:15 bar

    assert bar is not None
    assert bar.time == _ts(9, 15, 0)
    # close is the last tick *within* the 09:15 bucket (95.0); 101.0 opens 09:16.
    assert (bar.open, bar.high, bar.low, bar.close) == (100.0, 105.0, 95.0, 95.0)


def test_volume_accumulates_within_bucket() -> None:
    b = BarBuilder(interval_seconds=60)
    b.add_tick(1, 100.0, _ts(9, 15, 1), volume=10)
    b.add_tick(1, 101.0, _ts(9, 15, 5), volume=15)
    bar = b.add_tick(1, 102.0, _ts(9, 16, 1), volume=5)
    assert bar.volume == 25


def test_multiple_instruments_tracked_independently() -> None:
    b = BarBuilder(interval_seconds=60)
    b.add_tick(1, 100.0, _ts(9, 15, 1))
    b.add_tick(2, 200.0, _ts(9, 15, 1))
    bar1 = b.add_tick(1, 110.0, _ts(9, 16, 1))
    assert bar1.instrument_token == 1 and bar1.close == 100.0


def test_flush_emits_in_progress_bars() -> None:
    b = BarBuilder(interval_seconds=60)
    b.add_tick(1, 100.0, _ts(9, 15, 1))
    bars = b.flush()
    assert len(bars) == 1 and bars[0].close == 100.0
    assert b.flush() == []  # cleared
