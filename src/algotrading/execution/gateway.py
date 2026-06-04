"""Order execution gateways.

A single :class:`OrderGateway` interface keeps the paper/live boundary clean:
the engine talks only to this interface, so switching from paper to live is a
config change, not a rewrite. Per the project's hard constraints, only
:class:`LiveGateway` ever touches real order endpoints — and it stays stubbed
(raises ``NotImplementedError``) until explicitly enabled.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from algotrading.backtest.costs import CostConfig, Product, charges_for_fill
from algotrading.strategies.base import Side


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(StrEnum):
    FILLED = "FILLED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class Order:
    """An order request handed to a gateway.

    ``reference_price`` is the current/last market price, used by the paper
    gateway to simulate a fill (the live gateway would ignore it).
    """

    instrument_token: int
    side: Side
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    reference_price: float | None = None
    product: Product = Product.INTRADAY
    tag: str = ""
    reason: str = ""


@dataclass(frozen=True)
class Fill:
    """The outcome of placing an order."""

    order: Order
    status: OrderStatus
    fill_price: float
    quantity: int
    time: datetime
    charges: float
    message: str = ""


class OrderGateway(ABC):
    """Abstract order execution interface."""

    @abstractmethod
    def place_order(self, order: Order, *, now: datetime | None = None) -> Fill:
        """Place ``order`` and return the resulting :class:`Fill`."""


class PaperGateway(OrderGateway):
    """Simulates fills against the last/reference price — no real orders."""

    def __init__(self, slippage_bps: float = 1.0, cost_config: CostConfig | None = None) -> None:
        self.slippage_bps = slippage_bps
        self.cost_config = cost_config or CostConfig()

    def _slip(self, price: float, side: Side) -> float:
        factor = self.slippage_bps / 10_000.0
        return price * (1 + factor) if side is Side.BUY else price * (1 - factor)

    def place_order(self, order: Order, *, now: datetime | None = None) -> Fill:
        when = now or datetime.now(UTC)

        if order.order_type is OrderType.MARKET:
            if order.reference_price is None:
                return self._rejected(order, when, "no reference price for market order")
            fill_price = self._slip(order.reference_price, order.side)
            return self._filled(order, when, fill_price)

        # LIMIT: fill only if the reference price has reached the limit.
        if order.limit_price is None:
            return self._rejected(order, when, "limit order without limit price")
        ref = order.reference_price
        crossed = ref is not None and (
            (order.side is Side.BUY and ref <= order.limit_price)
            or (order.side is Side.SELL and ref >= order.limit_price)
        )
        if not crossed:
            return Fill(order, OrderStatus.PENDING, 0.0, 0, when, 0.0, "limit not reached")
        return self._filled(order, when, order.limit_price)

    def _filled(self, order: Order, when: datetime, fill_price: float) -> Fill:
        charges = charges_for_fill(
            order.side, fill_price, order.quantity, order.product, self.cost_config
        ).total
        return Fill(order, OrderStatus.FILLED, fill_price, order.quantity, when, charges)

    def _rejected(self, order: Order, when: datetime, message: str) -> Fill:
        return Fill(order, OrderStatus.REJECTED, 0.0, 0, when, 0.0, message)


class LiveGateway(OrderGateway):
    """Real order execution — intentionally disabled.

    Live trading requires a registered static IP and an explicit opt-in, and is
    out of scope for this phase. This stub guarantees no real order can be sent.
    """

    def place_order(self, order: Order, *, now: datetime | None = None) -> Fill:
        raise NotImplementedError(
            "Live order execution is disabled. Enable only with a registered "
            "static IP and an explicit, reviewed opt-in."
        )
