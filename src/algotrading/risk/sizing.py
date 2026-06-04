"""Volatility-based position sizing.

Sizes a position so that a stop placed ``atr_stop_multiple`` ATRs away risks at
most ``risk_per_trade`` of capital, optionally capped by available notional.
"""

from __future__ import annotations

from collections.abc import Sequence

from algotrading.strategies.base import Bar


def average_true_range(bars: Sequence[Bar], period: int = 14) -> float:
    """Wilder-style ATR over the last ``period`` bars (simple mean of TRs).

    Returns 0.0 if there are too few bars to compute a true range.
    """
    if len(bars) < 2:
        return 0.0
    true_ranges: list[float] = []
    for prev, curr in zip(bars, bars[1:], strict=False):
        true_ranges.append(
            max(
                curr.high - curr.low,
                abs(curr.high - prev.close),
                abs(curr.low - prev.close),
            )
        )
    window = true_ranges[-period:]
    return sum(window) / len(window) if window else 0.0


def atr_position_size(
    capital: float,
    risk_per_trade: float,
    atr: float,
    *,
    atr_stop_multiple: float = 1.5,
    price: float | None = None,
    max_notional: float | None = None,
) -> int:
    """Number of shares to trade given an ATR-based stop distance.

    ``risk_per_trade`` is a fraction of ``capital`` (e.g. 0.01 = 1%). Returns 0
    when the inputs make sizing impossible (non-positive ATR/capital/risk).
    """
    if capital <= 0 or risk_per_trade <= 0 or atr <= 0 or atr_stop_multiple <= 0:
        return 0

    per_share_risk = atr * atr_stop_multiple
    qty = int((capital * risk_per_trade) // per_share_risk)

    if price is not None and price > 0:
        budget = max_notional if max_notional is not None else capital
        qty = min(qty, int(budget // price))

    return max(0, qty)
