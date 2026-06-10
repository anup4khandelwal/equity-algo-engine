"""Tests for the from-scratch logistic regression and scaler."""

from __future__ import annotations

import numpy as np
import pytest

from algotrading.ml.model import LogisticRegression, StandardScaler


def test_scaler_standardises_columns() -> None:
    x = np.array([[1.0, 100.0], [2.0, 200.0], [3.0, 300.0]])
    scaler = StandardScaler()
    z = scaler.fit_transform(x)
    assert np.allclose(z.mean(axis=0), 0.0, atol=1e-9)
    assert np.allclose(z.std(axis=0), 1.0, atol=1e-9)


def test_scaler_handles_constant_column() -> None:
    x = np.array([[1.0, 5.0], [2.0, 5.0], [3.0, 5.0]])
    z = StandardScaler().fit_transform(x)
    # Constant column maps to zeros without dividing by zero.
    assert np.allclose(z[:, 1], 0.0)
    assert not np.isnan(z).any()


def test_scaler_roundtrip() -> None:
    x = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    scaler = StandardScaler().fit(x)
    restored = StandardScaler.from_dict(scaler.to_dict())
    assert np.allclose(scaler.transform(x), restored.transform(x))


def test_logreg_learns_separable_data() -> None:
    rng = np.random.default_rng(42)
    pos = rng.normal(2.0, 0.4, size=(60, 2))
    neg = rng.normal(-2.0, 0.4, size=(60, 2))
    x = np.vstack([pos, neg])
    y = np.array([1] * 60 + [0] * 60)

    scaler = StandardScaler()
    model = LogisticRegression(learning_rate=0.5, n_iter=800, seed=1)
    model.fit(scaler.fit_transform(x), y)

    preds = model.predict(scaler.transform(x))
    accuracy = float((preds == y).mean())
    assert accuracy > 0.95


def test_logreg_proba_in_unit_interval() -> None:
    x = np.array([[0.0], [1.0], [-1.0], [10.0], [-10.0]])
    y = np.array([0, 1, 0, 1, 0])
    model = LogisticRegression(n_iter=100).fit(x, y)
    proba = model.predict_proba(x)
    assert proba.min() >= 0.0
    assert proba.max() <= 1.0


def test_logreg_predict_one_matches_batch() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(40, 3))
    y = (x[:, 0] > 0).astype(int)
    model = LogisticRegression(n_iter=200).fit(x, y)
    batch = model.predict_proba(x[:1])[0]
    one = model.predict_proba_one(list(x[0]))
    assert one == pytest.approx(batch)


def test_logreg_roundtrip_serialisation() -> None:
    rng = np.random.default_rng(7)
    x = rng.normal(size=(30, 4))
    y = (x.sum(axis=1) > 0).astype(int)
    model = LogisticRegression(n_iter=150, l2=0.01, seed=3).fit(x, y)
    restored = LogisticRegression.from_dict(model.to_dict())
    assert np.allclose(model.predict_proba(x), restored.predict_proba(x))


def test_logreg_is_deterministic() -> None:
    rng = np.random.default_rng(11)
    x = rng.normal(size=(50, 2))
    y = (x[:, 1] > 0).astype(int)
    a = LogisticRegression(seed=5, n_iter=100).fit(x, y)
    b = LogisticRegression(seed=5, n_iter=100).fit(x, y)
    assert np.allclose(a.weights_, b.weights_)
    assert a.bias_ == b.bias_


def test_unfitted_model_raises() -> None:
    with pytest.raises(RuntimeError):
        LogisticRegression().predict_proba(np.zeros((1, 2)))
    with pytest.raises(RuntimeError):
        StandardScaler().transform(np.zeros((1, 2)))
