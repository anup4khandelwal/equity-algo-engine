"""Supertrend — an ATR-band trend-following strategy.

Enter long when the trend flips up (price closes above the Supertrend line),
exit when it flips down. Long-only here; the same flip drives entries/exits.
"""

from __future__ import annotations

from collections.abc import Sequence

from .base import Bar, Side, Signal, SignalType, Strategy


def _atr(bars: Sequence[Bar], period: int) -> float:
    trs = []
    for prev, curr in zip(bars, bars[1:], strict=False):
        trs.append(
            max(
                curr.high - curr.low,
                abs(curr.high - prev.close),
                abs(curr.low - prev.close),
            )
        )
    window = trs[-period:]
    return sum(window) / len(window) if window else 0.0


class Supertrend(Strategy):
    name = "supertrend"

    def __init__(self, instrument_token: int, *, period: int = 10, multiplier: float = 3.0) -> None:
        self.instrument_token = instrument_token
        self.period = period
        self.multiplier = multiplier
        self.reset()

    def reset(self) -> None:
        self._bars: list[Bar] = []
        self._final_upper = 0.0
        self._final_lower = 0.0
        self._supertrend = 0.0
        self._prev_close = 0.0
        self._trend = -1
        self._initialized = False
        self._in_position = False

    def generate_signal(self, bar: Bar) -> Signal | None:
        self._bars.append(bar)
        if len(self._bars) < self.period + 1:
            return None

        atr = _atr(self._bars, self.period)
        hl2 = (bar.high + bar.low) / 2.0
        basic_upper = hl2 + self.multiplier * atr
        basic_lower = hl2 - self.multiplier * atr

        if not self._initialized:
            self._final_upper = basic_upper
            self._final_lower = basic_lower
            self._supertrend = basic_upper
            self._trend = -1
            self._prev_close = bar.close
            self._initialized = True
            return None

        final_upper = (
            basic_upper
            if (basic_upper < self._final_upper or self._prev_close > self._final_upper)
            else self._final_upper
        )
        final_lower = (
            basic_lower
            if (basic_lower > self._final_lower or self._prev_close < self._final_lower)
            else self._final_lower
        )

        if self._supertrend == self._final_upper:
            if bar.close <= final_upper:
                supertrend, trend = final_upper, -1
            else:
                supertrend, trend = final_lower, 1
        else:
            if bar.close >= final_lower:
                supertrend, trend = final_lower, 1
            else:
                supertrend, trend = final_upper, -1

        signal: Signal | None = None
        if trend == 1 and self._trend == -1 and not self._in_position:
            self._in_position = True
            signal = Signal(
                bar.time, self.instrument_token, SignalType.ENTRY, Side.BUY, bar.close, "flip_up"
            )
        elif trend == -1 and self._trend == 1 and self._in_position:
            self._in_position = False
            signal = Signal(
                bar.time, self.instrument_token, SignalType.EXIT, Side.SELL, bar.close, "flip_down"
            )

        self._final_upper = final_upper
        self._final_lower = final_lower
        self._supertrend = supertrend
        self._trend = trend
        self._prev_close = bar.close
        return signal
