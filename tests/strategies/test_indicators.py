"""Tests for the pure indicators."""

from __future__ import annotations

import pytest

from algotrading.strategies.indicators import rsi, sma


def test_sma() -> None:
    assert sma([1, 2, 3, 4, 5], 3) == pytest.approx(4.0)  # mean of 3,4,5


def test_rsi_all_gains_is_100() -> None:
    assert rsi([1, 2, 3, 4, 5], 4) == 100.0


def test_rsi_all_losses_is_zero() -> None:
    assert rsi([5, 4, 3, 2, 1], 4) == pytest.approx(0.0)


def test_rsi_balanced_is_fifty() -> None:
    # Equal up/down moves of the same size -> RSI 50.
    assert rsi([10, 11, 10, 11, 10], 4) == pytest.approx(50.0)
