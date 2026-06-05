"""Moving-average crossover — a trend-following strategy.

Long when the fast SMA crosses above the slow SMA; exit when it crosses back
below. Positional (holds across days).
"""

from __future__ import annotations

from .base import Bar, Side, Signal, SignalType, Strategy
from .indicators import sma


class MovingAverageCrossover(Strategy):
    name = "ma_crossover"

    def __init__(self, instrument_token: int, *, fast: int = 20, slow: int = 50) -> None:
        if fast >= slow:
            raise ValueError("fast period must be < slow period")
        self.instrument_token = instrument_token
        self.fast = fast
        self.slow = slow
        self.reset()

    def reset(self) -> None:
        self._closes: list[float] = []
        self._in_position = False

    def generate_signal(self, bar: Bar) -> Signal | None:
        self._closes.append(bar.close)
        if len(self._closes) < self.slow + 1:
            return None

        fast_now = sma(self._closes, self.fast)
        slow_now = sma(self._closes, self.slow)
        fast_prev = sma(self._closes[:-1], self.fast)
        slow_prev = sma(self._closes[:-1], self.slow)

        cross_up = fast_prev <= slow_prev and fast_now > slow_now
        cross_down = fast_prev >= slow_prev and fast_now < slow_now

        if not self._in_position and cross_up:
            self._in_position = True
            return Signal(
                bar.time,
                self.instrument_token,
                SignalType.ENTRY,
                Side.BUY,
                bar.close,
                "ma_cross_up",
            )
        if self._in_position and cross_down:
            self._in_position = False
            return Signal(
                bar.time,
                self.instrument_token,
                SignalType.EXIT,
                Side.SELL,
                bar.close,
                "ma_cross_down",
            )
        return None
