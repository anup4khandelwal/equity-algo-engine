"""Tests for regime detection (ADX + realized volatility)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from algotrading.strategies.base import Bar
from algotrading.strategies.regime import (
    Regime,
    RegimeDetector,
    adx,
    realized_volatility,
)

TOKEN = 1


def _bars(closes: list[float], spread: float = 0.5) -> list[Bar]:
    start = datetime(2026, 1, 1)
    return [
        Bar(TOKEN, start + timedelta(days=i), c, c + spread, c - spread, c)
        for i, c in enumerate(closes)
    ]


def _trending(n: int = 60) -> list[Bar]:
    return _bars([100.0 + 2.0 * i for i in range(n)])


def _ranging(n: int = 60) -> list[Bar]:
    return _bars([100.0 + (1.0 if i % 2 else -1.0) for i in range(n)])


def test_adx_high_in_trend_low_in_range() -> None:
    trending = adx(_trending(), period=14)
    ranging = adx(_ranging(), period=14)
    assert trending > 25.0
    assert ranging < 25.0
    assert trending > ranging


def test_adx_needs_warmup() -> None:
    assert adx(_trending(10), period=14) == 0.0


def test_realized_volatility() -> None:
    assert realized_volatility([100.0] * 30) == pytest.approx(0.0)
    flat = realized_volatility([100.0, 100.1] * 15)
    wild = realized_volatility([100.0, 110.0] * 15)
    assert wild > flat > 0.0
    assert realized_volatility([100.0, 101.0]) == 0.0  # too short


def test_detector_classifies_streaming() -> None:
    det = RegimeDetector(adx_period=14, adx_threshold=25.0)
    states = [det.update(b) for b in _trending()]
    assert states[0] is Regime.UNKNOWN  # warm-up
    assert states[-1] is Regime.TRENDING

    det.reset()
    states = [det.update(b) for b in _ranging()]
    assert states[-1] is Regime.RANGING


def test_detector_window_is_capped() -> None:
    det = RegimeDetector(adx_period=14)
    for bar in _trending(500):
        det.update(bar)
    assert len(det._bars) <= 6 * 14
