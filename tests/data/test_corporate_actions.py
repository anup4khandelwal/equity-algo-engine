"""Tests for corporate-action price adjustment."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from algotrading.data.corporate_actions import (
    adjust_bars,
    bonus_action,
    split_action,
)
from algotrading.strategies.base import Bar


def _bar(day: int, close: float, volume: int = 1000) -> Bar:
    return Bar(1, datetime(2026, 6, day, 9, 15), close, close, close, close, volume)


def test_split_back_adjusts_pre_ex_prices() -> None:
    # 1:5 split, ex-date 2026-06-10. Pre-ex prices scale by 1/5, volume *5.
    action = split_action(1, date(2026, 6, 10), old=1, new=5)
    bars = [_bar(9, 1000.0, 100), _bar(10, 200.0, 500)]  # day 9 pre-ex, day 10 ex
    adjusted = adjust_bars(bars, [action])

    assert adjusted[0].close == pytest.approx(200.0)  # 1000 * 1/5
    assert adjusted[0].volume == 500  # 100 / (1/5)
    assert adjusted[1].close == pytest.approx(200.0)  # on/after ex unchanged
    assert adjusted[1].volume == 500


def test_bonus_one_for_one_halves_pre_ex_prices() -> None:
    action = bonus_action(1, date(2026, 6, 10), held=1, bonus=1)  # ratio 0.5
    adjusted = adjust_bars([_bar(9, 100.0)], [action])
    assert adjusted[0].close == pytest.approx(50.0)


def test_multiple_actions_compound() -> None:
    a1 = split_action(1, date(2026, 6, 10), 1, 2)  # ratio 0.5
    a2 = bonus_action(1, date(2026, 6, 20), 1, 1)  # ratio 0.5
    # A bar before both ex-dates scales by 0.5 * 0.5 = 0.25.
    adjusted = adjust_bars([_bar(9, 400.0)], [a1, a2])
    assert adjusted[0].close == pytest.approx(100.0)


def test_no_actions_leaves_bars_unchanged() -> None:
    bars = [_bar(9, 100.0), _bar(10, 110.0)]
    adjusted = adjust_bars(bars, [])
    assert [b.close for b in adjusted] == [100.0, 110.0]


def test_invalid_ratios_raise() -> None:
    with pytest.raises(ValueError):
        split_action(1, date(2026, 6, 10), 0, 5)
    with pytest.raises(ValueError):
        bonus_action(1, date(2026, 6, 10), 1, 0)
