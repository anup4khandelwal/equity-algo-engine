"""Read-only FastAPI dashboard.

Thin layer over ``service.py``: each endpoint returns a read-model view of the
current :class:`DashboardState`. The dashboard never mutates state and never
places orders — it is for monitoring only.
"""

from __future__ import annotations

from fastapi import FastAPI

from .service import (
    DashboardState,
    equity_curve_view,
    pnl_summary,
    positions_view,
    strategy_attribution,
    trades_view,
)


def create_app(state: DashboardState) -> FastAPI:
    """Build the dashboard app bound to a live :class:`DashboardState`."""
    app = FastAPI(title="equity-algo-engine dashboard", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/positions")
    def positions() -> list[dict]:
        return positions_view(state)

    @app.get("/pnl")
    def pnl() -> dict:
        return pnl_summary(state)

    @app.get("/trades")
    def trades() -> list[dict]:
        return trades_view(state)

    @app.get("/equity")
    def equity() -> list[dict]:
        return equity_curve_view(state)

    @app.get("/attribution")
    def attribution() -> list[dict]:
        return strategy_attribution(state)

    return app
