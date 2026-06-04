"""Performance metrics computed from a backtest result.

Sharpe/Sortino are annualised from **daily** returns (the equity curve is
resampled to one point per calendar day), which keeps them comparable across
strategies regardless of bar resolution.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from math import sqrt

from .simulator import BacktestResult

TRADING_DAYS_PER_YEAR = 252


def max_drawdown(equity: Sequence[float]) -> float:
    """Largest peak-to-trough decline as a positive fraction (0..1)."""
    peak = float("-inf")
    mdd = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            mdd = max(mdd, (peak - value) / peak)
    return mdd


def sharpe_ratio(
    returns: Sequence[float],
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
    risk_free: float = 0.0,
) -> float:
    """Annualised Sharpe ratio from per-period returns."""
    if len(returns) < 2:
        return 0.0
    target = risk_free / periods_per_year
    excess = [r - target for r in returns]
    sd = statistics.stdev(excess)
    if sd == 0:
        return 0.0
    return (statistics.fmean(excess) / sd) * sqrt(periods_per_year)


def sortino_ratio(
    returns: Sequence[float],
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
    risk_free: float = 0.0,
) -> float:
    """Annualised Sortino ratio (downside-deviation denominator)."""
    if len(returns) < 2:
        return 0.0
    target = risk_free / periods_per_year
    excess = [r - target for r in returns]
    downside = statistics.fmean([min(0.0, e) ** 2 for e in excess])
    dd = sqrt(downside)
    if dd == 0:
        return 0.0
    return (statistics.fmean(excess) / dd) * sqrt(periods_per_year)


def daily_returns(equity_curve: Sequence[tuple[datetime, float]]) -> list[float]:
    """Resample an equity curve to end-of-day values and return % changes."""
    daily: dict = {}
    for ts, value in equity_curve:
        daily[ts.date()] = value  # last value seen for the day wins
    values = [daily[day] for day in sorted(daily)]
    returns = []
    for prev, curr in zip(values, values[1:], strict=False):
        if prev != 0:
            returns.append((curr - prev) / prev)
    return returns


@dataclass(frozen=True)
class Metrics:
    """Summary statistics for a backtest run."""

    net_pnl: float
    gross_pnl: float
    total_costs: float
    return_pct: float
    num_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    sharpe: float
    sortino: float
    max_drawdown_pct: float
    turnover: float

    def as_table(self) -> str:
        """Human-readable summary for the CLI."""
        rows = [
            ("Net P&L", f"{self.net_pnl:,.2f}"),
            ("Gross P&L", f"{self.gross_pnl:,.2f}"),
            ("Total costs", f"{self.total_costs:,.2f}"),
            ("Return", f"{self.return_pct:.2%}"),
            ("Trades", f"{self.num_trades}"),
            ("Win rate", f"{self.win_rate:.2%}"),
            ("Avg win", f"{self.avg_win:,.2f}"),
            ("Avg loss", f"{self.avg_loss:,.2f}"),
            ("Sharpe", f"{self.sharpe:.2f}"),
            ("Sortino", f"{self.sortino:.2f}"),
            ("Max drawdown", f"{self.max_drawdown_pct:.2%}"),
            ("Turnover", f"{self.turnover:.2f}x"),
        ]
        width = max(len(label) for label, _ in rows)
        return "\n".join(f"{label:<{width}} : {value}" for label, value in rows)


def compute_metrics(
    result: BacktestResult,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> Metrics:
    """Aggregate a :class:`BacktestResult` into summary :class:`Metrics`."""
    trades = result.trades
    net_pnl = sum(t.net_pnl for t in trades)
    gross_pnl = sum(t.gross_pnl for t in trades)
    total_costs = sum(t.costs for t in trades)

    wins = [t.net_pnl for t in trades if t.net_pnl > 0]
    losses = [t.net_pnl for t in trades if t.net_pnl <= 0]
    num_trades = len(trades)
    win_rate = len(wins) / num_trades if num_trades else 0.0
    avg_win = statistics.fmean(wins) if wins else 0.0
    avg_loss = statistics.fmean(losses) if losses else 0.0

    returns = daily_returns(result.equity_curve)
    equity = [value for _, value in result.equity_curve]

    traded_value = sum(t.entry_price * t.quantity + t.exit_price * t.quantity for t in trades)
    turnover = traded_value / result.initial_capital if result.initial_capital else 0.0

    return Metrics(
        net_pnl=net_pnl,
        gross_pnl=gross_pnl,
        total_costs=total_costs,
        return_pct=net_pnl / result.initial_capital if result.initial_capital else 0.0,
        num_trades=num_trades,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        sharpe=sharpe_ratio(returns, periods_per_year),
        sortino=sortino_ratio(returns, periods_per_year),
        max_drawdown_pct=max_drawdown(equity),
        turnover=turnover,
    )
