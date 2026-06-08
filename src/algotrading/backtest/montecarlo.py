"""Monte-Carlo bootstrap on trade returns.

A single backtest is one path through history. Resampling the *sequence* of
per-trade P&L (with replacement) many times gives a distribution of outcomes —
so a result comes with a confidence band and a probability of profit instead of
a single number. Deterministic given ``seed``.
"""

from __future__ import annotations

import random
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from .metrics import max_drawdown
from .simulator import BacktestResult


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile of an already-sorted sequence."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = q * (len(sorted_values) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (idx - lo)


@dataclass(frozen=True)
class MonteCarloResult:
    """Bootstrap distribution summary."""

    n_simulations: int
    mean_net_pnl: float
    median_net_pnl: float
    p05_net_pnl: float
    p95_net_pnl: float
    mean_max_drawdown: float
    p95_max_drawdown: float
    prob_profit: float

    def as_table(self) -> str:
        rows = [
            ("Simulations", f"{self.n_simulations}"),
            ("Mean net P&L", f"{self.mean_net_pnl:,.2f}"),
            ("Median net P&L", f"{self.median_net_pnl:,.2f}"),
            ("5th pct net P&L", f"{self.p05_net_pnl:,.2f}"),
            ("95th pct net P&L", f"{self.p95_net_pnl:,.2f}"),
            ("Mean max DD", f"{self.mean_max_drawdown:.2%}"),
            ("95th pct max DD", f"{self.p95_max_drawdown:.2%}"),
            ("Prob. of profit", f"{self.prob_profit:.2%}"),
        ]
        width = max(len(label) for label, _ in rows)
        return "\n".join(f"{label:<{width}} : {value}" for label, value in rows)


def bootstrap_trades(
    trade_pnls: Sequence[float],
    initial_capital: float,
    n_simulations: int = 1000,
    seed: int | None = None,
) -> MonteCarloResult:
    """Bootstrap a sequence of per-trade P&L into an outcome distribution."""
    if not trade_pnls or n_simulations <= 0:
        return MonteCarloResult(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    rng = random.Random(seed)
    n = len(trade_pnls)
    net_results: list[float] = []
    dd_results: list[float] = []

    for _ in range(n_simulations):
        equity = [initial_capital]
        cum = initial_capital
        for _ in range(n):
            cum += rng.choice(trade_pnls)
            equity.append(cum)
        net_results.append(equity[-1] - initial_capital)
        dd_results.append(max_drawdown(equity))

    net_sorted = sorted(net_results)
    dd_sorted = sorted(dd_results)
    return MonteCarloResult(
        n_simulations=n_simulations,
        mean_net_pnl=statistics.fmean(net_results),
        median_net_pnl=_percentile(net_sorted, 0.5),
        p05_net_pnl=_percentile(net_sorted, 0.05),
        p95_net_pnl=_percentile(net_sorted, 0.95),
        mean_max_drawdown=statistics.fmean(dd_results),
        p95_max_drawdown=_percentile(dd_sorted, 0.95),
        prob_profit=sum(1 for x in net_results if x > 0) / n_simulations,
    )


def monte_carlo(
    result: BacktestResult, n_simulations: int = 1000, seed: int | None = None
) -> MonteCarloResult:
    """Bootstrap a :class:`BacktestResult`'s trades."""
    return bootstrap_trades(
        [t.net_pnl for t in result.trades], result.initial_capital, n_simulations, seed
    )
