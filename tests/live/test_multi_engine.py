"""Tests for the multi-strategy engine (shared portfolio + risk budget)."""

from __future__ import annotations

from datetime import datetime

from algotrading.engine import EngineConfig, MultiStrategyEngine
from algotrading.execution.portfolio import Portfolio
from algotrading.risk.manager import RiskLimits, RiskManager
from algotrading.strategies.base import Bar, Side, Signal, SignalType, Strategy


class ScriptedStrategy(Strategy):
    def __init__(self, token: int, name: str, signals: dict[datetime, Signal]) -> None:
        self.instrument_token = token
        self.name = name
        self._signals = signals

    def generate_signal(self, bar: Bar) -> Signal | None:
        return self._signals.get(bar.time)


def _bar(token: int, hour: int, minute: int, close: float) -> Bar:
    return Bar(token, datetime(2026, 6, 3, hour, minute), close, close, close, close)


def _entry(token: int, when: datetime) -> Signal:
    return Signal(when, token, SignalType.ENTRY, Side.BUY)


def _exit(token: int, when: datetime) -> Signal:
    return Signal(when, token, SignalType.EXIT, Side.SELL, reason="exit")


def _engine(**kw) -> MultiStrategyEngine:
    kw.setdefault("config", EngineConfig(fixed_quantity=10, use_atr_sizing=False))
    return MultiStrategyEngine(**kw)


def test_duplicate_instrument_registration_raises() -> None:
    engine = _engine()
    engine.add_strategy(ScriptedStrategy(1, "a", {}))
    try:
        engine.add_strategy(ScriptedStrategy(1, "b", {}))
    except ValueError:
        return
    raise AssertionError("expected ValueError for duplicate instrument")


def test_two_strategies_trade_independent_instruments() -> None:
    t1, t2 = datetime(2026, 6, 3, 9, 30), datetime(2026, 6, 3, 10, 0)
    engine = _engine()
    engine.add_strategy(ScriptedStrategy(1, "s1", {t1: _entry(1, t1), t2: _exit(1, t2)}))
    engine.add_strategy(ScriptedStrategy(2, "s2", {t1: _entry(2, t1)}))

    engine.on_bar(_bar(1, 9, 30, 100.0))
    engine.on_bar(_bar(2, 9, 30, 200.0))
    assert set(engine.portfolio.positions) == {1, 2}

    engine.on_bar(_bar(1, 10, 0, 110.0))  # s1 exits
    assert set(engine.portfolio.positions) == {2}
    assert engine.portfolio.realized_pnl > 0  # s1 booked a profit
    # Fills attributed to each strategy.
    strategies = {f.order.tag for f in engine.trade_log.fills}
    assert strategies == {"s1", "s2"}


def test_shared_max_positions_budget() -> None:
    t1 = datetime(2026, 6, 3, 9, 30)
    engine = _engine(risk=RiskManager(RiskLimits(max_open_positions=1)))
    engine.add_strategy(ScriptedStrategy(1, "s1", {t1: _entry(1, t1)}))
    engine.add_strategy(ScriptedStrategy(2, "s2", {t1: _entry(2, t1)}))

    engine.on_bar(_bar(1, 9, 30, 100.0))  # fills -> 1 open
    engine.on_bar(_bar(2, 9, 30, 200.0))  # blocked by shared cap
    assert set(engine.portfolio.positions) == {1}


def test_shared_kill_switch_blocks_all() -> None:
    t1 = datetime(2026, 6, 3, 9, 30)
    engine = _engine(
        risk=RiskManager(RiskLimits(daily_loss_limit=1000.0)),
        portfolio=Portfolio(realized_pnl=-2000.0),
    )
    engine.add_strategy(ScriptedStrategy(1, "s1", {t1: _entry(1, t1)}))
    engine.add_strategy(ScriptedStrategy(2, "s2", {t1: _entry(2, t1)}))
    engine.on_bar(_bar(1, 9, 30, 100.0))
    engine.on_bar(_bar(2, 9, 30, 200.0))
    assert engine.portfolio.open_position_count() == 0


def test_unregistered_instrument_is_ignored() -> None:
    engine = _engine()
    engine.add_strategy(ScriptedStrategy(1, "s1", {}))
    engine.on_bar(_bar(999, 9, 30, 50.0))  # no strategy for 999
    assert engine.portfolio.open_position_count() == 0
    assert engine.last_prices[999] == 50.0  # still marked for P&L
    assert len(engine.equity_curve) == 1


def test_square_off_flattens_across_strategies() -> None:
    t1 = datetime(2026, 6, 3, 9, 30)
    engine = _engine()
    engine.add_strategy(ScriptedStrategy(1, "s1", {t1: _entry(1, t1)}))
    engine.on_bar(_bar(1, 9, 30, 100.0))
    assert engine.portfolio.open_position_count() == 1
    engine.on_bar(_bar(1, 15, 15, 105.0))  # square-off time
    assert engine.portfolio.open_position_count() == 0
    assert engine.trade_log.fills[-1].order.reason == "square_off"
