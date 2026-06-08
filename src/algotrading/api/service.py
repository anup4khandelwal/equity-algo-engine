"""Read-only dashboard read-models.

Pure functions that turn engine/portfolio state into JSON-serialisable views.
No web framework here, so this is fully unit-testable; ``app.py`` is a thin
FastAPI layer over these.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from algotrading.execution.gateway import Fill
from algotrading.execution.portfolio import Portfolio

if TYPE_CHECKING:
    from algotrading.engine import PaperTradingEngine


@dataclass
class DashboardState:
    """Everything the dashboard needs, decoupled from the live engine."""

    portfolio: Portfolio
    fills: list[Fill] = field(default_factory=list)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)
    last_prices: dict[int, float] = field(default_factory=dict)

    @classmethod
    def from_engine(cls, engine: PaperTradingEngine) -> DashboardState:
        return cls(
            portfolio=engine.portfolio,
            fills=engine.trade_log.fills,
            equity_curve=engine.equity_curve,
            last_prices=engine.last_prices,
        )


def positions_view(state: DashboardState) -> list[dict[str, Any]]:
    rows = []
    for token, pos in state.portfolio.positions.items():
        price = state.last_prices.get(token)
        unrealized = (
            pos.sign * (price - pos.entry_price) * pos.quantity if price is not None else None
        )
        rows.append(
            {
                "instrument_token": token,
                "direction": pos.direction.value,
                "quantity": pos.quantity,
                "entry_price": pos.entry_price,
                "last_price": price,
                "unrealized_pnl": unrealized,
            }
        )
    return rows


def pnl_summary(state: DashboardState) -> dict[str, float]:
    unrealized = state.portfolio.unrealized_pnl(state.last_prices)
    realized = state.portfolio.realized_pnl
    return {
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "total_pnl": realized + unrealized,
        "total_charges": state.portfolio.total_charges,
        "open_positions": state.portfolio.open_position_count(),
    }


def trades_view(state: DashboardState) -> list[dict[str, Any]]:
    return [
        {
            "time": fill.time.isoformat(),
            "instrument_token": fill.order.instrument_token,
            "side": fill.order.side.value,
            "quantity": fill.quantity,
            "fill_price": fill.fill_price,
            "charges": fill.charges,
            "strategy": fill.order.tag,
            "reason": fill.order.reason,
        }
        for fill in state.fills
    ]


def equity_curve_view(state: DashboardState) -> list[dict[str, Any]]:
    return [{"time": ts.isoformat(), "equity": equity} for ts, equity in state.equity_curve]


def closed_trades_view(state: DashboardState) -> list[dict[str, Any]]:
    """Completed round-trip trades reconstructed from the fill history."""
    from algotrading.execution.analytics import event_from_fill, round_trips

    trips = round_trips([event_from_fill(f) for f in state.fills])
    return [
        {
            "instrument_token": t.instrument_token,
            "strategy": t.strategy,
            "direction": t.direction,
            "quantity": t.quantity,
            "entry_time": t.entry_time.isoformat(),
            "entry_price": t.entry_price,
            "exit_time": t.exit_time.isoformat(),
            "exit_price": t.exit_price,
            "gross_pnl": t.gross_pnl,
            "charges": t.charges,
            "net_pnl": t.net_pnl,
            "holding_seconds": t.holding_seconds,
        }
        for t in trips
    ]


def strategy_pnl_view(state: DashboardState) -> list[dict[str, Any]]:
    """Per-strategy realised P&L from completed round trips."""
    from algotrading.execution.analytics import (
        event_from_fill,
        pnl_by_strategy,
        round_trips,
    )

    trips = round_trips([event_from_fill(f) for f in state.fills])
    return [
        {
            "strategy": s.strategy,
            "trades": s.trades,
            "net_pnl": s.net_pnl,
            "gross_pnl": s.gross_pnl,
            "charges": s.charges,
            "win_rate": s.win_rate,
        }
        for s in pnl_by_strategy(trips)
    ]


def strategy_attribution(state: DashboardState) -> list[dict[str, Any]]:
    """Per-strategy (order tag) activity and cost summary."""
    groups: dict[str, dict[str, float]] = {}
    for fill in state.fills:
        tag = fill.order.tag or "unknown"
        g = groups.setdefault(tag, {"fills": 0, "quantity": 0, "charges": 0.0, "traded_value": 0.0})
        g["fills"] += 1
        g["quantity"] += fill.quantity
        g["charges"] += fill.charges
        g["traded_value"] += fill.fill_price * fill.quantity
    return [{"strategy": tag, **stats} for tag, stats in sorted(groups.items())]
