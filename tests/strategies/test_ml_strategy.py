"""Tests for the ML-driven strategy and its Scorer protocol."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from algotrading.strategies.base import Bar, Side, SignalType
from algotrading.strategies.features import FeatureExtractor
from algotrading.strategies.ml_strategy import MLStrategy, Scorer

TOKEN = 7
T0 = datetime(2026, 1, 1, 9, 15)


def _bar(i: int, close: float = 100.0) -> Bar:
    return Bar(TOKEN, T0 + timedelta(minutes=i), close, close * 1.001, close * 0.999, close)


class FixedScorer:
    """Returns a constant probability — exercises threshold logic deterministically."""

    def __init__(self, proba: float) -> None:
        self._proba = proba

    def predict_proba_one(self, features: list[float]) -> float:
        return self._proba


def _run(strategy: MLStrategy, n: int):
    return [strategy.on_bar(_bar(i, 100.0 + i)) for i in range(n)]


def test_fixed_scorer_satisfies_protocol() -> None:
    assert isinstance(FixedScorer(0.6), Scorer)


def test_no_signals_during_warmup() -> None:
    strat = MLStrategy(TOKEN, FixedScorer(0.99))
    warmup = strat.extractor.warmup
    signals = _run(strat, warmup - 1)
    assert all(s is None for s in signals)


def test_high_proba_enters_long_then_holds() -> None:
    strat = MLStrategy(TOKEN, FixedScorer(0.9), entry_threshold=0.55, exit_threshold=0.45)
    signals = [s for s in _run(strat, strat.extractor.warmup + 10) if s is not None]
    assert len(signals) == 1
    entry = signals[0]
    assert entry.type is SignalType.ENTRY
    assert entry.side is Side.BUY
    assert strat._long is True


def test_low_proba_never_enters() -> None:
    strat = MLStrategy(TOKEN, FixedScorer(0.1))
    signals = [s for s in _run(strat, strat.extractor.warmup + 10) if s is not None]
    assert signals == []


def test_entry_then_exit_on_dropping_proba() -> None:
    class StepScorer:
        """High until called `flip` times, then low — forces an entry then an exit."""

        def __init__(self, flip: int) -> None:
            self.calls = 0
            self.flip = flip

        def predict_proba_one(self, features: list[float]) -> float:
            self.calls += 1
            return 0.9 if self.calls <= self.flip else 0.1

    strat = MLStrategy(TOKEN, StepScorer(flip=2))
    signals = [s for s in _run(strat, strat.extractor.warmup + 12) if s is not None]
    assert [s.type for s in signals] == [SignalType.ENTRY, SignalType.EXIT]
    assert signals[0].side is Side.BUY
    assert signals[1].side is Side.SELL
    assert strat._long is False


def test_reset_clears_state() -> None:
    strat = MLStrategy(TOKEN, FixedScorer(0.9))
    _run(strat, strat.extractor.warmup + 5)
    assert strat._long is True
    strat.reset()
    assert strat._long is False
    assert strat.last_proba is None
    assert strat.extractor._bars == []


def test_invalid_thresholds_rejected() -> None:
    with pytest.raises(ValueError):
        MLStrategy(TOKEN, FixedScorer(0.5), entry_threshold=0.4, exit_threshold=0.6)


def test_custom_extractor_is_used() -> None:
    ex = FeatureExtractor(rsi_period=5, sma_period=5, vol_period=5, adx_period=5)
    strat = MLStrategy(TOKEN, FixedScorer(0.9), extractor=ex)
    assert strat.extractor is ex
