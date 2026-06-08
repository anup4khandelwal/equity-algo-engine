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
from .portfolio import Portfolio

__all__ = [
    "Fill",
    "FillEvent",
    "LiveGateway",
    "Order",
    "OrderGateway",
    "OrderStatus",
    "OrderType",
    "PaperGateway",
    "Portfolio",
    "RoundTrip",
    "StrategyPnl",
    "event_from_fill",
    "event_from_record",
    "pnl_by_strategy",
    "round_trips",
]
