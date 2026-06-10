"""Market regime detection.

A strategy that works in a trend bleeds in a range, and vice versa. The
:class:`RegimeDetector` classifies the market per bar using Wilder's ADX
(trend strength) and a realized-volatility percentile, so strategies (or the
:class:`~algotrading.strategies.ensemble.EnsembleStrategy`) can be gated to the
conditions they were designed for.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from .base import Bar


class Regime(StrEnum):
    """Coarse market state."""

    UNKNOWN = "UNKNOWN"  # not enough data yet
    TRENDING = "TRENDING"
    RANGING = "RANGING"


def adx(bars: Sequence[Bar], period: int = 14) -> float:
    """Wilder's Average Directional Index over the last bars.

    Returns 0.0 until there are at least ``2 * period + 1`` bars.
    """
    if len(bars) < 2 * period + 1:
        return 0.0

    plus_dm: list[float] = []
    minus_dm: list[float] = []
    tr: list[float] = []
    for prev, curr in zip(bars, bars[1:], strict=False):
        up = curr.high - prev.high
        down = prev.low - curr.low
        plus_dm.append(up if (up > down and up > 0) else 0.0)
        minus_dm.append(down if (down > up and down > 0) else 0.0)
        tr.append(
            max(curr.high - curr.low, abs(curr.high - prev.close), abs(curr.low - prev.close))
        )

    def _wilder(values: list[float]) -> list[float]:
        smoothed = [sum(values[:period])]
        for v in values[period:]:
            smoothed.append(smoothed[-1] - smoothed[-1] / period + v)
        return smoothed

    atr_s = _wilder(tr)
    plus_s = _wilder(plus_dm)
    minus_s = _wilder(minus_dm)

    dx: list[float] = []
    for a, p, m in zip(atr_s, plus_s, minus_s, strict=True):
        if a == 0:
            dx.append(0.0)
            continue
        plus_di = 100.0 * p / a
        minus_di = 100.0 * m / a
        denom = plus_di + minus_di
        dx.append(100.0 * abs(plus_di - minus_di) / denom if denom else 0.0)

    if len(dx) < period:
        return 0.0
    adx_val = sum(dx[:period]) / period
    for v in dx[period:]:
        adx_val = (adx_val * (period - 1) + v) / period
    return adx_val


def realized_volatility(closes: Sequence[float], period: int = 20) -> float:
    """Std-dev of simple returns over the last ``period`` closes (per-bar, not annualised)."""
    window = list(closes[-(period + 1) :])
    if len(window) < 3:
        return 0.0
    returns = [(b - a) / a for a, b in zip(window, window[1:], strict=False) if a]
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return var**0.5


class RegimeDetector:
    """Streaming regime classifier: feed bars, get a :class:`Regime` back."""

    def __init__(self, *, adx_period: int = 14, adx_threshold: float = 25.0) -> None:
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.reset()

    def reset(self) -> None:
        self._bars: list[Bar] = []
        self.last_adx = 0.0

    def update(self, bar: Bar) -> Regime:
        self._bars.append(bar)
        cap = 6 * self.adx_period
        if len(self._bars) > cap:
            del self._bars[:-cap]
        if len(self._bars) < 2 * self.adx_period + 1:
            return Regime.UNKNOWN
        self.last_adx = adx(self._bars, self.adx_period)
        return Regime.TRENDING if self.last_adx >= self.adx_threshold else Regime.RANGING
