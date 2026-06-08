"""Tests for the Monte-Carlo bootstrap."""

from __future__ import annotations

from datetime import datetime

from algotrading.backtest.montecarlo import (
    _percentile,
    bootstrap_trades,
    monte_carlo,
)
from algotrading.backtest.simulator import BacktestResult, Trade
from algotrading.strategies.base import Side


def test_percentile_interpolates() -> None:
    vals = [0.0, 10.0, 20.0, 30.0, 40.0]
    assert _percentile(vals, 0.0) == 0.0
    assert _percentile(vals, 1.0) == 40.0
    assert _percentile(vals, 0.5) == 20.0


def test_all_winning_trades_always_profit() -> None:
    mc = bootstrap_trades([100.0, 50.0, 75.0], initial_capital=10_000, n_simulations=200, seed=1)
    assert mc.prob_profit == 1.0
    assert mc.mean_net_pnl > 0
    assert mc.p05_net_pnl > 0


def test_all_losing_trades_never_profit() -> None:
    mc = bootstrap_trades([-100.0, -50.0], initial_capital=10_000, n_simulations=200, seed=1)
    assert mc.prob_profit == 0.0
    assert mc.mean_net_pnl < 0
    assert mc.mean_max_drawdown > 0


def test_deterministic_with_seed() -> None:
    pnls = [100.0, -40.0, 60.0, -20.0, 30.0]
    a = bootstrap_trades(pnls, 10_000, n_simulations=100, seed=42)
    b = bootstrap_trades(pnls, 10_000, n_simulations=100, seed=42)
    assert a == b
    c = bootstrap_trades(pnls, 10_000, n_simulations=100, seed=7)
    assert c != a  # different seed -> different sample


def test_empty_or_zero_sims_returns_zeros() -> None:
    assert bootstrap_trades([], 10_000).n_simulations == 0
    assert bootstrap_trades([1.0], 10_000, n_simulations=0).n_simulations == 0


def _trade(net: float) -> Trade:
    t = datetime(2026, 1, 1, 9, 30)
    return Trade(1, Side.BUY, 10, t, 100.0, t, 100.0 + net / 10, net + 5, 5.0, net, "x")


def test_monte_carlo_from_result() -> None:
    result = BacktestResult(
        trades=[_trade(100), _trade(-40), _trade(60)],
        equity_curve=[],
        initial_capital=100_000.0,
        final_equity=100_120.0,
    )
    mc = monte_carlo(result, n_simulations=300, seed=3)
    assert mc.n_simulations == 300
    assert 0.0 <= mc.prob_profit <= 1.0
    assert mc.p05_net_pnl <= mc.median_net_pnl <= mc.p95_net_pnl
    assert "Prob. of profit" in mc.as_table()
