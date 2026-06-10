"""A strategy driven by a learned probability score.

:class:`MLStrategy` runs the streaming :class:`FeatureExtractor` over each bar and
asks a ``Scorer`` for P(up-move). It goes long when that probability clears
``entry_threshold`` and flattens when it falls back below ``exit_threshold``,
giving a clean hysteresis band so a borderline score doesn't churn the book.

The ``Scorer`` is a tiny Protocol (``predict_proba_one(features) -> float``), so
this module — and every other strategy — stays NumPy-free; only the fitted
:class:`~algotrading.ml.model.LogisticRegression` carries the dependency. That
means an MLStrategy slots into the :class:`EnsembleStrategy` as just another
:class:`Member`, backtesting and paper-trading through the same engines.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .base import Bar, Side, Signal, SignalType, Strategy
from .features import FeatureExtractor


@runtime_checkable
class Scorer(Protocol):
    """Anything that turns a feature vector into a probability in [0, 1]."""

    def predict_proba_one(self, features: list[float]) -> float: ...


class MLStrategy(Strategy):
    name = "ml"

    def __init__(
        self,
        instrument_token: int,
        scorer: Scorer,
        *,
        extractor: FeatureExtractor | None = None,
        entry_threshold: float = 0.55,
        exit_threshold: float = 0.45,
    ) -> None:
        if not 0.0 < exit_threshold <= entry_threshold < 1.0:
            raise ValueError("require 0 < exit_threshold <= entry_threshold < 1")
        self.instrument_token = instrument_token
        self.scorer = scorer
        self.extractor = extractor or FeatureExtractor()
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.reset()

    def reset(self) -> None:
        self.extractor.reset()
        self._long = False
        self.last_proba: float | None = None

    def generate_signal(self, bar: Bar) -> Signal | None:
        features = self.extractor.update(bar)
        if features is None:
            return None  # still warming up
        proba = self.scorer.predict_proba_one(self.extractor.vector(features))
        self.last_proba = proba

        if not self._long:
            if proba >= self.entry_threshold:
                self._long = True
                return Signal(
                    bar.time,
                    self.instrument_token,
                    SignalType.ENTRY,
                    Side.BUY,
                    bar.close,
                    f"ml_long({proba:.2f})",
                )
            return None

        if proba < self.exit_threshold:
            self._long = False
            return Signal(
                bar.time,
                self.instrument_token,
                SignalType.EXIT,
                Side.SELL,
                bar.close,
                f"ml_exit({proba:.2f})",
            )
        return None
