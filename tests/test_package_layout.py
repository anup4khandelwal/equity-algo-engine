"""Verify the Phase 0 package skeleton imports cleanly."""

from __future__ import annotations

import importlib

import pytest

SUBPACKAGES = [
    "algotrading",
    "algotrading.broker",
    "algotrading.data",
    "algotrading.strategies",
    "algotrading.backtest",
    "algotrading.execution",
    "algotrading.risk",
    "algotrading.engine",
]


@pytest.mark.parametrize("module", SUBPACKAGES)
def test_importable(module: str) -> None:
    assert importlib.import_module(module) is not None


def test_version() -> None:
    import algotrading

    assert algotrading.__version__ == "0.1.0"
