"""Tests for benchmark-relative metrics (alpha/beta/information ratio)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from algotrading.backtest.metrics import (
    alpha,
    beta,
    compare_to_benchmark,
    information_ratio,
)
from algotrading.backtest.simulator import BacktestResult


def test_beta_of_double_exposure_is_two() -> None:
    bench = [0.01, -0.02, 0.03, -0.01]
    strat = [2 * x for x in bench]
    assert beta(strat, bench) == pytest.approx(2.0)


def test_beta_zero_when_benchmark_constant() -> None:
    assert beta([0.01, 0.02, 0.03], [0.01, 0.01, 0.01]) == 0.0


def test_alpha_captures_constant_outperformance() -> None:
    bench = [0.01, -0.02, 0.03, -0.01]
    strat = [x + 0.001 for x in bench]  # beta 1, +0.1%/day alpha
    assert beta(strat, bench) == pytest.approx(1.0)
    assert alpha(strat, bench, periods_per_year=252) == pytest.approx(0.001 * 252)


def test_information_ratio_zero_without_active_variation() -> None:
    bench = [0.01, -0.02, 0.03]
    assert information_ratio(bench, bench) == 0.0  # zero active return -> 0


def test_information_ratio_positive_when_outperforming_with_variation() -> None:
    bench = [0.01, 0.0, 0.01, 0.0]
    strat = [0.02, 0.0, 0.03, 0.01]
    assert information_ratio(strat, bench) > 0


def _curve(values: list[float]) -> list[tuple[datetime, float]]:
    start = datetime(2026, 1, 1)
    return [(start + timedelta(days=i), v) for i, v in enumerate(values)]


def test_compare_to_benchmark_aligns_and_correlates() -> None:
    result = BacktestResult(
        trades=[],
        equity_curve=_curve([100, 110, 104.5, 112.86]),  # +10, -5, +8 %
        initial_capital=100.0,
        final_equity=112.86,
    )
    benchmark = _curve([200, 210, 205.8, 214.03])  # +5, -2, +4 %
    stats = compare_to_benchmark(result, benchmark)

    assert stats.beta > 0
    assert 0 < stats.correlation <= 1.0
    assert isinstance(stats.alpha, float)


def test_compare_to_benchmark_uses_common_dates_only() -> None:
    result = BacktestResult(
        trades=[],
        equity_curve=_curve([100, 110, 121]),
        initial_capital=100.0,
        final_equity=121.0,
    )
    # Benchmark shorter / offset; only overlapping dates are used.
    benchmark = _curve([50, 52])
    stats = compare_to_benchmark(result, benchmark)
    assert isinstance(stats.beta, float)  # no crash on partial overlap
