"""Tests for the Portfolio position/P&L tracker."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from algotrading.execution.gateway import Fill, Order, OrderStatus
from algotrading.execution.portfolio import Portfolio
from algotrading.strategies.base import Side

NOW = datetime(2026, 6, 3, 9, 30, tzinfo=UTC)


def _fill(side: Side, qty: int, price: float, charges: float = 5.0) -> Fill:
    return Fill(
        order=Order(1, side, qty, reference_price=price),
        status=OrderStatus.FILLED,
        fill_price=price,
        quantity=qty,
        time=NOW,
        charges=charges,
    )


def test_open_then_close_realises_net_pnl() -> None:
    pf = Portfolio()
    pf.apply_fill(_fill(Side.BUY, 100, 100.0, charges=5.0))
    assert pf.open_position_count() == 1

    pf.apply_fill(_fill(Side.SELL, 100, 110.0, charges=7.0))
    assert pf.open_position_count() == 0
    # gross 1000 minus 5 + 7 charges
    assert pf.realized_pnl == pytest.approx(1000.0 - 12.0)
    assert pf.total_charges == pytest.approx(12.0)


def test_adding_to_position_averages_entry() -> None:
    pf = Portfolio()
    pf.apply_fill(_fill(Side.BUY, 100, 100.0, charges=0.0))
    pf.apply_fill(_fill(Side.BUY, 100, 120.0, charges=0.0))
    pos = pf.positions[1]
    assert pos.quantity == 200
    assert pos.entry_price == pytest.approx(110.0)


def test_short_then_cover_profits_when_price_falls() -> None:
    pf = Portfolio()
    pf.apply_fill(_fill(Side.SELL, 50, 100.0, charges=0.0))
    pf.apply_fill(_fill(Side.BUY, 50, 90.0, charges=0.0))
    assert pf.realized_pnl == pytest.approx(500.0)
    assert pf.open_position_count() == 0


def test_flip_past_flat_opens_remainder() -> None:
    pf = Portfolio()
    pf.apply_fill(_fill(Side.BUY, 100, 100.0, charges=0.0))
    pf.apply_fill(_fill(Side.SELL, 150, 110.0, charges=0.0))  # close 100, open 50 short
    pos = pf.positions[1]
    assert pos.direction is Side.SELL
    assert pos.quantity == 50
    assert pf.realized_pnl == pytest.approx(1000.0)  # 100 * (110 - 100)


def test_unrealized_and_day_pnl() -> None:
    pf = Portfolio()
    pf.apply_fill(_fill(Side.BUY, 100, 100.0, charges=10.0))
    assert pf.unrealized_pnl({1: 105.0}) == pytest.approx(500.0)
    assert pf.day_pnl({1: 105.0}) == pytest.approx(500.0 - 10.0)


def test_non_filled_orders_are_ignored() -> None:
    pf = Portfolio()
    rejected = Fill(Order(1, Side.BUY, 10), OrderStatus.REJECTED, 0.0, 0, NOW, 0.0)
    pf.apply_fill(rejected)
    assert pf.open_position_count() == 0
    assert pf.realized_pnl == 0.0
