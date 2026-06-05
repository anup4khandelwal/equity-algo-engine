"""Tests for grid-search and walk-forward optimization."""

from __future__ import annotations

from datetime import datetime, timedelta

from algotrading.backtest.optimize import (
    expand_grid,
    grid_search,
    walk_forward,
)
from algotrading.backtest.simulator import BacktestConfig
from algotrading.strategies.base import Bar
from algotrading.strategies.orb import OpeningRangeBreakout

TOKEN = 1


def test_expand_grid_produces_all_combinations() -> None:
    combos = expand_grid({"a": [1, 2], "b": [3, 4]})
    assert {tuple(sorted(c.items())) for c in combos} == {
        (("a", 1), ("b", 3)),
        (("a", 1), ("b", 4)),
        (("a", 2), ("b", 3)),
        (("a", 2), ("b", 4)),
    }


def test_expand_grid_empty() -> None:
    assert expand_grid({}) == [{}]


def _orb_day(day: int) -> list[Bar]:
    base = datetime(2026, 6, day, 9, 15)
    spec = [
        (0, 100, 110, 100, 105),
        (1, 105, 108, 90, 100),  # range high 110, low 90
        (16, 110, 112, 109, 111),  # long breakout
        (17, 111, 131, 110, 130),  # target hit (with target_multiple=1.0)
    ]
    return [Bar(TOKEN, base + timedelta(minutes=m), o, h, low, c) for m, o, h, low, c in spec]


def _dataset(days: list[int]) -> list[Bar]:
    return [bar for day in days for bar in _orb_day(day)]


def _factory(params: dict) -> OpeningRangeBreakout:
    return OpeningRangeBreakout(TOKEN, opening_range_minutes=15, **params)


def test_grid_search_sorts_best_first() -> None:
    bars = _dataset([1, 2, 3])
    cfg = BacktestConfig(quantity=100, slippage_bps=0.0)
    ranked = grid_search(bars, _factory, {"target_multiple": [0.5, 1.0, 2.0]}, cfg, "net_pnl")

    assert len(ranked) == 3
    nets = [m.net_pnl for _, m in ranked]
    assert nets == sorted(nets, reverse=True)  # best first


def test_walk_forward_runs_out_of_sample() -> None:
    bars = _dataset(list(range(1, 11)))  # 10 trading "days"
    cfg = BacktestConfig(quantity=100, slippage_bps=0.0)
    result = walk_forward(
        bars,
        _factory,
        {"target_multiple": [0.5, 1.0]},
        train_days=4,
        test_days=2,
        config=cfg,
    )

    # (10 - 4) // 2 = 3 folds.
    assert len(result.folds) == 3
    for fold in result.folds:
        assert fold.params["target_multiple"] in (0.5, 1.0)
        assert fold.train_end < fold.test_start  # OOS strictly after IS
    # Combined OOS aggregate is computable.
    assert result.out_sample_metrics.num_trades == len(result.combined.trades)


def test_walk_forward_too_little_data_yields_no_folds() -> None:
    bars = _dataset([1, 2])
    result = walk_forward(bars, _factory, {"target_multiple": [1.0]}, train_days=4, test_days=2)
    assert result.folds == []
