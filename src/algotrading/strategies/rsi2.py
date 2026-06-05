"""RSI(2) mean-reversion (Connors-style).

Buy short-term oversold dips, exit when momentum recovers. An optional trend
filter only takes longs when price is above a longer SMA.
"""

from __future__ import annotations

from .base import Bar, Side, Signal, SignalType, Strategy
from .indicators import rsi, sma


class RSI2(Strategy):
    name = "rsi2"

    def __init__(
        self,
        instrument_token: int,
        *,
        period: int = 2,
        lower: float = 10.0,
        upper: float = 50.0,
        trend_filter: int | None = 200,
    ) -> None:
        self.instrument_token = instrument_token
        self.period = period
        self.lower = lower
        self.upper = upper
        self.trend_filter = trend_filter
        self.reset()

    def reset(self) -> None:
        self._closes: list[float] = []
        self._in_position = False

    def generate_signal(self, bar: Bar) -> Signal | None:
        self._closes.append(bar.close)
        if len(self._closes) < self.period + 1:
            return None

        value = rsi(self._closes, self.period)

        trend_ok = True
        if self.trend_filter is not None:
            if len(self._closes) < self.trend_filter:
                trend_ok = False  # not enough data to confirm the trend
            else:
                trend_ok = bar.close > sma(self._closes, self.trend_filter)

        if not self._in_position and value < self.lower and trend_ok:
            self._in_position = True
            return Signal(
                bar.time,
                self.instrument_token,
                SignalType.ENTRY,
                Side.BUY,
                bar.close,
                "rsi_oversold",
            )
        if self._in_position and value > self.upper:
            self._in_position = False
            return Signal(
                bar.time, self.instrument_token, SignalType.EXIT, Side.SELL, bar.close, "rsi_exit"
            )
        return None
