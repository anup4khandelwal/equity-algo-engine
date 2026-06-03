"""Tests for backfill orchestration (Kite client + repositories mocked)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from algotrading.data.backfill import backfill_bars, sync_instruments


class FakeInstrumentRepo:
    def __init__(self) -> None:
        self.upserted: list[dict[str, Any]] = []

    def upsert_many(self, records: list[dict[str, Any]]) -> int:
        self.upserted.extend(records)
        return len(records)


class FakeOHLCRepo:
    def __init__(self) -> None:
        self.batches: list[list[dict[str, Any]]] = []

    def upsert_bars(self, rows: list[dict[str, Any]]) -> int:
        self.batches.append(rows)
        return len(rows)


class FakeClient:
    def __init__(self, instruments=None, bars=None) -> None:
        self._instruments = instruments or []
        self._bars = bars or []
        self.instruments_calls: list[str | None] = []
        self.historical_calls: list[tuple[int, date, date, str]] = []

    def instruments(self, exchange: str | None = None):
        self.instruments_calls.append(exchange)
        return self._instruments

    def historical_data(self, instrument_token, from_date, to_date, interval):
        self.historical_calls.append((instrument_token, from_date, to_date, interval))
        return self._bars


def test_sync_instruments_maps_and_upserts() -> None:
    client = FakeClient(
        instruments=[
            {
                "instrument_token": 1,
                "tradingsymbol": "INFY",
                "exchange": "NSE",
                "instrument_type": "EQ",
            }
        ]
    )
    repo = FakeInstrumentRepo()

    count = sync_instruments(client, repo, "NSE")

    assert count == 1
    assert client.instruments_calls == ["NSE"]
    assert repo.upserted[0]["tradingsymbol"] == "INFY"


def test_sync_instruments_without_exchange_fetches_all() -> None:
    client = FakeClient(instruments=[])
    sync_instruments(client, FakeInstrumentRepo())
    assert client.instruments_calls == [None]


def test_backfill_bars_chunks_requests_and_stores() -> None:
    bar = {
        "date": datetime(2026, 1, 1, 9, 15),
        "open": 1,
        "high": 2,
        "low": 0.5,
        "close": 1.5,
        "volume": 10,
    }
    client = FakeClient(bars=[bar])
    repo = FakeOHLCRepo()

    total = backfill_bars(
        client,
        repo,
        instrument_token=408065,
        start=date(2026, 1, 1),
        end=date(2026, 1, 5),
        interval="minute",
        chunk_days=2,
    )

    # 3 windows (2+2+1 days), one bar each -> 3 stored.
    assert total == 3
    assert len(client.historical_calls) == 3
    assert client.historical_calls[0] == (408065, date(2026, 1, 1), date(2026, 1, 2), "minute")
    assert repo.batches[0][0]["instrument_token"] == 408065


def test_backfill_bars_handles_empty_response() -> None:
    client = FakeClient(bars=[])
    repo = FakeOHLCRepo()
    total = backfill_bars(
        client, repo, 1, date(2026, 1, 1), date(2026, 1, 1), chunk_days=60
    )
    assert total == 0
    assert client.historical_calls == [(1, date(2026, 1, 1), date(2026, 1, 1), "minute")]
