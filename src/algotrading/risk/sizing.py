"""Volatility-based position sizing.

Three approaches:
- :func:`atr_position_size` — risk a fixed % of capital to an ATR-based stop.
- :func:`volatility_target_size` — size one position to a target P&L volatility.
- :func:`risk_parity_sizes` — allocate a basket so each name contributes equal
  risk (inverse-volatility weighting). Essential for an Indian multi-stock book
  where a smallcap and a largecap have very different volatility.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

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


def return_volatility(closes: Sequence[float], period: int = 20) -> float:
    """Sample std-dev of simple returns over the last ``period`` closes.

    Per-bar (not annualised); 0.0 when there are too few points.
    """
    window = list(closes[-(period + 1) :])
    if len(window) < 3:
        return 0.0
    returns = [(b - a) / a for a, b in zip(window, window[1:], strict=False) if a]
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return var**0.5


def volatility_target_size(
    capital: float,
    target_vol: float,
    vol_per_share: float,
    *,
    price: float | None = None,
    max_notional: float | None = None,
) -> int:
    """Shares so the position's P&L volatility ≈ ``capital * target_vol``.

    ``vol_per_share`` is one share's per-period rupee volatility (e.g. ATR, or
    ``price * return_volatility``). Capped by available notional.
    """
    if capital <= 0 or target_vol <= 0 or vol_per_share <= 0:
        return 0
    qty = int((capital * target_vol) / vol_per_share)
    if price is not None and price > 0:
        budget = max_notional if max_notional is not None else capital
        qty = min(qty, int(budget // price))
    return max(0, qty)


def inverse_vol_weights(vols: Mapping[int, float]) -> dict[int, float]:
    """Risk-parity weights ∝ 1/volatility, normalised to sum to 1.

    Names with non-positive volatility are dropped.
    """
    inv = {token: 1.0 / v for token, v in vols.items() if v and v > 0}
    total = sum(inv.values())
    if total <= 0:
        return {}
    return {token: w / total for token, w in inv.items()}


def _cap_weights(weights: Mapping[int, float], max_weight: float) -> dict[int, float]:
    """Cap each weight at ``max_weight``, redistributing the excess (water-filling).

    Keeps the total at 1.0 while ensuring no single name exceeds the cap.
    """
    result = dict(weights)
    for _ in range(len(result) + 1):
        over = [t for t, w in result.items() if w > max_weight + 1e-12]
        if not over:
            break
        for t in over:
            result[t] = max_weight
        remaining = 1.0 - max_weight * len(over)
        under = {t: w for t, w in result.items() if t not in over}
        under_total = sum(under.values())
        if remaining <= 0 or under_total <= 0:
            break
        for t in under:
            result[t] = remaining * (under[t] / under_total)
    return result


def risk_parity_sizes(
    capital: float,
    prices: Mapping[int, float],
    vols: Mapping[int, float],
    *,
    max_weight: float | None = None,
) -> dict[int, int]:
    """Inverse-vol share counts for a basket, so each name risks roughly the same.

    ``max_weight`` caps any single name's capital weight (then renormalises).
    """
    if capital <= 0:
        return {}
    weights = inverse_vol_weights(vols)
    if max_weight is not None:
        weights = _cap_weights(weights, max_weight)
    sizes: dict[int, int] = {}
    for token, weight in weights.items():
        price = prices.get(token, 0.0)
        if price > 0:
            qty = int((capital * weight) // price)
            if qty > 0:
                sizes[token] = qty
    return sizes
