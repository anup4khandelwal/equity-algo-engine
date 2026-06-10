"""Turn a bar stream into a supervised (X, y) dataset for the ML scorer.

Walks bars through a :class:`~algotrading.strategies.features.FeatureExtractor`,
and labels each feature row by what the price does ``horizon`` bars later: 1 if
the forward return clears ``threshold`` (a tradeable up-move), else 0. The
threshold keeps tiny, cost-eaten moves out of the positive class — for Indian
intraday, a move that doesn't beat round-trip charges is not a win.

Rows are emitted only where both a warmed-up feature vector and a full forward
window exist, so X and y stay aligned with no look-ahead.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from algotrading.strategies.base import Bar
from algotrading.strategies.features import FEATURE_NAMES, FeatureExtractor


@dataclass(frozen=True)
class Dataset:
    """Aligned design matrix and labels with their feature names."""

    x: np.ndarray
    y: np.ndarray
    feature_names: tuple[str, ...]

    def __len__(self) -> int:
        return int(self.x.shape[0])


def build_dataset(
    bars: Sequence[Bar],
    *,
    horizon: int = 5,
    threshold: float = 0.0,
    extractor: FeatureExtractor | None = None,
) -> Dataset:
    """Build a forward-return-labelled dataset from ``bars``.

    A row's label is 1 when ``(close[t + horizon] - close[t]) / close[t]`` exceeds
    ``threshold``. Returns empty arrays when there is too little history.
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    extractor = extractor or FeatureExtractor()

    rows: list[list[float]] = []
    labels: list[int] = []
    feature_at: list[tuple[int, list[float]]] = []

    for index, bar in enumerate(bars):
        features = extractor.update(bar)
        if features is not None:
            feature_at.append((index, extractor.vector(features)))

    n = len(bars)
    for index, vector in feature_at:
        future = index + horizon
        if future >= n:
            break
        base = bars[index].close
        if base <= 0:
            continue
        fwd_ret = (bars[future].close - base) / base
        rows.append(vector)
        labels.append(1 if fwd_ret > threshold else 0)

    if not rows:
        empty = np.empty((0, len(FEATURE_NAMES)), dtype=float)
        return Dataset(x=empty, y=np.empty(0, dtype=int), feature_names=FEATURE_NAMES)

    return Dataset(
        x=np.asarray(rows, dtype=float),
        y=np.asarray(labels, dtype=int),
        feature_names=FEATURE_NAMES,
    )
