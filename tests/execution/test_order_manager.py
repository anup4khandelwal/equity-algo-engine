"""Tests for the async live order manager."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from algotrading.backtest.costs import charges_for_fill
from algotrading.execution.gateway import Order, OrderStatus
from algotrading.execution.order_manager import OrderManager, OrderState, OrderUpdate
from algotrading.strategies.base import Side

T0 = datetime(2026, 6, 3, 9, 30, tzinfo=UTC)


def _order(side: Side = Side.BUY, qty: int = 100) -> Order:
    return Order(instrument_token=1, side=side, quantity=qty, tag="orb")


def _update(oid: str, status: OrderState, filled: int, avg: float, minute: int = 0) -> OrderUpdate:
    return OrderUpdate(oid, status, filled, avg, T0.replace(minute=30 + minute))


def test_single_full_fill_emits_one_fill() -> None:
    mgr = OrderManager()
    mgr.register("o1", _order(qty=100))
    fill = mgr.on_update(_update("o1", OrderState.COMPLETE, 100, 101.0))

    assert fill is not None
    assert fill.status is OrderStatus.FILLED
    assert fill.quantity == 100
    assert fill.fill_price == pytest.approx(101.0)
    assert mgr.state("o1") is OrderState.COMPLETE
    assert mgr.open_order_ids() == []


def test_partial_then_complete_prices_each_leg() -> None:
    mgr = OrderManager()
    mgr.register("o1", _order(qty=100))

    f1 = mgr.on_update(_update("o1", OrderState.PARTIAL, 40, 100.0, minute=0))
    assert f1 is not None and f1.quantity == 40 and f1.fill_price == pytest.approx(100.0)
    assert "o1" in mgr.open_order_ids()  # still working

    # cumulative avg 102 over 100 -> the new 60 leg must price at 103.333…
    f2 = mgr.on_update(_update("o1", OrderState.COMPLETE, 100, 102.0, minute=1))
    assert f2 is not None and f2.quantity == 60
    assert f2.fill_price == pytest.approx((100 * 102 - 40 * 100) / 60)
    assert mgr.open_order_ids() == []


def test_no_new_fill_returns_none() -> None:
    mgr = OrderManager()
    mgr.register("o1", _order())
    assert mgr.on_update(_update("o1", OrderState.OPEN, 0, 0.0)) is None  # ack
    mgr.on_update(_update("o1", OrderState.COMPLETE, 100, 100.0))
    # A duplicate terminal update with no new qty -> no second fill.
    assert mgr.on_update(_update("o1", OrderState.COMPLETE, 100, 100.0)) is None


def test_rejected_and_unknown_orders() -> None:
    mgr = OrderManager()
    mgr.register("o1", _order())
    assert mgr.on_update(_update("o1", OrderState.REJECTED, 0, 0.0)) is None
    assert mgr.state("o1") is OrderState.REJECTED
    assert mgr.open_order_ids() == []
    # Update for an order we never registered is ignored.
    assert mgr.on_update(_update("ghost", OrderState.COMPLETE, 10, 100.0)) is None


def test_dedup_guard_blocks_double_submit() -> None:
    mgr = OrderManager()
    assert mgr.register("o1", _order(), dedup_key="entry-INFY-0930") is True
    assert mgr.register("o2", _order(), dedup_key="entry-INFY-0930") is False
    assert "o2" not in mgr.open_order_ids()


def test_net_positions_sum_signed_fills() -> None:
    mgr = OrderManager()
    mgr.register("buy", _order(Side.BUY, 100))
    mgr.register("sell", _order(Side.SELL, 30))
    mgr.on_update(_update("buy", OrderState.COMPLETE, 100, 100.0))
    mgr.on_update(_update("sell", OrderState.COMPLETE, 30, 105.0))
    assert mgr.net_positions() == {1: 70}


def test_charge_fn_estimates_costs() -> None:
    mgr = OrderManager(charge_fn=lambda s, p, q, pr: charges_for_fill(s, p, q, pr).total)
    mgr.register("o1", _order(Side.BUY, 100))
    fill = mgr.on_update(_update("o1", OrderState.COMPLETE, 100, 1000.0))
    assert fill is not None and fill.charges > 0
