"""Tests for the NSE trading calendar."""

from __future__ import annotations

import json
from datetime import date, datetime

from algotrading.data.calendar import TradingCalendar, load_holidays


def _cal() -> TradingCalendar:
    # 2026-01-26 (Republic Day) is a Monday holiday for this test.
    return TradingCalendar(holidays=frozenset({date(2026, 1, 26)}))


def test_weekends_are_not_trading_days() -> None:
    cal = _cal()
    assert not cal.is_trading_day(date(2026, 1, 24))  # Saturday
    assert not cal.is_trading_day(date(2026, 1, 25))  # Sunday
    assert cal.is_trading_day(date(2026, 1, 27))  # Tuesday


def test_holiday_is_not_a_trading_day() -> None:
    assert not _cal().is_trading_day(date(2026, 1, 26))


def test_is_session_time() -> None:
    cal = _cal()
    assert cal.is_session_time(datetime(2026, 1, 27, 9, 15))
    assert cal.is_session_time(datetime(2026, 1, 27, 15, 30))
    assert not cal.is_session_time(datetime(2026, 1, 27, 9, 0))  # pre-open
    assert not cal.is_session_time(datetime(2026, 1, 27, 16, 0))  # post-close
    assert not cal.is_session_time(datetime(2026, 1, 26, 10, 0))  # holiday


def test_next_and_previous_session_skip_non_trading_days() -> None:
    cal = _cal()
    # Friday 2026-01-23 -> next is Tuesday 27 (Sat/Sun + Mon holiday skipped).
    assert cal.next_session(date(2026, 1, 23)) == date(2026, 1, 27)
    assert cal.previous_session(date(2026, 1, 27)) == date(2026, 1, 23)


def test_sessions_lists_trading_days() -> None:
    cal = _cal()
    sessions = cal.sessions(date(2026, 1, 23), date(2026, 1, 27))
    assert sessions == [date(2026, 1, 23), date(2026, 1, 27)]


def test_missing_sessions_detects_gaps() -> None:
    cal = _cal()
    present = [date(2026, 1, 23)]
    assert cal.missing_sessions(date(2026, 1, 23), date(2026, 1, 27), present) == [
        date(2026, 1, 27)
    ]


def test_load_holidays_from_file(tmp_path) -> None:
    path = tmp_path / "h.json"
    path.write_text(json.dumps({"holidays": ["2026-01-26", "2026-12-25"]}), encoding="utf-8")
    holidays = load_holidays(path)
    assert date(2026, 1, 26) in holidays and date(2026, 12, 25) in holidays


def test_shipped_holidays_file_loads() -> None:
    cal = TradingCalendar.from_file("config/nse_holidays.json")
    assert date(2026, 1, 26) in cal.holidays  # Republic Day
    assert not cal.is_trading_day(date(2026, 1, 26))
