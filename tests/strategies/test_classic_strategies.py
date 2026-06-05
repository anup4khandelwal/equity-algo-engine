"""Behavioural tests for the MA-crossover, RSI(2), VWAP, and Supertrend strategies."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from algotrading.strategies.base import Bar, SignalType
from algotrading.strategies.ma_crossover import MovingAverageCrossover
from algotrading.strategies.rsi2 import RSI2
from algotrading.strategies.supertrend import Supertrend
from algotrading.strategies.vwap import VWAPReversion

TOKEN = 1


def _daily(closes: list[float], highs=None, lows=None, vols=None) -> list[Bar]:
    start = datetime(2026, 1, 1)
    bars = []
    for i, c in enumerate(closes):
        h = highs[i] if highs else c
        low = lows[i] if lows else c
        v = vols[i] if vols else 0
        bars.append(Bar(TOKEN, start + timedelta(days=i), c, h, low, c, v))
    return bars


def _collect(strat, bars) -> list:
    return [s for bar in bars if (s := strat.on_bar(bar)) is not None]


# --- Moving-average crossover -------------------------------------------------
def test_ma_crossover_enters_on_golden_cross_and_exits() -> None:
    strat = MovingAverageCrossover(TOKEN, fast=2, slow=3)
    # Down then up so the fast MA crosses above the slow, then back below.
    closes = [10, 9, 8, 7, 12, 16, 20, 8, 4, 2]
    signals = _collect(strat, _daily(closes))
    types = [s.type for s in signals]
    assert SignalType.ENTRY in types
    assert types.index(SignalType.ENTRY) < types.index(SignalType.EXIT)


def test_ma_crossover_rejects_bad_periods() -> None:
    with pytest.raises(ValueError):
        MovingAverageCrossover(TOKEN, fast=50, slow=20)


# --- RSI(2) -------------------------------------------------------------------
def test_rsi2_buys_oversold_without_trend_filter() -> None:
    strat = RSI2(TOKEN, period=2, lower=10, upper=50, trend_filter=None)
    # Steady decline -> RSI(2) ~0 -> oversold entry.
    signals = _collect(strat, _daily([100, 98, 96, 94, 92]))
    assert any(s.type is SignalType.ENTRY for s in signals)


def test_rsi2_trend_filter_blocks_when_below_sma() -> None:
    # With a trend filter longer than the data, no long is allowed.
    strat = RSI2(TOKEN, period=2, lower=10, upper=50, trend_filter=100)
    signals = _collect(strat, _daily([100, 98, 96, 94, 92]))
    assert signals == []


# --- VWAP reversion (intraday) ------------------------------------------------
def _intraday(prices: list[float], vol: int = 1000) -> list[Bar]:
    base = datetime(2026, 6, 3, 9, 15)
    return [Bar(TOKEN, base + timedelta(minutes=i), p, p, p, p, vol) for i, p in enumerate(prices)]


def test_vwap_longs_below_band_and_exits_on_revert() -> None:
    strat = VWAPReversion(TOKEN, band=0.005, allow_short=False)
    # First bar sets VWAP=100; a dip well below triggers a long; recovery exits.
    signals = _collect(strat, _intraday([100, 100, 90, 101]))
    types = [s.type for s in signals]
    assert types[0] is SignalType.ENTRY
    assert SignalType.EXIT in types


def test_vwap_rejects_bad_band() -> None:
    with pytest.raises(ValueError):
        VWAPReversion(TOKEN, band=0)


# --- Supertrend ---------------------------------------------------------------
def test_supertrend_enters_in_uptrend_and_exits_in_downtrend() -> None:
    strat = Supertrend(TOKEN, period=3, multiplier=2.0)
    up = [100 + 3 * i for i in range(12)]
    down = [up[-1] - 4 * i for i in range(1, 12)]
    closes = up + down
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    signals = _collect(strat, _daily(closes, highs, lows))
    types = [s.type for s in signals]
    assert SignalType.ENTRY in types
    assert SignalType.EXIT in types
    assert types.index(SignalType.ENTRY) < types.index(SignalType.EXIT)
