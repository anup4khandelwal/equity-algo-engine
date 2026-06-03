"""Tests for Kite payload -> row-dict mappers."""

from __future__ import annotations

from datetime import date, datetime

from algotrading.data.mappers import parse_bar, parse_instrument


def test_parse_equity_instrument() -> None:
    record = {
        "instrument_token": 408065,
        "exchange_token": 1594,
        "tradingsymbol": "INFY",
        "name": "INFOSYS",
        "exchange": "NSE",
        "segment": "NSE",
        "instrument_type": "EQ",
        "lot_size": 1,
        "tick_size": 0.05,
        "expiry": "",
        "strike": 0,
        "last_price": 1500.5,
    }
    parsed = parse_instrument(record)
    assert parsed["instrument_token"] == 408065
    assert parsed["tradingsymbol"] == "INFY"
    assert parsed["expiry"] is None  # empty expiry -> None
    assert parsed["strike"] is None  # strike 0 -> not applicable
    assert parsed["last_price"] == 1500.5


def test_parse_option_instrument_with_typed_values() -> None:
    record = {
        "instrument_token": 12345,
        "exchange_token": 48,
        "tradingsymbol": "NIFTY26JUN25000CE",
        "name": "NIFTY",
        "exchange": "NFO",
        "segment": "NFO-OPT",
        "instrument_type": "CE",
        "lot_size": 75,
        "tick_size": 0.05,
        "expiry": date(2026, 6, 25),
        "strike": 25000.0,
    }
    parsed = parse_instrument(record)
    assert parsed["expiry"] == date(2026, 6, 25)
    assert parsed["strike"] == 25000.0
    assert parsed["lot_size"] == 75
    assert parsed["last_price"] is None  # missing key -> None


def test_parse_instrument_coerces_string_expiry() -> None:
    record = {
        "instrument_token": "1",
        "tradingsymbol": "X",
        "exchange": "NFO",
        "instrument_type": "FUT",
        "expiry": "2026-06-25",
    }
    assert parse_instrument(record)["expiry"] == date(2026, 6, 25)


def test_parse_bar_from_datetime() -> None:
    bar = parse_bar(
        408065,
        {
            "date": datetime(2026, 6, 3, 9, 15),
            "open": 100.0,
            "high": 101.5,
            "low": 99.5,
            "close": 101.0,
            "volume": 1200,
        },
    )
    assert bar == {
        "instrument_token": 408065,
        "time": datetime(2026, 6, 3, 9, 15),
        "open": 100.0,
        "high": 101.5,
        "low": 99.5,
        "close": 101.0,
        "volume": 1200,
    }


def test_parse_bar_coerces_string_date_and_missing_volume() -> None:
    bar = parse_bar(
        1,
        {"date": "2026-06-03T09:16:00", "open": 1, "high": 2, "low": 0.5, "close": 1.5},
    )
    assert bar["time"] == datetime(2026, 6, 3, 9, 16)
    assert bar["volume"] == 0
