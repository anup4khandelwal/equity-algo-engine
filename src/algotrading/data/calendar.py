"""NSE trading calendar.

Weekend handling is built in; exchange holidays are data that must be kept
current, so they are loaded from a file (see ``config/nse_holidays.json``) or
injected, rather than hard-coded as authoritative in source. Times are naive
exchange-local (IST).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path


def load_holidays(path: str | Path) -> frozenset[date]:
    """Load holiday dates from a JSON file.

    Accepts either a bare list of ISO dates, or an object with a ``holidays``
    list (so the file can also carry a ``_source``/``_note`` for maintenance).
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data["holidays"] if isinstance(data, dict) else data
    return frozenset(date.fromisoformat(d) for d in items)


@dataclass(frozen=True)
class TradingCalendar:
    """NSE session calendar: weekends + injected holidays, plus market hours."""

    holidays: frozenset[date] = field(default_factory=frozenset)
    session_open: time = time(9, 15)
    session_close: time = time(15, 30)

    @classmethod
    def from_file(cls, path: str | Path, **kwargs) -> TradingCalendar:
        return cls(holidays=load_holidays(path), **kwargs)

    def is_trading_day(self, day: date) -> bool:
        return day.weekday() < 5 and day not in self.holidays

    def is_session_time(self, when: datetime) -> bool:
        return self.is_trading_day(when.date()) and (
            self.session_open <= when.time() <= self.session_close
        )

    def next_session(self, day: date) -> date:
        nxt = day + timedelta(days=1)
        while not self.is_trading_day(nxt):
            nxt += timedelta(days=1)
        return nxt

    def previous_session(self, day: date) -> date:
        prev = day - timedelta(days=1)
        while not self.is_trading_day(prev):
            prev -= timedelta(days=1)
        return prev

    def sessions(self, start: date, end: date) -> list[date]:
        """Trading days in ``[start, end]`` inclusive."""
        days: list[date] = []
        cursor = start
        while cursor <= end:
            if self.is_trading_day(cursor):
                days.append(cursor)
            cursor += timedelta(days=1)
        return days

    def missing_sessions(self, start: date, end: date, present: Iterable[date]) -> list[date]:
        """Trading days in range with no data — useful for gap detection."""
        have = set(present)
        return [d for d in self.sessions(start, end) if d not in have]
