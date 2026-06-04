"""DB-integration tests for the repositories.

Run against PostgreSQL in CI; skipped automatically when no DB is reachable
(see conftest.py). These exercise the ON CONFLICT upsert paths, which are
PostgreSQL-specific.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from algotrading.data.repositories import InstrumentRepository, OHLCRepository

pytestmark = pytest.mark.usefixtures("db_session")


def _instrument(token: int = 408065, symbol: str = "INFY") -> dict:
    return {
        "instrument_token": token,
        "exchange_token": 1594,
        "tradingsymbol": symbol,
        "name": "INFOSYS",
        "exchange": "NSE",
        "segment": "NSE",
        "instrument_type": "EQ",
        "lot_size": 1,
        "tick_size": 0.05,
        "expiry": None,
        "strike": None,
        "last_price": 1500.5,
    }


def test_instrument_upsert_is_idempotent_and_updates(db_session) -> None:
    repo = InstrumentRepository(db_session)

    repo.upsert_many([_instrument()])
    db_session.flush()
    assert repo.count() == 1

    # Re-upsert with a changed price: still one row, value refreshed.
    updated = _instrument()
    updated["last_price"] = 1600.0
    repo.upsert_many([updated])
    db_session.flush()

    assert repo.count() == 1
    found = repo.get_by_symbol("NSE", "INFY")
    assert found is not None
    assert found.last_price == 1600.0


def test_get_by_symbol_returns_none_when_absent(db_session) -> None:
    repo = InstrumentRepository(db_session)
    assert repo.get_by_symbol("NSE", "NOPE") is None


def test_ohlc_upsert_and_range_query(db_session) -> None:
    InstrumentRepository(db_session).upsert_many([_instrument()])
    db_session.flush()

    ohlc = OHLCRepository(db_session)
    rows = [
        {
            "instrument_token": 408065,
            "time": datetime(2026, 6, 3, 9, 15 + i, tzinfo=UTC),
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1000 + i,
        }
        for i in range(3)
    ]
    assert ohlc.upsert_bars(rows) == 3
    db_session.flush()

    result = ohlc.get_range(
        408065,
        datetime(2026, 6, 3, 9, 15, tzinfo=UTC),
        datetime(2026, 6, 3, 9, 16, tzinfo=UTC),
    )
    assert [bar.close for bar in result] == [100.5, 101.5]  # 9:15 and 9:16 only


def test_ohlc_upsert_overwrites_existing_bar(db_session) -> None:
    InstrumentRepository(db_session).upsert_many([_instrument()])
    db_session.flush()
    ohlc = OHLCRepository(db_session)

    t = datetime(2026, 6, 3, 9, 15, tzinfo=UTC)
    base = {
        "instrument_token": 408065,
        "time": t,
        "open": 1.0,
        "high": 1.0,
        "low": 1.0,
        "close": 1.0,
        "volume": 1,
    }
    ohlc.upsert_bars([base])
    db_session.flush()
    ohlc.upsert_bars([{**base, "close": 2.0, "volume": 50}])
    db_session.flush()

    result = ohlc.get_range(408065, t, t)
    assert len(result) == 1
    assert result[0].close == 2.0
    assert result[0].volume == 50
