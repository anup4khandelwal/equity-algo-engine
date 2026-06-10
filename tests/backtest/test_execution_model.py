"""Tests for the NSE/BSE execution model and the simulator's realistic path."""

from __future__ import annotations

from datetime import datetime

import pytest

from algotrading.backtest.execution_model import ExecutionModel
from algotrading.backtest.simulator import BacktestConfig, run
from algotrading.strategies.base import Bar, Side, Signal, SignalType, Strategy


# --- the model in isolation ---------------------------------------------------
def test_tick_rounding_to_5_paise() -> None:
    m = ExecutionModel(tick_size=0.05, slippage_bps=0.0)
    assert m.round_to_tick(100.03) == pytest.approx(100.05)
    assert m.round_to_tick(100.02) == pytest.approx(100.00)
    assert m.fill_price(100.02, Side.BUY) == pytest.approx(100.00)


def test_slippage_then_tick() -> None:
    m = ExecutionModel(tick_size=0.05, slippage_bps=10.0)  # 0.1%
    # buy 1000 -> 1001 -> already on a tick
    assert m.fill_price(1000.0, Side.BUY) == pytest.approx(1001.0)
    assert m.fill_price(1000.0, Side.SELL) == pytest.approx(999.0)


def test_circuit_band_membership_and_clamp() -> None:
    m = ExecutionModel(circuit_pct=0.10)
    assert m.within_band(108.0, prev_close=100.0)  # within 10%
    assert not m.within_band(111.0, prev_close=100.0)  # beyond 10%
    assert m.within_band(111.0, prev_close=None)  # no reference -> allowed
    assert m.clamp_to_band(120.0, prev_close=100.0) == pytest.approx(110.0)
    assert m.clamp_to_band(80.0, prev_close=100.0) == pytest.approx(90.0)


def test_participation_cap() -> None:
    m = ExecutionModel(max_participation=0.10)
    assert m.cap_quantity(1000, bar_volume=5000) == 500  # 10% of 5000
    assert m.cap_quantity(100, bar_volume=5000) == 100  # under the cap
    assert m.cap_quantity(1000, bar_volume=0) == 1000  # no volume -> cap disabled


def test_invalid_model() -> None:
    with pytest.raises(ValueError):
        ExecutionModel(fill_at="immediate")
    with pytest.raises(ValueError):
        ExecutionModel(tick_size=0)


# --- integrated with the simulator -------------------------------------------
class ScriptedStrategy(Strategy):
    def __init__(self, signals: dict[datetime, Signal]) -> None:
        self._signals = signals

    def generate_signal(self, bar: Bar) -> Signal | None:
        return self._signals.get(bar.time)


def _bar(minute: int, o, h, low, c, vol=0) -> Bar:
    return Bar(1, datetime(2026, 6, 3, 9, minute), o, h, low, c, vol)


def _entry(minute: int, side: Side) -> Signal:
    return Signal(datetime(2026, 6, 3, 9, minute), 1, SignalType.ENTRY, side, None, "x")


def _exit(minute: int, side: Side) -> Signal:
    return Signal(datetime(2026, 6, 3, 9, minute), 1, SignalType.EXIT, side, None, "x")


def test_next_open_fill_kills_lookahead() -> None:
    # Decide at 9:15 (close 100), but the trade fills at 9:16's OPEN (105), not the
    # close it was decided on — that's the look-ahead fix.
    strat = ScriptedStrategy(
        {
            datetime(2026, 6, 3, 9, 15): _entry(15, Side.BUY),
            datetime(2026, 6, 3, 9, 20): _exit(20, Side.SELL),
        }
    )
    bars = [
        _bar(15, 100.0, 100.0, 100.0, 100.0),
        _bar(16, 105.0, 106.0, 104.0, 105.5),  # entry fills here at open 105
        _bar(20, 110.0, 110.0, 110.0, 110.0),  # exit signal at 9:20 close
        _bar(21, 112.0, 112.0, 112.0, 112.0),  # exit fills here at open 112
    ]
    model = ExecutionModel(tick_size=0.05, slippage_bps=0.0, fill_at="next_open")
    result = run(strat, bars, BacktestConfig(quantity=100, execution=model))

    assert len(result.trades) == 1
    t = result.trades[0]
    assert t.entry_price == pytest.approx(105.0)  # next-bar open, not 100 close
    assert t.exit_price == pytest.approx(112.0)  # next-bar open after the exit signal


def test_entry_rejected_at_circuit() -> None:
    # Prev close 100, 5% band; next-open 110 is beyond +5% -> entry rejected.
    strat = ScriptedStrategy({datetime(2026, 6, 3, 9, 15): _entry(15, Side.BUY)})
    bars = [
        _bar(15, 100.0, 100.0, 100.0, 100.0),
        _bar(16, 110.0, 110.0, 110.0, 110.0),  # gap-up beyond circuit
        _bar(17, 110.0, 110.0, 110.0, 110.0),
    ]
    model = ExecutionModel(circuit_pct=0.05, slippage_bps=0.0, fill_at="next_open")
    result = run(strat, bars, BacktestConfig(quantity=10, execution=model))
    assert result.trades == []  # couldn't get in through the circuit


def test_participation_caps_fill_size() -> None:
    strat = ScriptedStrategy(
        {
            datetime(2026, 6, 3, 9, 15): _entry(15, Side.BUY),
            datetime(2026, 6, 3, 9, 17): _exit(17, Side.SELL),
        }
    )
    bars = [
        _bar(15, 100.0, 100.0, 100.0, 100.0),
        _bar(16, 100.0, 100.0, 100.0, 100.0, vol=1000),  # entry fills, vol 1000
        _bar(17, 101.0, 101.0, 101.0, 101.0),
        _bar(18, 101.0, 101.0, 101.0, 101.0),
    ]
    # Want 1000 sh but cap at 10% of 1000 = 100.
    model = ExecutionModel(max_participation=0.10, slippage_bps=0.0, fill_at="next_open")
    result = run(strat, bars, BacktestConfig(quantity=1000, execution=model))
    assert result.trades[0].quantity == 100
