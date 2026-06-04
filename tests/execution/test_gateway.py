"""Tests for the execution gateways."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from algotrading.execution.gateway import (
    LiveGateway,
    Order,
    OrderStatus,
    OrderType,
    PaperGateway,
)
from algotrading.strategies.base import Side

NOW = datetime(2026, 6, 3, 9, 30, tzinfo=UTC)


def test_paper_market_buy_fills_with_slippage_and_charges() -> None:
    gw = PaperGateway(slippage_bps=10.0)
    order = Order(1, Side.BUY, 100, reference_price=100.0)
    fill = gw.place_order(order, now=NOW)

    assert fill.status is OrderStatus.FILLED
    assert fill.fill_price == pytest.approx(100.0 * 1.001)  # buy pays up
    assert fill.quantity == 100
    assert fill.charges > 0


def test_paper_market_sell_receives_less() -> None:
    gw = PaperGateway(slippage_bps=10.0)
    fill = gw.place_order(Order(1, Side.SELL, 50, reference_price=200.0), now=NOW)
    assert fill.fill_price == pytest.approx(200.0 * 0.999)


def test_paper_market_without_reference_is_rejected() -> None:
    fill = PaperGateway().place_order(Order(1, Side.BUY, 10), now=NOW)
    assert fill.status is OrderStatus.REJECTED
    assert fill.charges == 0.0


def test_paper_limit_buy_pending_until_crossed() -> None:
    gw = PaperGateway(slippage_bps=0.0)
    # Reference above the buy limit -> not reached.
    pending = gw.place_order(
        Order(1, Side.BUY, 10, OrderType.LIMIT, limit_price=99.0, reference_price=100.0),
        now=NOW,
    )
    assert pending.status is OrderStatus.PENDING

    filled = gw.place_order(
        Order(1, Side.BUY, 10, OrderType.LIMIT, limit_price=101.0, reference_price=100.0),
        now=NOW,
    )
    assert filled.status is OrderStatus.FILLED
    assert filled.fill_price == 101.0


def test_live_gateway_is_disabled() -> None:
    with pytest.raises(NotImplementedError):
        LiveGateway().place_order(Order(1, Side.BUY, 1, reference_price=100.0), now=NOW)
