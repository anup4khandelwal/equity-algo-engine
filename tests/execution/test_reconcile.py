"""Tests for broker ↔ internal position reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime

from algotrading.execution.portfolio import Portfolio
from algotrading.execution.reconcile import internal_positions, reconcile
from algotrading.strategies.base import Position, Side

NOW = datetime(2026, 6, 3, 9, 30, tzinfo=UTC)


def _portfolio(positions: dict[int, tuple[Side, int]]) -> Portfolio:
    return Portfolio(
        positions={t: Position(side, qty, 100.0, NOW) for t, (side, qty) in positions.items()}
    )


def test_internal_positions_signed() -> None:
    pf = _portfolio({1: (Side.BUY, 100), 2: (Side.SELL, 50)})
    assert internal_positions(pf) == {1: 100, 2: -50}


def test_no_discrepancy_when_matched() -> None:
    pf = _portfolio({1: (Side.BUY, 100)})
    assert reconcile(pf, {1: 100}) == []


def test_quantity_mismatch() -> None:
    pf = _portfolio({1: (Side.BUY, 100)})
    [d] = reconcile(pf, {1: 80})
    assert d.instrument_token == 1
    assert d.internal_qty == 100 and d.broker_qty == 80
    assert d.diff == -20  # broker is 20 short of internal


def test_broker_has_position_engine_doesnt() -> None:
    pf = _portfolio({})  # engine flat
    [d] = reconcile(pf, {5: 40})  # but broker shows a position (e.g. a manual trade)
    assert d.internal_qty == 0 and d.broker_qty == 40 and d.diff == 40


def test_direction_mismatch_is_flagged() -> None:
    pf = _portfolio({1: (Side.BUY, 100)})  # internal long
    [d] = reconcile(pf, {1: -100})  # broker short
    assert d.diff == -200
