"""Parameter grid-search and walk-forward optimization.

Built on the event-driven :func:`run` simulator so optimization uses the exact
same strategy code and cost model as backtests and live trading — no drift, and
no separate vectorised engine to keep in sync. (``vectorbt`` remains available
in the ``backtest`` extra for fast exploratory research.)

Walk-forward picks the best parameters on each in-sample window and evaluates
them on the *next* out-of-sample window, so reported performance is genuinely
out-of-sample rather than curve-fit.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from algotrading.strategies.base import Bar, Strategy

from .metrics import Metrics, compute_metrics
from .simulator import BacktestConfig, BacktestResult, Trade, run

StrategyFactory = Callable[[dict], Strategy]


def expand_grid(grid: dict[str, Sequence]) -> list[dict]:
    """Expand ``{name: [values]}`` into every combination of parameters."""
    if not grid:
        return [{}]
    names = list(grid)
    return [dict(zip(names, combo, strict=True)) for combo in itertools.product(*grid.values())]


def grid_search(
    bars: Sequence[Bar],
    factory: StrategyFactory,
    grid: dict[str, Sequence],
    config: BacktestConfig | None = None,
    metric: str = "net_pnl",
) -> list[tuple[dict, Metrics]]:
    """Backtest every parameter combination; return results sorted best-first."""
    results = []
    for params in expand_grid(grid):
        result = run(factory(params), bars, config)
        results.append((params, compute_metrics(result)))
    results.sort(key=lambda item: getattr(item[1], metric), reverse=True)
    return results


@dataclass(frozen=True)
class Fold:
    """One walk-forward fold."""

    train_start: date
    train_end: date
    test_start: date
    test_end: date
    params: dict
    in_sample: Metrics
    out_sample: Metrics


@dataclass(frozen=True)
class WalkForwardResult:
    """Walk-forward output: per-fold detail plus a stitched OOS aggregate."""

    folds: list[Fold]
    combined: BacktestResult

    @property
    def out_sample_metrics(self) -> Metrics:
        return compute_metrics(self.combined)


def _bars_by_date(bars: Sequence[Bar]) -> dict[date, list[Bar]]:
    grouped: dict[date, list[Bar]] = {}
    for bar in bars:
        grouped.setdefault(bar.time.date(), []).append(bar)
    return grouped


def walk_forward(
    bars: Sequence[Bar],
    factory: StrategyFactory,
    grid: dict[str, Sequence],
    *,
    train_days: int,
    test_days: int,
    step_days: int | None = None,
    config: BacktestConfig | None = None,
    metric: str = "net_pnl",
) -> WalkForwardResult:
    """Rolling walk-forward: optimise in-sample, evaluate out-of-sample."""
    cfg = config or BacktestConfig()
    step = step_days or test_days
    by_date = _bars_by_date(bars)
    days = sorted(by_date)

    folds: list[Fold] = []
    combined_trades: list[Trade] = []
    combined_curve: list[tuple] = []
    running = cfg.initial_capital

    start = 0
    while start + train_days + test_days <= len(days):
        train = days[start : start + train_days]
        test = days[start + train_days : start + train_days + test_days]

        train_bars = [b for d in train for b in by_date[d]]
        test_bars = [b for d in test for b in by_date[d]]

        ranked = grid_search(train_bars, factory, grid, cfg, metric)
        best_params, in_sample = ranked[0]

        oos = run(factory(best_params), test_bars, cfg)
        combined_trades.extend(oos.trades)
        # Chain the out-of-sample P&L additively onto the running equity.
        for ts, equity in oos.equity_curve:
            running_point = running + (equity - cfg.initial_capital)
            combined_curve.append((ts, running_point))
        if oos.equity_curve:
            running = combined_curve[-1][1]

        folds.append(
            Fold(
                train_start=train[0],
                train_end=train[-1],
                test_start=test[0],
                test_end=test[-1],
                params=best_params,
                in_sample=in_sample,
                out_sample=compute_metrics(oos),
            )
        )
        start += step

    combined = BacktestResult(
        trades=combined_trades,
        equity_curve=combined_curve,
        initial_capital=cfg.initial_capital,
        final_equity=combined_curve[-1][1] if combined_curve else cfg.initial_capital,
    )
    return WalkForwardResult(folds=folds, combined=combined)
