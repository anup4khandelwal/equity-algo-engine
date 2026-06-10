"""Read-only dashboard (Phase 6).

Only the framework-agnostic service layer is exported here; import
``algotrading.api.app`` explicitly to build the FastAPI app (requires the
``api`` extra).
"""

from .service import (
    DashboardState,
    candles_view,
    closed_trades_view,
    equity_curve_view,
    pnl_summary,
    positions_view,
    regime_view,
    strategy_attribution,
    strategy_pnl_view,
    trades_view,
)

__all__ = [
    "DashboardState",
    "candles_view",
    "closed_trades_view",
    "equity_curve_view",
    "pnl_summary",
    "positions_view",
    "regime_view",
    "strategy_attribution",
    "strategy_pnl_view",
    "trades_view",
]
