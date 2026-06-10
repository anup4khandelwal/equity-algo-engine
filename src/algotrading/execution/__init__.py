"""OrderGateway interface, PaperGateway, and LiveGateway stub (Phase 4)."""

from .analytics import (
    FillEvent,
    RoundTrip,
    StrategyPnl,
    event_from_fill,
    event_from_record,
    pnl_by_strategy,
    round_trips,
)
from .gateway import (
    Fill,
    LiveGateway,
    Order,
    OrderGateway,
    OrderStatus,
    OrderType,
    PaperGateway,
)
from .order_manager import OrderManager, OrderState, OrderUpdate
from .portfolio import Portfolio
from .reconcile import Discrepancy, internal_positions, reconcile

__all__ = [
    "Discrepancy",
    "Fill",
    "FillEvent",
    "LiveGateway",
    "Order",
    "OrderGateway",
    "OrderManager",
    "OrderState",
    "OrderStatus",
    "OrderType",
    "OrderUpdate",
    "PaperGateway",
    "Portfolio",
    "RoundTrip",
    "StrategyPnl",
    "event_from_fill",
    "event_from_record",
    "internal_positions",
    "pnl_by_strategy",
    "reconcile",
    "round_trips",
]
