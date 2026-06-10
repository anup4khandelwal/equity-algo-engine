"""Tests for portfolio-level backtesting via engine replay."""

from __future__ import annotations

from datetime import datetime

import pytest

from algotrading.backtest.metrics import compute_metrics
from algotrading.backtest.replay import replay
from algotrading.engine import EngineConfig, MultiStrategyEngine
from algotrading.risk.manager import RiskLimits, RiskManager
from algotrading.strategies.base import Bar, Side, Signal, SignalType, Strategy


class ScriptedStrategy(Strategy):
    def __init__(self, token: int, name: str, signals: dict[datetime, Signal]) -> None:
        self.instrument_token = token
        self.name = name
        self._signals = signals

    def generate_signal(self, bar: Bar) -> Signal | None:
        return self._signals.get(bar.time)


def _bar(token: int, minute: int, close: float) -> Bar:
    return Bar(token, datetime(2026, 6, 3, 9, 30 + minute), close, close, close, close)


def _entry(token: int, when: datetime) -> Signal:
    return Signal(when, token, SignalType.ENTRY, Side.BUY)


def _exit(token: int, when: datetime) -> Signal:
    return Signal(when, token, SignalType.EXIT, Side.SELL, reason="exit")


def _round_trip_signals(token: int, enter_min: int, exit_min: int) -> dict[datetime, Signal]:
    t_in = datetime(2026, 6, 3, 9, 30 + enter_min)
    t_out = datetime(2026, 6, 3, 9, 30 + exit_min)
    return {t_in: _entry(token, t_in), t_out: _exit(token, t_out)}


def test_replay_two_instruments_shared_capital() -> None:
    engine = MultiStrategyEngine(
        config=EngineConfig(capital=200_000.0, fixed_quantity=100, use_atr_sizing=False),
    )
    engine.add_strategy(ScriptedStrategy(1, "s1", _round_trip_signals(1, 0, 2)))
    engine.add_strategy(ScriptedStrategy(2, "s2", _round_trip_signals(2, 1, 3)))

    bars = [
        _bar(1, 0, 100.0),
        _bar(2, 1, 200.0),
        _bar(1, 2, 110.0),  # s1 exits +10/share
        _bar(2, 3, 190.0),  # s2 exits -10/share
    ]
    result = replay(engine, bars)

    assert len(result.trades) == 2
    by_token = {t.instrument_token: t for t in result.trades}
    assert by_token[1].net_pnl > 0
    assert by_token[2].net_pnl < 0
    assert result.initial_capital == 200_000.0
    # Equity curve marks every bar; final equity reflects both round trips.
    assert len(result.equity_curve) == 4
    net = sum(t.net_pnl for t in result.trades)
    assert result.final_equity == pytest.approx(200_000.0 + net)

    # Standard metrics apply unchanged to the portfolio result.
    metrics = compute_metrics(result)
    assert metrics.num_trades == 2
    assert metrics.net_pnl == pytest.approx(net)


def test_replay_sorts_out_of_order_bars() -> None:
    engine = MultiStrategyEngine(
        config=EngineConfig(capital=100_000.0, fixed_quantity=10, use_atr_sizing=False),
    )
    engine.add_strategy(ScriptedStrategy(1, "s1", _round_trip_signals(1, 0, 1)))
    bars = [_bar(1, 1, 105.0), _bar(1, 0, 100.0)]  # reversed on purpose
    result = replay(engine, bars)
    assert len(result.trades) == 1
    assert result.trades[0].net_pnl > 0


def test_replay_respects_shared_risk_budget() -> None:
    engine = MultiStrategyEngine(
        risk=RiskManager(RiskLimits(max_open_positions=1)),
        config=EngineConfig(capital=100_000.0, fixed_quantity=10, use_atr_sizing=False),
    )
    engine.add_strategy(ScriptedStrategy(1, "s1", _round_trip_signals(1, 0, 5)))
    engine.add_strategy(ScriptedStrategy(2, "s2", _round_trip_signals(2, 1, 5)))
    bars = [_bar(1, 0, 100.0), _bar(2, 1, 200.0), _bar(1, 5, 101.0), _bar(2, 5, 201.0)]
    result = replay(engine, bars)
    # Second entry was blocked by the shared max-positions cap → only one trade.
    assert len(result.trades) == 1
    assert result.trades[0].instrument_token == 1
