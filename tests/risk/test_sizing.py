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


# --- volatility target & risk parity -----------------------------------------
def test_return_volatility() -> None:
    from algotrading.risk.sizing import return_volatility

    assert return_volatility([100.0] * 30) == pytest.approx(0.0)
    assert return_volatility([100.0, 101.0]) == 0.0  # too short
    assert return_volatility([100.0, 110.0] * 15) > return_volatility([100.0, 100.5] * 15) > 0


def test_volatility_target_size() -> None:
    from algotrading.risk.sizing import volatility_target_size

    # target P&L vol = 1% of 100k = 1000; each share has 2 rupees of vol -> 500.
    assert volatility_target_size(100_000, 0.01, vol_per_share=2.0) == 500
    # capped by max_notional
    assert volatility_target_size(100_000, 0.05, 0.5, price=100.0, max_notional=30_000.0) == 300
    assert volatility_target_size(100_000, 0.0, 2.0) == 0  # bad input


def test_inverse_vol_weights_favour_low_vol() -> None:
    from algotrading.risk.sizing import inverse_vol_weights

    w = inverse_vol_weights({1: 0.01, 2: 0.04})  # token 2 four times as volatile
    assert w[1] > w[2]
    assert w[1] == pytest.approx(0.8) and w[2] == pytest.approx(0.2)
    assert sum(w.values()) == pytest.approx(1.0)
    assert inverse_vol_weights({1: 0.0}) == {}  # non-positive vol dropped


def test_risk_parity_sizes_equalise_risk() -> None:
    from algotrading.risk.sizing import risk_parity_sizes

    sizes = risk_parity_sizes(100_000.0, prices={1: 100.0, 2: 200.0}, vols={1: 0.01, 2: 0.02})
    # Each name's rupee risk (qty * price * vol) should be roughly equal.
    risk1 = sizes[1] * 100.0 * 0.01
    risk2 = sizes[2] * 200.0 * 0.02
    assert abs(risk1 - risk2) / risk1 < 0.02


def test_risk_parity_max_weight_cap() -> None:
    from algotrading.risk.sizing import risk_parity_sizes

    # Token 1 would dominate (very low vol); cap its weight at 60%.
    capped = risk_parity_sizes(
        100_000.0,
        prices={1: 100.0, 2: 100.0},
        vols={1: 0.001, 2: 0.05},
        max_weight=0.6,
    )
    # token 1 notional should be ~60% of capital, not ~98%.
    assert capped[1] * 100.0 <= 0.61 * 100_000.0
