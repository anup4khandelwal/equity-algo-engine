"""Tests for the time-series Momentum strategy."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from algotrading.strategies.base import SignalType
from algotrading.strategies.momentum import Momentum


def _bars(closes: list[float]) -> list:
    from algotrading.strategies.base import Bar

    start = datetime(2026, 1, 1)
    return [Bar(1, start + timedelta(days=i), c, c, c, c) for i, c in enumerate(closes)]


def _collect(strat: Momentum, bars) -> list:
    return [sig for bar in bars if (sig := strat.on_bar(bar)) is not None]


def test_no_signal_before_lookback_filled() -> None:
    strat = Momentum(1, lookback=3)
    signals = _collect(strat, _bars([100, 101, 102]))  # only 3 bars, need lookback+1
    assert signals == []


def test_enters_long_on_positive_momentum() -> None:
    strat = Momentum(1, lookback=3, entry_threshold=0.0)
    # 4th bar compares to 1st: 110 vs 100 -> +10% > 0 -> entry.
    signals = _collect(strat, _bars([100, 101, 102, 110]))
    assert len(signals) == 1
    assert signals[0].type is SignalType.ENTRY
    assert signals[0].reason == "momentum"


def test_exits_when_momentum_turns_negative() -> None:
    strat = Momentum(1, lookback=2, entry_threshold=0.0, exit_threshold=0.0)
    # closes: 100,100,110 (entry; 110 vs 100 +10%), then 95 (95 vs 110 -> negative -> exit)
    signals = _collect(strat, _bars([100, 100, 110, 95]))
    types = [s.type for s in signals]
    assert types == [SignalType.ENTRY, SignalType.EXIT]
    assert signals[-1].reason == "momentum_exit"


def test_no_double_entry_while_in_position() -> None:
    strat = Momentum(1, lookback=2, entry_threshold=0.0)
    signals = _collect(strat, _bars([100, 100, 110, 120, 130]))
    assert sum(1 for s in signals if s.type is SignalType.ENTRY) == 1


def test_invalid_lookback_raises() -> None:
    with pytest.raises(ValueError):
        Momentum(1, lookback=0)
