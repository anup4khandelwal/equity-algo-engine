"""Tests for performance metrics."""

from __future__ import annotations

from datetime import datetime

import pytest

from algotrading.backtest.metrics import (
    compute_metrics,
    daily_returns,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)
from algotrading.backtest.simulator import BacktestResult, Trade
from algotrading.strategies.base import Side


def test_max_drawdown() -> None:
    assert max_drawdown([100, 120, 90, 110, 80]) == pytest.approx((120 - 80) / 120)


def test_max_drawdown_monotonic_increase_is_zero() -> None:
    assert max_drawdown([100, 101, 102, 103]) == pytest.approx(0.0)


def test_sharpe_zero_when_no_variation() -> None:
    assert sharpe_ratio([0.01, 0.01, 0.01]) == 0.0


def test_sharpe_positive_for_positive_mean() -> None:
    assert sharpe_ratio([0.01, -0.005, 0.02, 0.0, 0.015]) > 0


def test_sharpe_needs_two_points() -> None:
    assert sharpe_ratio([0.05]) == 0.0


def test_sortino_zero_without_downside() -> None:
    # No negative returns -> downside deviation is zero -> defined as 0.
    assert sortino_ratio([0.01, 0.02, 0.03]) == 0.0


def test_sortino_positive_with_mixed_returns() -> None:
    assert sortino_ratio([0.02, -0.01, 0.03, -0.005]) > 0


def test_daily_returns_uses_end_of_day_values() -> None:
    curve = [
        (datetime(2026, 1, 1, 9, 15), 100.0),
        (datetime(2026, 1, 1, 15, 15), 110.0),  # EOD day 1
        (datetime(2026, 1, 2, 9, 15), 110.0),
        (datetime(2026, 1, 2, 15, 15), 121.0),  # EOD day 2
    ]
    assert daily_returns(curve) == pytest.approx([0.1])  # 110 -> 121


def _trade(net: float) -> Trade:
    return Trade(
        instrument_token=1,
        direction=Side.BUY,
        quantity=10,
        entry_time=datetime(2026, 1, 1, 9, 30),
        entry_price=100.0,
        exit_time=datetime(2026, 1, 1, 10, 0),
        exit_price=100.0 + net / 10,
        gross_pnl=net + 5,
        costs=5.0,
        net_pnl=net,
        exit_reason="test",
    )


def test_compute_metrics_win_rate_and_pnl() -> None:
    trades = [_trade(100.0), _trade(-40.0), _trade(60.0)]
    curve = [
        (datetime(2026, 1, 1, 15, 15), 100_120.0),
        (datetime(2026, 1, 2, 15, 15), 100_120.0),
    ]
    result = BacktestResult(
        trades=trades,
        equity_curve=curve,
        initial_capital=100_000.0,
        final_equity=100_120.0,
    )
    m = compute_metrics(result)
    assert m.num_trades == 3
    assert m.net_pnl == pytest.approx(120.0)
    assert m.total_costs == pytest.approx(15.0)
    assert m.win_rate == pytest.approx(2 / 3)
    assert m.avg_win == pytest.approx(80.0)
    assert m.avg_loss == pytest.approx(-40.0)
    assert "Net P&L" in m.as_table()
