"""Portfolio-level backtesting by replaying history through the live engine.

The single-instrument simulator is great for fast research, but a real book
runs many strategies over many instruments with shared capital and a shared
risk budget. This module replays stored bars through a
:class:`~algotrading.engine.MultiStrategyEngine` (or ``PaperTradingEngine``) —
the *same* code that paper-trades live — and converts the outcome into a
standard :class:`BacktestResult`, so ``compute_metrics`` / Monte-Carlo / the
HTML report all apply unchanged. Zero backtest-vs-live drift, by construction.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from algotrading.execution.analytics import event_from_fill, round_trips
from algotrading.strategies.base import Bar, Side

from .simulator import BacktestResult, Trade


def replay(engine: Any, bars: Iterable[Bar]) -> BacktestResult:
    """Feed ``bars`` (any instruments, any order) through ``engine`` in time order.

    ``engine`` must expose ``on_bar(bar)``, ``trade_log.fills``,
    ``equity_curve`` and ``config.capital`` — both live engines do.
    """
    for bar in sorted(bars, key=lambda b: b.time):
        engine.on_bar(bar)

    trips = round_trips([event_from_fill(f) for f in engine.trade_log.fills])
    trades = [
        Trade(
            instrument_token=t.instrument_token,
            direction=Side(t.direction),
            quantity=t.quantity,
            entry_time=t.entry_time,
            entry_price=t.entry_price,
            exit_time=t.exit_time,
            exit_price=t.exit_price,
            gross_pnl=t.gross_pnl,
            costs=t.charges,
            net_pnl=t.net_pnl,
            exit_reason=t.strategy,
        )
        for t in trips
    ]

    capital = float(engine.config.capital)
    curve = list(engine.equity_curve)
    final_equity = curve[-1][1] if curve else capital
    return BacktestResult(
        trades=trades,
        equity_curve=curve,
        initial_capital=capital,
        final_equity=final_equity,
    )
