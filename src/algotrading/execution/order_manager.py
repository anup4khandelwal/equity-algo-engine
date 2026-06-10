"""Asynchronous order lifecycle management for live trading.

A real broker (Zerodha Kite) does not fill synchronously: ``place_order`` returns
an *order id*, and fills arrive later as order updates — possibly **partial**,
then ``COMPLETE``, or ``REJECTED``/``CANCELLED``. The :class:`OrderManager`
tracks each order's lifecycle and turns incremental fills into the same
:class:`~algotrading.execution.gateway.Fill` objects the paper path produces, so
everything downstream (Portfolio, analytics, dashboard) is identical.

This module is **broker-agnostic and side-effect free** — it never calls any
API. A future ``LiveGateway`` submits to Kite, calls :meth:`OrderManager.register`
with the returned id, and feeds Kite's order updates into
:meth:`OrderManager.on_update`. No real order is placed here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from .gateway import Fill, Order, OrderStatus

# Charge estimator: (side, price, quantity, product) -> total charges.
ChargeFn = Callable[..., float]


class OrderState(StrEnum):
    """Broker-side order lifecycle states (mirrors Kite)."""

    PENDING = "PENDING"  # submitted, not yet acknowledged
    OPEN = "OPEN"  # acknowledged, resting
    PARTIAL = "PARTIAL"  # partially filled
    COMPLETE = "COMPLETE"  # fully filled
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


_TERMINAL = {OrderState.COMPLETE, OrderState.REJECTED, OrderState.CANCELLED}


@dataclass(frozen=True)
class OrderUpdate:
    """A broker order-update event (one per status change)."""

    order_id: str
    status: OrderState
    filled_quantity: int  # cumulative filled so far
    average_price: float  # cumulative VWAP of the fills
    time: datetime
    message: str = ""


@dataclass
class _Managed:
    order: Order
    state: OrderState
    filled: int = 0
    avg_price: float = 0.0


class OrderManager:
    """Tracks live orders and emits a :class:`Fill` for each incremental fill."""

    def __init__(self, charge_fn: ChargeFn | None = None) -> None:
        self._orders: dict[str, _Managed] = {}
        self._dedup: set = set()
        self._charge_fn = charge_fn

    def register(self, order_id: str, order: Order, *, dedup_key: object | None = None) -> bool:
        """Track a submitted order. Returns ``False`` if ``dedup_key`` was seen.

        The dedup guard prevents a retry/double-click from submitting the same
        logical order twice.
        """
        if dedup_key is not None:
            if dedup_key in self._dedup:
                return False
            self._dedup.add(dedup_key)
        self._orders[order_id] = _Managed(order, OrderState.PENDING)
        return True

    def on_update(self, update: OrderUpdate) -> Fill | None:
        """Process an order update; return a :class:`Fill` for any *new* fill."""
        managed = self._orders.get(update.order_id)
        if managed is None:
            return None  # unknown order — ignore

        managed.state = update.status
        new_qty = update.filled_quantity - managed.filled
        if new_qty <= 0:
            return None  # status change with no new fill (ack / reject / cancel)

        # Marginal price of just this leg, backed out of the cumulative VWAP.
        marginal = (
            update.filled_quantity * update.average_price - managed.filled * managed.avg_price
        ) / new_qty
        managed.filled = update.filled_quantity
        managed.avg_price = update.average_price

        order = managed.order
        charges = (
            self._charge_fn(order.side, marginal, new_qty, order.product)
            if self._charge_fn is not None
            else 0.0
        )
        return Fill(
            order=replace(order, quantity=new_qty),
            status=OrderStatus.FILLED,
            fill_price=marginal,
            quantity=new_qty,
            time=update.time,
            charges=charges,
        )

    def state(self, order_id: str) -> OrderState | None:
        managed = self._orders.get(order_id)
        return managed.state if managed else None

    def open_order_ids(self) -> list[str]:
        """Order ids not yet in a terminal state."""
        return [oid for oid, m in self._orders.items() if m.state not in _TERMINAL]

    def net_positions(self) -> dict[int, int]:
        """Signed net quantity per instrument from filled orders (+ long, - short)."""
        from algotrading.strategies.base import Side

        positions: dict[int, int] = {}
        for managed in self._orders.values():
            if managed.filled <= 0:
                continue
            token = managed.order.instrument_token
            sign = 1 if managed.order.side is Side.BUY else -1
            positions[token] = positions.get(token, 0) + sign * managed.filled
        return {t: q for t, q in positions.items() if q != 0}
