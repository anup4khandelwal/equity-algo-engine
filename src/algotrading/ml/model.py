"""From-scratch logistic regression + feature scaling (NumPy only).

A deliberately small, deterministic learner: full-batch gradient descent with L2
regularisation, plus a standardiser so features on different scales (a 0.001
return vs an RSI of 70) train sanely. Both serialise to plain dicts so a fitted
model can be persisted to JSON and reloaded in the live engine without pickling.

This is intentionally not scikit-learn: fewer moving parts, no extra dependency,
and every number is reproducible from the seed and the data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

ArrayLike = np.ndarray


@dataclass
class StandardScaler:
    """Zero-mean, unit-variance feature scaler fitted from training data."""

    mean_: np.ndarray | None = field(default=None)
    scale_: np.ndarray | None = field(default=None)

    def fit(self, x: ArrayLike) -> StandardScaler:
        x = np.asarray(x, dtype=float)
        self.mean_ = x.mean(axis=0)
        std = x.std(axis=0)
        # Guard against zero-variance columns (constant features).
        self.scale_ = np.where(std > 1e-12, std, 1.0)
        return self

    def transform(self, x: ArrayLike) -> np.ndarray:
        if self.mean_ is None or self.scale_ is None:
            raise RuntimeError("StandardScaler must be fitted before transform")
        x = np.asarray(x, dtype=float)
        return (x - self.mean_) / self.scale_

    def fit_transform(self, x: ArrayLike) -> np.ndarray:
        return self.fit(x).transform(x)

    def to_dict(self) -> dict[str, list[float]]:
        if self.mean_ is None or self.scale_ is None:
            raise RuntimeError("cannot serialise an unfitted StandardScaler")
        return {"mean": self.mean_.tolist(), "scale": self.scale_.tolist()}

    @classmethod
    def from_dict(cls, data: dict[str, list[float]]) -> StandardScaler:
        return cls(
            mean_=np.asarray(data["mean"], dtype=float),
            scale_=np.asarray(data["scale"], dtype=float),
        )


@dataclass
class LogisticRegression:
    """Binary logistic regression trained by full-batch gradient descent.

    Predicts P(label = 1) — for trading, the probability the next move clears the
    labelling threshold (see :func:`algotrading.ml.dataset.build_dataset`).
    """

    learning_rate: float = 0.1
    n_iter: int = 500
    l2: float = 0.0
    seed: int = 0
    weights_: np.ndarray | None = field(default=None)
    bias_: float = 0.0

    @staticmethod
    def _sigmoid(z: np.ndarray) -> np.ndarray:
        # Numerically stable sigmoid (avoids overflow for large |z|).
        out = np.empty_like(z, dtype=float)
        pos = z >= 0
        out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
        ez = np.exp(z[~pos])
        out[~pos] = ez / (1.0 + ez)
        return out

    def fit(self, x: ArrayLike, y: ArrayLike) -> LogisticRegression:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float).ravel()
        if x.ndim != 2:
            raise ValueError("x must be a 2-D (n_samples, n_features) array")
        if x.shape[0] != y.shape[0]:
            raise ValueError("x and y must have the same number of rows")
        n_samples, n_features = x.shape
        rng = np.random.default_rng(self.seed)
        self.weights_ = rng.normal(0.0, 0.01, size=n_features)
        self.bias_ = 0.0

        for _ in range(self.n_iter):
            preds = self._sigmoid(x @ self.weights_ + self.bias_)
            error = preds - y
            grad_w = x.T @ error / n_samples + self.l2 * self.weights_
            grad_b = float(error.mean())
            self.weights_ -= self.learning_rate * grad_w
            self.bias_ -= self.learning_rate * grad_b
        return self

    def predict_proba(self, x: ArrayLike) -> np.ndarray:
        if self.weights_ is None:
            raise RuntimeError("LogisticRegression must be fitted before predict")
        x = np.asarray(x, dtype=float)
        return self._sigmoid(x @ self.weights_ + self.bias_)

    def predict_proba_one(self, features: list[float]) -> float:
        """Probability for a single feature vector — the live, per-bar path."""
        return float(self.predict_proba(np.asarray([features], dtype=float))[0])

    def predict(self, x: ArrayLike, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba(x) >= threshold).astype(int)

    def to_dict(self) -> dict[str, object]:
        if self.weights_ is None:
            raise RuntimeError("cannot serialise an unfitted LogisticRegression")
        return {
            "weights": self.weights_.tolist(),
            "bias": self.bias_,
            "learning_rate": self.learning_rate,
            "n_iter": self.n_iter,
            "l2": self.l2,
            "seed": self.seed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> LogisticRegression:
        model = cls(
            learning_rate=float(data.get("learning_rate", 0.1)),
            n_iter=int(data.get("n_iter", 500)),
            l2=float(data.get("l2", 0.0)),
            seed=int(data.get("seed", 0)),
        )
        model.weights_ = np.asarray(data["weights"], dtype=float)
        model.bias_ = float(data["bias"])
        return model
