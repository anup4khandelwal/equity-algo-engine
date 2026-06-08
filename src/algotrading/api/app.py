"""Read-only FastAPI dashboard.

Thin layer over ``service.py``: each endpoint returns a read-model view of the
current :class:`DashboardState`. The dashboard never mutates state and never
places orders — it is for monitoring only.
"""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .service import (
    DashboardState,
    closed_trades_view,
    equity_curve_view,
    pnl_summary,
    positions_view,
    strategy_attribution,
    strategy_pnl_view,
    trades_view,
)


def create_app(
    state: DashboardState,
    *,
    cors_origins: Sequence[str] | None = None,
) -> FastAPI:
    """Build the dashboard app bound to a live :class:`DashboardState`.

    ``cors_origins`` allows the Next.js frontend (default http://localhost:3000)
    to call the API from the browser. The dashboard is read-only, so permissive
    CORS for a local, personal tool is acceptable.
    """
    app = FastAPI(title="equity-algo-engine dashboard", version="0.1.0")

    origins = (
        list(cors_origins)
        if cors_origins is not None
        else [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

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

    @app.get("/closed-trades")
    def closed_trades() -> list[dict]:
        return closed_trades_view(state)

    @app.get("/equity")
    def equity() -> list[dict]:
        return equity_curve_view(state)

    @app.get("/attribution")
    def attribution() -> list[dict]:
        return strategy_attribution(state)

    @app.get("/strategy-pnl")
    def strategy_pnl() -> list[dict]:
        return strategy_pnl_view(state)

    return app
