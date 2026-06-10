"""Tests for the dashboard service (read-model) layer."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from algotrading.api.service import (
    DashboardState,
    equity_curve_view,
    pnl_summary,
    positions_view,
    strategy_attribution,
    trades_view,
)
from algotrading.execution.gateway import Fill, Order, OrderStatus
from algotrading.execution.portfolio import Portfolio
from algotrading.strategies.base import Position, Side

NOW = datetime(2026, 6, 3, 9, 30, tzinfo=UTC)


def _fill(side: Side, qty: int, price: float, charges: float, tag: str) -> Fill:
    return Fill(
        Order(1, side, qty, reference_price=price, tag=tag),
        OrderStatus.FILLED,
        price,
        qty,
        NOW,
        charges,
    )


def _state() -> DashboardState:
    pf = Portfolio(
        positions={1: Position(Side.BUY, 100, 100.0, NOW)},
        realized_pnl=250.0,
        total_charges=30.0,
    )
    fills = [
        _fill(Side.BUY, 100, 100.0, 10.0, "orb"),
        _fill(Side.SELL, 100, 110.0, 12.0, "orb"),
        _fill(Side.BUY, 50, 200.0, 8.0, "momentum"),
    ]
    return DashboardState(
        portfolio=pf,
        fills=fills,
        equity_curve=[(NOW, 100_250.0)],
        last_prices={1: 105.0},
    )


def test_positions_view_includes_unrealized() -> None:
    rows = positions_view(_state())
    assert rows[0]["instrument_token"] == 1
    assert rows[0]["unrealized_pnl"] == pytest.approx((105.0 - 100.0) * 100)


def test_pnl_summary() -> None:
    summary = pnl_summary(_state())
    assert summary["realized_pnl"] == pytest.approx(250.0)
    assert summary["unrealized_pnl"] == pytest.approx(500.0)
    assert summary["total_pnl"] == pytest.approx(750.0)
    assert summary["open_positions"] == 1


def test_trades_view_shapes_fills() -> None:
    rows = trades_view(_state())
    assert len(rows) == 3
    assert rows[0]["strategy"] == "orb"
    assert rows[2]["side"] == "BUY"


def test_equity_curve_view() -> None:
    rows = equity_curve_view(_state())
    assert rows == [{"time": NOW.isoformat(), "equity": 100_250.0}]


def test_closed_trades_view_reconstructs_round_trips() -> None:
    from algotrading.api.service import closed_trades_view

    rows = closed_trades_view(_state())
    # _state has an ORB buy then sell of 100 -> one completed long round trip.
    assert len(rows) == 1
    assert rows[0]["direction"] == "BUY"
    assert rows[0]["quantity"] == 100
    assert rows[0]["net_pnl"] == pytest.approx((110.0 - 100.0) * 100 - (10.0 + 12.0))


def test_strategy_pnl_view_realised_per_strategy() -> None:
    from algotrading.api.service import strategy_pnl_view

    rows = strategy_pnl_view(_state())
    # _state: one completed orb round trip (+978 net); momentum buy is still open.
    by = {r["strategy"]: r for r in rows}
    assert "orb" in by
    assert by["orb"]["trades"] == 1
    assert by["orb"]["net_pnl"] == pytest.approx((110.0 - 100.0) * 100 - 22.0)
    assert "momentum" not in by  # open position -> no realised round trip


def test_strategy_attribution_groups_by_tag() -> None:
    attr = {row["strategy"]: row for row in strategy_attribution(_state())}
    assert attr["orb"]["fills"] == 2
    assert attr["orb"]["quantity"] == 200
    assert attr["orb"]["charges"] == pytest.approx(22.0)
    assert attr["momentum"]["fills"] == 1


def test_candles_and_regime_views() -> None:
    from datetime import timedelta

    from algotrading.api.service import DashboardState, candles_view, regime_view
    from algotrading.strategies.base import Bar

    start = NOW
    bars = [
        Bar(1, start + timedelta(days=i), 100 + 2 * i, 101 + 2 * i, 99 + 2 * i, 100 + 2 * i)
        for i in range(40)  # strong uptrend -> TRENDING
    ] + [Bar(2, start, 50, 51, 49, 50)]
    state = DashboardState(portfolio=Portfolio(), bars=bars)

    candles = candles_view(state, instrument_token=1)
    assert len(candles) == 40
    assert candles[0]["open"] == 100 and candles[-1]["close"] == 100 + 2 * 39
    assert candles_view(state)[0]["instrument_token"] in (1, 2)  # unfiltered includes both

    regimes = {r["instrument_token"]: r for r in regime_view(state)}
    assert regimes[1]["regime"] == "TRENDING" and regimes[1]["adx"] > 25
    assert regimes[2]["regime"] == "UNKNOWN"  # one bar -> warm-up
