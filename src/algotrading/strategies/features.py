"""Streaming feature extraction for ML signals.

Turns a bar stream into a fixed, ordered feature vector per bar — the inputs a
learned model scores. Features are India-equity-relevant and cheap to compute:
short/medium returns, realized vol, RSI, ADX (trend strength), the opening gap,
distance from a moving average, and the bar's range. All reuse the indicators
already in the package, so the same maths runs in research and live.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from algotrading.risk.sizing import return_volatility

from .base import Bar
from .indicators import rsi, sma
from .regime import adx

FEATURE_NAMES: tuple[str, ...] = (
    "ret_1",
    "ret_5",
    "vol",
    "rsi",
    "adx",
    "gap",
    "sma_dist",
    "hl_range",
)


@dataclass
class FeatureExtractor:
    """Builds a feature vector per bar once enough history has accumulated."""

    rsi_period: int = 14
    adx_period: int = 14
    vol_period: int = 20
    sma_period: int = 20
    _bars: list[Bar] = field(default_factory=list, init=False, repr=False)

    @property
    def feature_names(self) -> tuple[str, ...]:
        return FEATURE_NAMES

    @property
    def warmup(self) -> int:
        return max(
            6,
            self.rsi_period + 1,
            self.vol_period + 1,
            self.sma_period,
            2 * self.adx_period + 1,
        )

    def reset(self) -> None:
        self._bars = []

    def update(self, bar: Bar) -> dict[str, float] | None:
        """Append ``bar``; return its feature dict, or ``None`` during warm-up."""
        self._bars.append(bar)
        cap = 6 * self.warmup
        if len(self._bars) > cap:
            del self._bars[:-cap]
        if len(self._bars) < self.warmup:
            return None

        closes = [b.close for b in self._bars]
        prev_close = closes[-2]
        sma_val = sma(closes, self.sma_period)
        features = {
            "ret_1": (bar.close - prev_close) / prev_close if prev_close else 0.0,
            "ret_5": (bar.close - closes[-6]) / closes[-6] if closes[-6] else 0.0,
            "vol": return_volatility(closes, self.vol_period),
            "rsi": rsi(closes, self.rsi_period) / 100.0,
            "adx": adx(self._bars, self.adx_period) / 100.0,
            "gap": (bar.open - prev_close) / prev_close if prev_close else 0.0,
            "sma_dist": (bar.close - sma_val) / sma_val if sma_val else 0.0,
            "hl_range": (bar.high - bar.low) / bar.close if bar.close else 0.0,
        }
        return features

    def vector(self, features: dict[str, float]) -> list[float]:
        """Ordered feature vector matching :attr:`feature_names`."""
        return [features[name] for name in FEATURE_NAMES]
