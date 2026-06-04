"""Tests for ATR computation and position sizing."""

from __future__ import annotations

from datetime import datetime

import pytest

from algotrading.risk.sizing import atr_position_size, average_true_range
from algotrading.strategies.base import Bar


def _bar(c: float, h: float, low: float) -> Bar:
    return Bar(1, datetime(2026, 6, 3, 9, 15), open=c, high=h, low=low, close=c)


def test_atr_of_constant_bars_is_range() -> None:
    bars = [_bar(100, 102, 98) for _ in range(5)]
    # prev close == 100, so TR == high-low == 4 each.
    assert average_true_range(bars, period=14) == pytest.approx(4.0)


def test_atr_uses_gap_to_previous_close() -> None:
    bars = [
        Bar(1, datetime(2026, 6, 3, 9, 15), 100, 100, 100, 100),
        Bar(1, datetime(2026, 6, 3, 9, 16), 110, 112, 108, 110),  # TR = max(4, 12, 8) = 12
    ]
    assert average_true_range(bars) == pytest.approx(12.0)


def test_atr_too_few_bars_is_zero() -> None:
    assert average_true_range([_bar(100, 101, 99)]) == 0.0


def test_position_size_respects_risk_budget() -> None:
    # risk 1% of 100k = 1000; stop = 2 * 1.5 = 3 per share -> 333 shares.
    qty = atr_position_size(100_000, 0.01, atr=2.0, atr_stop_multiple=1.5)
    assert qty == 333


def test_position_size_capped_by_notional() -> None:
    # Risk allows many shares, but price * qty must fit the budget.
    qty = atr_position_size(
        100_000, 0.05, atr=0.5, atr_stop_multiple=1.0, price=1000.0, max_notional=50_000.0
    )
    assert qty == 50  # 50_000 // 1000


def test_zero_atr_returns_zero() -> None:
    assert atr_position_size(100_000, 0.01, atr=0.0) == 0
