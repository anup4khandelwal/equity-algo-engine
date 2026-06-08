"""Tests for the HTML backtest report."""

from __future__ import annotations

from datetime import datetime, timedelta

from algotrading.backtest.metrics import compute_metrics
from algotrading.backtest.report import _equity_svg, render_html
from algotrading.backtest.simulator import BacktestResult


def _curve(values: list[float]) -> list[tuple[datetime, float]]:
    start = datetime(2026, 1, 1)
    return [(start + timedelta(days=i), v) for i, v in enumerate(values)]


def test_equity_svg_renders_polyline() -> None:
    svg = _equity_svg(_curve([100, 110, 105, 120]))
    assert "<svg" in svg and "<polyline" in svg
    assert svg.count(",") >= 3  # one coord pair per point


def test_equity_svg_handles_too_few_points() -> None:
    assert "No equity data" in _equity_svg(_curve([100]))


def test_render_html_is_self_contained() -> None:
    result = BacktestResult(
        trades=[],
        equity_curve=_curve([100_000, 101_000, 100_500, 102_000]),
        initial_capital=100_000.0,
        final_equity=102_000.0,
    )
    metrics = compute_metrics(result)
    out = render_html(metrics, result.equity_curve, title="My <Report>")

    assert out.startswith("<!doctype html>")
    assert "</html>" in out
    assert "<svg" in out  # inline chart, no external assets
    assert "Net P&amp;L" in out  # metrics table rendered (HTML-escaped)
    assert "My &lt;Report&gt;" in out  # title escaped
    assert "http://" not in out and "https://" not in out  # nothing external
