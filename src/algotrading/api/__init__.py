"""Read-only dashboard (Phase 6).

Only the framework-agnostic service layer is exported here; import
``algotrading.api.app`` explicitly to build the FastAPI app (requires the
``api`` extra).
"""

from .service import (
    DashboardState,
    equity_curve_view,
    pnl_summary,
    positions_view,
    strategy_attribution,
    trades_view,
)

__all__ = [
    "DashboardState",
    "equity_curve_view",
    "pnl_summary",
    "positions_view",
    "strategy_attribution",
    "trades_view",
]
