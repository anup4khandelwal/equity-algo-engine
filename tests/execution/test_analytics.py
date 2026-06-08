"""Tests for round-trip trade reconstruction from fills."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from algotrading.execution.analytics import (
    FillEvent,
    event_from_fill,
    event_from_record,
    round_trips,
)
from algotrading.execution.gateway import Fill, Order, OrderStatus
from algotrading.strategies.base import Side

T0 = datetime(2026, 6, 3, 9, 30, tzinfo=UTC)


def _ev(
    side: str, qty: int, price: float, charges: float, minute: int, token: int = 1
) -> FillEvent:
    return FillEvent(token, side, qty, price, charges, T0 + timedelta(minutes=minute), "orb")


def test_simple_long_round_trip_net_of_charges() -> None:
    events = [_ev("BUY", 100, 100.0, 5.0, 0), _ev("SELL", 100, 110.0, 7.0, 5)]
    trips = round_trips(events)
    assert len(trips) == 1
    t = trips[0]
    assert t.direction == "BUY" and t.quantity == 100
    assert t.gross_pnl == pytest.approx(1000.0)
    assert t.charges == pytest.approx(12.0)
    assert t.net_pnl == pytest.approx(988.0)
    assert t.holding_seconds == pytest.approx(300.0)


def test_short_round_trip_profits_when_price_falls() -> None:
    events = [_ev("SELL", 50, 100.0, 0.0, 0), _ev("BUY", 50, 90.0, 0.0, 1)]
    trips = round_trips(events)
    assert trips[0].direction == "SELL"
    assert trips[0].gross_pnl == pytest.approx(500.0)


def test_partial_exit_then_full_exit() -> None:
    events = [
        _ev("BUY", 100, 100.0, 0.0, 0),
        _ev("SELL", 60, 110.0, 0.0, 1),  # close 60
        _ev("SELL", 40, 120.0, 0.0, 2),  # close remaining 40
    ]
    trips = round_trips(events)
    assert [t.quantity for t in trips] == [60, 40]
    assert trips[1].exit_price == 120.0


def test_open_position_not_emitted() -> None:
    trips = round_trips([_ev("BUY", 100, 100.0, 0.0, 0)])  # never closed
    assert trips == []


def test_flip_past_flat_opens_new_lot() -> None:
    events = [
        _ev("BUY", 100, 100.0, 0.0, 0),
        _ev("SELL", 150, 110.0, 0.0, 1),  # close 100 long, open 50 short
        _ev("BUY", 50, 105.0, 0.0, 2),  # close the 50 short
    ]
    trips = round_trips(events)
    assert [t.direction for t in trips] == ["BUY", "SELL"]
    assert trips[1].quantity == 50


def test_multiple_instruments_independent() -> None:
    events = [
        _ev("BUY", 10, 100.0, 0.0, 0, token=1),
        _ev("BUY", 5, 200.0, 0.0, 0, token=2),
        _ev("SELL", 10, 105.0, 0.0, 1, token=1),
        _ev("SELL", 5, 190.0, 0.0, 1, token=2),
    ]
    trips = round_trips(events)
    by_token = {t.instrument_token: t for t in trips}
    assert by_token[1].net_pnl == pytest.approx(50.0)
    assert by_token[2].net_pnl == pytest.approx(-50.0)


def test_pnl_by_strategy_groups_and_aggregates() -> None:
    from algotrading.execution.analytics import pnl_by_strategy

    events = [
        FillEvent(1, "BUY", 10, 100.0, 0.0, T0, "orb"),
        FillEvent(1, "SELL", 10, 110.0, 0.0, T0 + timedelta(minutes=1), "orb"),  # +100
        FillEvent(2, "BUY", 10, 100.0, 0.0, T0, "rsi2"),
        FillEvent(2, "SELL", 10, 95.0, 0.0, T0 + timedelta(minutes=1), "rsi2"),  # -50
    ]
    stats = {s.strategy: s for s in pnl_by_strategy(round_trips(events))}
    assert stats["orb"].net_pnl == pytest.approx(100.0)
    assert stats["orb"].win_rate == 1.0
    assert stats["rsi2"].net_pnl == pytest.approx(-50.0)
    assert stats["rsi2"].win_rate == 0.0
    assert stats["orb"].trades == 1


def test_adapters_from_fill_and_record() -> None:
    fill = Fill(
        Order(1, Side.BUY, 10, reference_price=100.0, tag="orb"),
        OrderStatus.FILLED,
        100.0,
        10,
        T0,
        charges=2.0,
    )
    ev = event_from_fill(fill)
    assert ev.side == "BUY" and ev.strategy == "orb" and ev.price == 100.0

    class _Rec:
        instrument_token = 1
        side = "SELL"
        quantity = 10
        price = 105.0
        charges = 3.0
        time = T0
        strategy = "momentum"

    ev2 = event_from_record(_Rec())
    assert ev2.side == "SELL" and ev2.strategy == "momentum"
