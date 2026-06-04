"""Tests for the event-driven simulator.

A scripted strategy drives the simulator deterministically so we can assert
exact net P&L (gross minus the full cost stack) and slippage handling.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from algotrading.backtest.simulator import BacktestConfig, run
from algotrading.strategies.base import Bar, Side, Signal, SignalType, Strategy


class ScriptedStrategy(Strategy):
    """Emits predefined signals keyed by bar timestamp."""

    def __init__(self, signals: dict[datetime, Signal]) -> None:
        self._signals = signals

    def generate_signal(self, bar: Bar) -> Signal | None:
        return self._signals.get(bar.time)


def _bar(minute: int, close: float) -> Bar:
    return Bar(
        instrument_token=1,
        time=datetime(2026, 1, 1, 9, minute),
        open=close,
        high=close,
        low=close,
        close=close,
    )


def _entry(when: datetime, side: Side, price: float) -> Signal:
    return Signal(when, 1, SignalType.ENTRY, side=side, price=price)


def _exit(when: datetime, side: Side, price: float) -> Signal:
    return Signal(when, 1, SignalType.EXIT, side=side, price=price)


def test_long_trade_reports_net_of_costs() -> None:
    t1, t2 = datetime(2026, 1, 1, 9, 15), datetime(2026, 1, 1, 9, 20)
    strategy = ScriptedStrategy({t1: _entry(t1, Side.BUY, 100.0), t2: _exit(t2, Side.SELL, 110.0)})
    bars = [_bar(15, 100.0), _bar(20, 110.0)]
    result = run(strategy, bars, BacktestConfig(quantity=100, slippage_bps=0.0))

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.gross_pnl == pytest.approx(1000.0)
    # entry cost (buy 100@100) + exit cost (sell 100@110) from the cost model.
    assert trade.costs == pytest.approx(4.20226 + 7.042486)
    assert trade.net_pnl == pytest.approx(1000.0 - trade.costs)
    assert trade.net_pnl < trade.gross_pnl
    assert result.final_equity == pytest.approx(100_000.0 + trade.net_pnl)
    assert len(result.equity_curve) == 2


def test_short_trade_profits_when_price_falls() -> None:
    t1, t2 = datetime(2026, 1, 1, 9, 15), datetime(2026, 1, 1, 9, 20)
    strategy = ScriptedStrategy({t1: _entry(t1, Side.SELL, 100.0), t2: _exit(t2, Side.BUY, 90.0)})
    bars = [_bar(15, 100.0), _bar(20, 90.0)]
    result = run(strategy, bars, BacktestConfig(quantity=100, slippage_bps=0.0))

    trade = result.trades[0]
    assert trade.direction is Side.SELL
    assert trade.gross_pnl == pytest.approx(1000.0)
    assert trade.net_pnl < trade.gross_pnl


def test_slippage_moves_fills_adversely() -> None:
    t1, t2 = datetime(2026, 1, 1, 9, 15), datetime(2026, 1, 1, 9, 20)
    strategy = ScriptedStrategy({t1: _entry(t1, Side.BUY, 100.0), t2: _exit(t2, Side.SELL, 110.0)})
    bars = [_bar(15, 100.0), _bar(20, 110.0)]
    result = run(strategy, bars, BacktestConfig(quantity=100, slippage_bps=10.0))

    trade = result.trades[0]
    assert trade.entry_price == pytest.approx(100.0 * 1.001)  # buy pays up
    assert trade.exit_price == pytest.approx(110.0 * 0.999)  # sell receives less


def test_entry_without_exit_leaves_position_open() -> None:
    t1 = datetime(2026, 1, 1, 9, 15)
    strategy = ScriptedStrategy({t1: _entry(t1, Side.BUY, 100.0)})
    bars = [_bar(15, 100.0), _bar(20, 105.0)]
    result = run(strategy, bars, BacktestConfig(quantity=10, slippage_bps=0.0))

    assert result.trades == []
    # Open position is marked to market in the equity curve (gross, +50).
    assert result.equity_curve[-1][1] == pytest.approx(100_000.0 + (105.0 - 100.0) * 10)


def test_uses_capital_to_size_when_quantity_not_given() -> None:
    t1, t2 = datetime(2026, 1, 1, 9, 15), datetime(2026, 1, 1, 9, 20)
    strategy = ScriptedStrategy({t1: _entry(t1, Side.BUY, 100.0), t2: _exit(t2, Side.SELL, 101.0)})
    bars = [_bar(15, 100.0), _bar(20, 101.0)]
    result = run(
        strategy,
        bars,
        BacktestConfig(capital_per_trade=50_000.0, slippage_bps=0.0),
    )
    # 50_000 // 100 = 500 shares.
    assert result.trades[0].quantity == 500
