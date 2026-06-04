"""Tests for cross-sectional momentum ranking."""

from __future__ import annotations

import pytest

from algotrading.strategies.cross_sectional import momentum_scores, select_top


def test_momentum_scores_only_for_sufficient_history() -> None:
    history = {1: [100, 110, 120], 2: [100]}  # token 2 too short for lookback 2
    scores = momentum_scores(history, lookback=2)
    assert set(scores) == {1}
    assert scores[1] == pytest.approx((120 - 100) / 100)


def test_select_top_ranks_and_filters() -> None:
    scores = {1: 0.30, 2: -0.10, 3: 0.50, 4: 0.05}
    # Only positive scores, highest first, capped at top_n.
    assert select_top(scores, top_n=2, min_score=0.0) == [3, 1]


def test_select_top_excludes_below_threshold() -> None:
    scores = {1: 0.01, 2: 0.20}
    assert select_top(scores, top_n=5, min_score=0.05) == [2]


def test_select_top_ties_break_by_token() -> None:
    scores = {5: 0.1, 2: 0.1, 9: 0.1}
    assert select_top(scores, top_n=2) == [2, 5]
