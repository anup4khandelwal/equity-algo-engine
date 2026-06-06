"""DB-integration tests for fill persistence.

Skipped automatically when no database is reachable (see conftest.py).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from algotrading.backtest.costs import Product
from algotrading.data.repositories import FillRepository, fill_to_record
from algotrading.execution.gateway import Fill, Order, OrderStatus
from algotrading.strategies.base import Side

pytestmark = pytest.mark.usefixtures("db_session")

NOW = datetime(2026, 6, 3, 9, 30, tzinfo=UTC)


def _fill(side: Side, qty: int, price: float, tag: str, reason: str) -> Fill:
    order = Order(
        instrument_token=408065,
        side=side,
        quantity=qty,
        reference_price=price,
        product=Product.INTRADAY,
        tag=tag,
        reason=reason,
    )
    return Fill(order, OrderStatus.FILLED, price, qty, NOW, charges=5.0)


def test_fill_to_record_maps_fields() -> None:
    record = fill_to_record(_fill(Side.BUY, 100, 100.0, "orb", "breakout"))
    assert record.instrument_token == 408065
    assert record.side == "BUY"
    assert record.strategy == "orb"
    assert record.reason == "breakout"
    assert record.product == "intraday"
    assert record.status == "FILLED"


def test_add_and_list(db_session) -> None:
    repo = FillRepository(db_session)
    repo.add(_fill(Side.BUY, 100, 100.0, "orb", "breakout"))
    repo.add(_fill(Side.SELL, 100, 110.0, "orb", "target"))
    db_session.flush()

    rows = repo.list_fills()
    assert len(rows) == 2
    assert rows[0].side == "BUY"
    assert rows[1].reason == "target"


def test_filter_by_strategy(db_session) -> None:
    repo = FillRepository(db_session)
    repo.add_many(
        [
            _fill(Side.BUY, 10, 100.0, "orb", "breakout"),
            _fill(Side.BUY, 5, 200.0, "momentum", "momentum"),
        ]
    )
    db_session.flush()
    assert len(repo.list_fills(strategy="momentum")) == 1
    assert repo.list_fills(strategy="momentum")[0].instrument_token == 408065


def test_limit(db_session) -> None:
    repo = FillRepository(db_session)
    repo.add_many([_fill(Side.BUY, 1, 100.0, "orb", "x") for _ in range(5)])
    db_session.flush()
    assert len(repo.list_fills(limit=3)) == 3
