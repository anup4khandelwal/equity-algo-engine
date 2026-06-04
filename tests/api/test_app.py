"""Tests for the FastAPI dashboard app.

Skipped when FastAPI isn't installed (it lives in the optional `api` extra; CI
installs it via --all-extras). We avoid an httpx dependency by calling the route
handlers directly rather than through a TestClient.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytest.importorskip("fastapi")

from algotrading.api.app import create_app  # noqa: E402
from algotrading.api.service import DashboardState  # noqa: E402
from algotrading.execution.portfolio import Portfolio  # noqa: E402
from algotrading.strategies.base import Position, Side  # noqa: E402

NOW = datetime(2026, 6, 3, 9, 30, tzinfo=UTC)


def _state() -> DashboardState:
    pf = Portfolio(positions={1: Position(Side.BUY, 10, 100.0, NOW)}, realized_pnl=5.0)
    return DashboardState(portfolio=pf, last_prices={1: 101.0})


def _handlers(app):
    return {route.path: route.endpoint for route in app.routes if hasattr(route, "endpoint")}


def test_expected_routes_registered() -> None:
    app = create_app(_state())
    paths = {route.path for route in app.routes}
    for expected in ("/health", "/positions", "/pnl", "/trades", "/equity", "/attribution"):
        assert expected in paths


def test_health_handler() -> None:
    handlers = _handlers(create_app(_state()))
    assert handlers["/health"]() == {"status": "ok"}


def test_positions_and_pnl_handlers_return_state() -> None:
    handlers = _handlers(create_app(_state()))
    positions = handlers["/positions"]()
    assert positions[0]["instrument_token"] == 1
    assert handlers["/pnl"]()["open_positions"] == 1
