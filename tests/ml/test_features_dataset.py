"""Tests for the feature extractor and dataset builder."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from algotrading.ml.dataset import build_dataset
from algotrading.strategies.base import Bar
from algotrading.strategies.features import FEATURE_NAMES, FeatureExtractor

TOKEN = 1
T0 = datetime(2026, 1, 1, 9, 15)


def _bar(i: int, close: float) -> Bar:
    # A gentle intrabar range so high/low features are non-degenerate.
    return Bar(TOKEN, T0 + timedelta(minutes=i), close, close * 1.002, close * 0.998, close)


def _trend(n: int) -> list[Bar]:
    return [_bar(i, 100.0 + i) for i in range(n)]


def test_extractor_returns_none_during_warmup() -> None:
    ex = FeatureExtractor()
    out = [ex.update(b) for b in _trend(ex.warmup - 1)]
    assert all(o is None for o in out)


def test_extractor_emits_named_features_after_warmup() -> None:
    ex = FeatureExtractor()
    bars = _trend(ex.warmup + 5)
    feats = None
    for b in bars:
        feats = ex.update(b)
    assert feats is not None
    assert set(feats) == set(FEATURE_NAMES)
    vec = ex.vector(feats)
    assert len(vec) == len(FEATURE_NAMES)
    assert all(isinstance(v, float) for v in vec)


def test_extractor_buffer_is_bounded() -> None:
    ex = FeatureExtractor()
    for b in _trend(ex.warmup * 20):
        ex.update(b)
    assert len(ex._bars) <= 6 * ex.warmup


def test_uptrend_has_positive_short_return() -> None:
    ex = FeatureExtractor()
    feats = None
    for b in _trend(ex.warmup + 3):
        feats = ex.update(b)
    assert feats is not None
    assert feats["ret_1"] > 0
    assert feats["sma_dist"] > 0  # price above its own moving average


def test_build_dataset_aligns_x_and_y() -> None:
    bars = _trend(80)
    ds = build_dataset(bars, horizon=5, threshold=0.0)
    assert ds.x.shape[0] == ds.y.shape[0]
    assert ds.x.shape[1] == len(FEATURE_NAMES)
    assert ds.feature_names == FEATURE_NAMES
    assert len(ds) == ds.x.shape[0]


def test_build_dataset_labels_uptrend_positive() -> None:
    bars = _trend(80)
    ds = build_dataset(bars, horizon=5, threshold=0.0)
    # A monotonic uptrend: every forward window is up.
    assert ds.y.sum() == ds.y.shape[0]


def test_build_dataset_labels_downtrend_negative() -> None:
    bars = [_bar(i, 200.0 - i) for i in range(80)]
    ds = build_dataset(bars, horizon=5, threshold=0.0)
    assert ds.y.sum() == 0


def test_build_dataset_empty_for_short_input() -> None:
    ds = build_dataset(_trend(3), horizon=5)
    assert len(ds) == 0
    assert ds.x.shape == (0, len(FEATURE_NAMES))


def test_build_dataset_threshold_filters_small_moves() -> None:
    bars = _trend(80)
    loose = build_dataset(bars, horizon=5, threshold=0.0)
    strict = build_dataset(bars, horizon=5, threshold=1.0)  # +100% in 5 bars: impossible here
    assert loose.y.sum() > strict.y.sum()
    assert strict.y.sum() == 0


def test_dataset_feeds_logistic_regression() -> None:
    # End-to-end: features -> dataset -> model trains without error.
    from algotrading.ml.model import LogisticRegression, StandardScaler

    up = _trend(60)
    down = [_bar(i, 200.0 - i) for i in range(60)]
    ds_up = build_dataset(up, horizon=3)
    ds_down = build_dataset(down, horizon=3)
    x = np.vstack([ds_up.x, ds_down.x])
    y = np.concatenate([ds_up.y, ds_down.y])
    model = LogisticRegression(n_iter=200, seed=0)
    scaler = StandardScaler()
    model.fit(scaler.fit_transform(x), y)
    assert model.predict_proba(scaler.transform(x)).shape[0] == x.shape[0]
