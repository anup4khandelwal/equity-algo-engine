"""Tests for the multi-asset momentum-rotation backtester."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from algotrading.backtest.metrics import compute_metrics
from algotrading.backtest.rotation import RotationConfig, build_panel, run_rotation
from algotrading.strategies.base import Bar


def _series(token: int, closes: list[float]) -> list[Bar]:
    start = datetime(2026, 1, 1)
    return [Bar(token, start + timedelta(days=i), c, c, c, c) for i, c in enumerate(closes)]


def _trending_panel():
    n = 12
    up = [100.0 + 10 * i for i in range(n)]  # token 1: strong uptrend
    flat = [100.0 for _ in range(n)]  # token 2: flat
    down = [100.0 - 4 * i for i in range(n)]  # token 3: downtrend
    return build_panel({1: _series(1, up), 2: _series(2, flat), 3: _series(3, down)})


def test_build_panel_aligns_by_timestamp() -> None:
    panel = build_panel({1: _series(1, [100, 101]), 2: _series(2, [200, 202])})
    assert len(panel) == 2
    assert panel[0][1] == {1: 100.0, 2: 200.0}


def test_rotation_holds_strongest_and_reports_net_pnl() -> None:
    cfg = RotationConfig(
        lookback=2, top_n=1, rebalance_every=1, initial_capital=100_000.0, slippage_bps=0.0
    )
    result = run_rotation(_trending_panel(), cfg)

    assert result.final_equity > cfg.initial_capital  # rode the uptrend
    assert result.trades  # trades were taken
    # The winning name (token 1) should dominate the traded names.
    assert any(t.instrument_token == 1 for t in result.trades)
    # Fully liquidated: realised net P&L matches the equity gain.
    net = sum(t.net_pnl for t in result.trades)
    assert net == pytest.approx(result.final_equity - cfg.initial_capital, rel=1e-6)


def test_costs_make_net_below_gross() -> None:
    cfg = RotationConfig(lookback=2, top_n=1, rebalance_every=1, slippage_bps=5.0)
    result = run_rotation(_trending_panel(), cfg)
    gross = sum(t.gross_pnl for t in result.trades)
    net = sum(t.net_pnl for t in result.trades)
    assert net < gross  # costs were charged


def test_metrics_apply_to_rotation_result() -> None:
    cfg = RotationConfig(lookback=2, top_n=1, rebalance_every=1, slippage_bps=0.0)
    result = run_rotation(_trending_panel(), cfg)
    metrics = compute_metrics(result)
    assert metrics.num_trades == len(result.trades)
    assert metrics.net_pnl == pytest.approx(result.final_equity - cfg.initial_capital, rel=1e-6)


def test_empty_panel_returns_flat_result() -> None:
    result = run_rotation([], RotationConfig())
    assert result.trades == []
    assert result.final_equity == RotationConfig().initial_capital
