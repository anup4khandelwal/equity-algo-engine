"""Tests for the Opening Range Breakout strategy.

Bars are fed directly to the strategy and the emitted signals collected, so the
state machine (range building, breakout, stop/target/square-off, one-trade-per-
day, daily reset) is verified in isolation from the simulator.
"""

from __future__ import annotations

from datetime import datetime

from algotrading.strategies.base import Bar, SignalType
from algotrading.strategies.orb import OpeningRangeBreakout

TOKEN = 1


def _bar(day: int, hour: int, minute: int, o, h, low, c) -> Bar:
    return Bar(TOKEN, datetime(2026, 6, day, hour, minute), o, h, low, c)


def _range_bars(day: int) -> list[Bar]:
    """Two bars in the 09:15-09:30 window -> range high 110, low 90."""
    return [
        _bar(day, 9, 15, 100, 110, 100, 105),
        _bar(day, 9, 16, 105, 108, 90, 100),
    ]


def _collect(strategy: OpeningRangeBreakout, bars: list[Bar]) -> list:
    return [sig for bar in bars if (sig := strategy.on_bar(bar)) is not None]


def test_long_breakout_then_target_exit() -> None:
    strat = OpeningRangeBreakout(TOKEN, opening_range_minutes=15, target_multiple=1.0)
    bars = [
        *_range_bars(3),
        _bar(3, 9, 31, 110, 112, 109, 111),  # close 111 > 110 -> long entry
        _bar(3, 9, 32, 111, 131, 110, 130),  # high 131 >= target (111+20) -> target exit
    ]
    signals = _collect(strat, bars)

    assert len(signals) == 2
    entry, exit_ = signals
    assert entry.type is SignalType.ENTRY and entry.side.value == "BUY"
    assert entry.price == 111 and entry.reason == "breakout"
    assert exit_.type is SignalType.EXIT and exit_.reason == "target"
    assert exit_.price == 131  # 111 + 1.0 * (110 - 90)


def test_short_breakout_then_stop_exit() -> None:
    strat = OpeningRangeBreakout(TOKEN, opening_range_minutes=15, target_multiple=1.0)
    bars = [
        *_range_bars(4),
        _bar(4, 9, 31, 91, 92, 88, 89),  # close 89 < 90 -> short entry
        _bar(4, 9, 32, 90, 111, 88, 100),  # high 111 >= stop (range high 110) -> stop exit
    ]
    signals = _collect(strat, bars)

    entry, exit_ = signals
    assert entry.side.value == "SELL" and entry.price == 89
    assert exit_.reason == "stop" and exit_.price == 110


def test_square_off_closes_open_position() -> None:
    strat = OpeningRangeBreakout(TOKEN, opening_range_minutes=15)
    bars = [
        *_range_bars(5),
        _bar(5, 9, 31, 110, 112, 109, 111),  # long entry
        _bar(5, 15, 15, 120, 121, 119, 120),  # 15:15 -> square off at close
    ]
    signals = _collect(strat, bars)
    assert signals[-1].reason == "square_off"
    assert signals[-1].price == 120


def test_only_one_trade_per_day() -> None:
    strat = OpeningRangeBreakout(TOKEN, opening_range_minutes=15, target_multiple=1.0)
    bars = [
        *_range_bars(6),
        _bar(6, 9, 31, 110, 112, 109, 111),  # entry
        _bar(6, 9, 32, 111, 131, 110, 130),  # target exit
        _bar(6, 9, 40, 130, 140, 129, 135),  # another breakout — must be ignored
    ]
    signals = _collect(strat, bars)
    assert len(signals) == 2  # no third (re-entry) signal


def test_no_entry_inside_opening_range_window() -> None:
    strat = OpeningRangeBreakout(TOKEN, opening_range_minutes=15)
    # A big move at 09:20 is still inside the range window -> no signal.
    bars = [
        _bar(7, 9, 15, 100, 110, 100, 105),
        _bar(7, 9, 20, 105, 200, 105, 199),
    ]
    assert _collect(strat, bars) == []


def test_state_resets_across_days() -> None:
    strat = OpeningRangeBreakout(TOKEN, opening_range_minutes=15, target_multiple=1.0)
    day1 = [
        *_range_bars(8),
        _bar(8, 9, 31, 110, 112, 109, 111),
        _bar(8, 9, 32, 111, 131, 110, 130),
    ]
    day2 = [
        *_range_bars(9),
        _bar(9, 9, 31, 110, 112, 109, 111),
        _bar(9, 9, 32, 111, 131, 110, 130),
    ]
    signals = _collect(strat, day1 + day2)
    # One round-trip per day -> 4 signals total.
    assert len(signals) == 4
