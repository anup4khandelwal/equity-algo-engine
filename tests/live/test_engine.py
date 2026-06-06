"""Tests for the paper-trading engine."""

from __future__ import annotations

from datetime import datetime

from algotrading.engine import EngineConfig, PaperTradingEngine
from algotrading.execution.portfolio import Portfolio
from algotrading.risk.manager import RiskLimits, RiskManager
from algotrading.strategies.base import Bar, Side, Signal, SignalType, Strategy


class ScriptedStrategy(Strategy):
    name = "scripted"

    def __init__(self, signals: dict[datetime, Signal]) -> None:
        self._signals = signals

    def generate_signal(self, bar: Bar) -> Signal | None:
        return self._signals.get(bar.time)


class CountingNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def notify(self, message: str) -> None:
        self.messages.append(message)


def _bar(h: int, m: int, close: float) -> Bar:
    return Bar(1, datetime(2026, 6, 3, h, m), close, close, close, close)


def _entry(when: datetime, side: Side) -> Signal:
    return Signal(when, 1, SignalType.ENTRY, side=side, price=None)


def _exit(when: datetime, side: Side) -> Signal:
    return Signal(when, 1, SignalType.EXIT, side=side, price=None, reason="exit")


def test_entry_then_exit_books_a_round_trip() -> None:
    t1, t2 = datetime(2026, 6, 3, 9, 30), datetime(2026, 6, 3, 10, 0)
    engine = PaperTradingEngine(
        ScriptedStrategy({t1: _entry(t1, Side.BUY), t2: _exit(t2, Side.SELL)}),
        config=EngineConfig(fixed_quantity=100, use_atr_sizing=False),
    )
    engine.on_bar(_bar(9, 30, 100.0))
    assert engine.portfolio.open_position_count() == 1

    engine.on_bar(_bar(10, 0, 110.0))
    assert engine.portfolio.open_position_count() == 0
    # ~1000 gross minus costs > 0, net of charges.
    assert 0 < engine.portfolio.realized_pnl < 1000
    assert len(engine.trade_log.fills) == 2


def test_kill_switch_blocks_entry() -> None:
    t1 = datetime(2026, 6, 3, 9, 30)
    engine = PaperTradingEngine(
        ScriptedStrategy({t1: _entry(t1, Side.BUY)}),
        risk=RiskManager(RiskLimits(daily_loss_limit=1000.0)),
        portfolio=Portfolio(realized_pnl=-2000.0),  # already past the limit
        notifier=CountingNotifier(),
        config=EngineConfig(fixed_quantity=10, use_atr_sizing=False),
    )
    engine.on_bar(_bar(9, 30, 100.0))
    assert engine.portfolio.open_position_count() == 0
    assert any("blocked by risk" in m for m in engine.notifier.messages)


def test_max_positions_blocks_entry() -> None:
    t1 = datetime(2026, 6, 3, 9, 30)
    engine = PaperTradingEngine(
        ScriptedStrategy({t1: _entry(t1, Side.BUY)}),
        risk=RiskManager(RiskLimits(max_open_positions=0)),
        config=EngineConfig(fixed_quantity=10, use_atr_sizing=False),
    )
    engine.on_bar(_bar(9, 30, 100.0))
    assert engine.portfolio.open_position_count() == 0


def test_square_off_flattens_open_position() -> None:
    t1 = datetime(2026, 6, 3, 9, 30)
    # Only an entry signal; no exit. The engine must flatten at square-off.
    engine = PaperTradingEngine(
        ScriptedStrategy({t1: _entry(t1, Side.BUY)}),
        config=EngineConfig(fixed_quantity=50, use_atr_sizing=False),
    )
    engine.on_bar(_bar(9, 30, 100.0))
    assert engine.portfolio.open_position_count() == 1

    engine.on_bar(_bar(15, 15, 105.0))  # square-off time
    assert engine.portfolio.open_position_count() == 0
    last = engine.trade_log.fills[-1].order
    assert last.tag == "scripted"  # attributed to the strategy
    assert last.reason == "square_off"  # reason preserved separately


def test_fill_listener_receives_filled_orders() -> None:
    t1, t2 = datetime(2026, 6, 3, 9, 30), datetime(2026, 6, 3, 10, 0)
    received = []
    engine = PaperTradingEngine(
        ScriptedStrategy({t1: _entry(t1, Side.BUY), t2: _exit(t2, Side.SELL)}),
        config=EngineConfig(fixed_quantity=10, use_atr_sizing=False),
        fill_listener=received.append,
    )
    engine.on_bar(_bar(9, 30, 100.0))
    engine.on_bar(_bar(10, 0, 110.0))
    assert len(received) == 2  # entry + exit fills
    assert all(f.status.value == "FILLED" for f in received)


def test_atr_sizing_used_when_enabled() -> None:
    # Build enough history for ATR, then enter.
    signals = {}
    enter_t = datetime(2026, 6, 3, 9, 40)
    signals[enter_t] = _entry(enter_t, Side.BUY)
    engine = PaperTradingEngine(
        ScriptedStrategy(signals),
        config=EngineConfig(
            capital=100_000, risk_per_trade=0.01, atr_stop_multiple=1.5, use_atr_sizing=True
        ),
    )
    # Feed warm-up bars with a ~2.0 true range, then the entry bar.
    for i in range(20):
        c = 100.0 + i * 0.1
        engine.on_bar(Bar(1, datetime(2026, 6, 3, 9, 20 + i), c, c + 1, c - 1, c))
    engine.on_bar(Bar(1, enter_t, 102.0, 103.0, 101.0, 102.0))

    pos = engine.portfolio.positions.get(1)
    assert pos is not None and pos.quantity > 0
