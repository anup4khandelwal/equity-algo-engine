"""Lightweight, dependency-free ML signal layer (NumPy only).

This is infrastructure for *finding* edge, not edge itself: a deterministic
feature pipeline (:mod:`algotrading.strategies.features`), a from-scratch
logistic-regression scorer (:class:`LogisticRegression`) with feature scaling
(:class:`StandardScaler`), and a labelling helper (:func:`build_dataset`) that
turns a bar stream into a supervised (X, y) matrix. The trained model plugs into
a strategy via the ``Scorer`` protocol in
:mod:`algotrading.strategies.ml_strategy`, so strategy code never imports NumPy.

No scikit-learn — everything here is small, auditable, and reproducible, which
matters more than convenience for a personal trading system.
"""

from .dataset import build_dataset
from .model import LogisticRegression, StandardScaler

__all__ = [
    "LogisticRegression",
    "StandardScaler",
    "build_dataset",
]
