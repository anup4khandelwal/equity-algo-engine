"""Tests for engine-level protective stops."""

from __future__ import annotations

from datetime import datetime

from algotrading.risk.stops import ProtectiveStops, StopConfig
from algotrading.strategies.base import Bar, Position, Side


def _bar(o, h, low, c) -> Bar:
    return Bar(1, datetime(2026, 6, 3, 9, 30), o, h, low, c)


def _long(entry: float = 100.0) -> Position:
    return Position(Side.BUY, 100, entry, datetime(2026, 6, 3, 9, 15))


def _short(entry: float = 100.0) -> Position:
    return Position(Side.SELL, 100, entry, datetime(2026, 6, 3, 9, 15))


def test_disabled_never_triggers() -> None:
    stops = ProtectiveStops(StopConfig())
    assert stops.update_and_check(1, _long(), _bar(100, 100, 1, 1)) is None


def test_long_hard_stop() -> None:
    stops = ProtectiveStops(StopConfig(stop_loss_pct=0.02))
    # bar low 97 <= 98 stop
    hit = stops.update_and_check(1, _long(100), _bar(100, 100, 97, 98))
    assert hit is not None and hit.reason == "stop_loss"
    assert hit.price == 98.0


def test_long_hard_stop_not_triggered_above_level() -> None:
    stops = ProtectiveStops(StopConfig(stop_loss_pct=0.02))
    assert stops.update_and_check(1, _long(100), _bar(100, 101, 99, 100)) is None


def test_short_hard_stop() -> None:
    stops = ProtectiveStops(StopConfig(stop_loss_pct=0.02))
    hit = stops.update_and_check(1, _short(100), _bar(100, 103, 100, 102))  # high 103 >= 102
    assert hit is not None and hit.reason == "stop_loss" and hit.price == 102.0


def test_long_trailing_stop_from_peak() -> None:
    stops = ProtectiveStops(StopConfig(trailing_pct=0.05))
    # Bar 1 runs up to 120 (low 115 stays above the 114 trail) -> no breach.
    assert stops.update_and_check(1, _long(100), _bar(115, 120, 115, 119)) is None
    # Bar 2 dips to 113 <= 114 -> trailing stop.
    hit = stops.update_and_check(1, _long(100), _bar(119, 119, 113, 115))
    assert hit is not None and hit.reason == "trailing_stop"
    assert hit.price == 120.0 * 0.95


def test_hard_stop_takes_precedence_over_trailing() -> None:
    stops = ProtectiveStops(StopConfig(stop_loss_pct=0.02, trailing_pct=0.01))
    hit = stops.update_and_check(1, _long(100), _bar(100, 100, 90, 95))
    assert hit is not None and hit.reason == "stop_loss"


def test_on_close_resets_extreme() -> None:
    stops = ProtectiveStops(StopConfig(trailing_pct=0.05))
    stops.update_and_check(1, _long(100), _bar(100, 130, 100, 129))  # extreme 130
    stops.on_close(1)
    # Fresh position: extreme re-initialises to the new entry (no stale 130).
    assert stops.update_and_check(1, _long(100), _bar(100, 101, 99, 100)) is None
