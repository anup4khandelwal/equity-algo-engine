"""Pure transforms from Kite API payloads into row dicts for our tables.

Kept free of any DB or network dependency so they are trivially unit-testable.
Kite's ``instruments()`` and ``historical_data()`` may return already-parsed
Python types (via the kiteconnect SDK) or raw strings (e.g. from a CSV dump), so
these helpers coerce both.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _to_date(value: Any) -> date | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _to_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    number = float(value)
    # Equities/futures report strike 0; treat that as "not applicable".
    return number if number != 0 else None


def parse_instrument(record: dict[str, Any]) -> dict[str, Any]:
    """Map a Kite instrument record to ``Instrument`` column values."""
    exchange_token = record.get("exchange_token")
    return {
        "instrument_token": int(record["instrument_token"]),
        "exchange_token": (int(exchange_token) if exchange_token not in (None, "") else None),
        "tradingsymbol": str(record["tradingsymbol"]),
        "name": (str(record["name"]) if record.get("name") else None),
        "exchange": str(record["exchange"]),
        "segment": (str(record["segment"]) if record.get("segment") else None),
        "instrument_type": str(record.get("instrument_type", "")),
        "lot_size": int(record.get("lot_size") or 1),
        "tick_size": float(record.get("tick_size") or 0.05),
        "expiry": _to_date(record.get("expiry")),
        "strike": _to_optional_float(record.get("strike")),
        "last_price": _to_optional_float(record.get("last_price")),
    }


def parse_bar(instrument_token: int, record: dict[str, Any]) -> dict[str, Any]:
    """Map a Kite historical bar to ``OHLCBar`` column values."""
    raw_time = record["date"]
    if isinstance(raw_time, str):
        raw_time = datetime.fromisoformat(raw_time)
    return {
        "instrument_token": int(instrument_token),
        "time": raw_time,
        "open": float(record["open"]),
        "high": float(record["high"]),
        "low": float(record["low"]),
        "close": float(record["close"]),
        "volume": int(record.get("volume") or 0),
    }
