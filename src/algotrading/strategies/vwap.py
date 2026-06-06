"""Intraday VWAP mean-reversion.

Fade moves away from the session VWAP: go long when price is a band below VWAP
(expecting reversion up), short when a band above, and exit when price returns to
VWAP. VWAP resets each day. Square-off is handled by the engine.
"""

from __future__ import annotations

from datetime import date

from .base import Bar, Side, Signal, SignalType, Strategy


class VWAPReversion(Strategy):
    name = "vwap_reversion"

    def __init__(
        self, instrument_token: int, *, band: float = 0.005, allow_short: bool = True
    ) -> None:
        if band <= 0:
            raise ValueError("band must be positive")
        self.instrument_token = instrument_token
        self.band = band
        self.allow_short = allow_short
        self.reset()

    def reset(self) -> None:
        self._date: date | None = None
        self._cum_pv = 0.0
        self._cum_vol = 0.0
        self._direction: Side | None = None

    def _reset_day(self, day: date) -> None:
        self._date = day
        self._cum_pv = 0.0
        self._cum_vol = 0.0
        self._direction = None

    def generate_signal(self, bar: Bar) -> Signal | None:
        if bar.time.date() != self._date:
            self._reset_day(bar.time.date())

        typical = (bar.high + bar.low + bar.close) / 3.0
        volume = max(bar.volume, 0)
        self._cum_pv += typical * volume
        self._cum_vol += volume
        vwap = self._cum_pv / self._cum_vol if self._cum_vol > 0 else bar.close

        if self._direction is None:
            if bar.close < vwap * (1 - self.band):
                self._direction = Side.BUY
                return Signal(
                    bar.time,
                    self.instrument_token,
                    SignalType.ENTRY,
                    Side.BUY,
                    bar.close,
                    "below_vwap",
                )
            if self.allow_short and bar.close > vwap * (1 + self.band):
                self._direction = Side.SELL
                return Signal(
                    bar.time,
                    self.instrument_token,
                    SignalType.ENTRY,
                    Side.SELL,
                    bar.close,
                    "above_vwap",
                )
            return None

        # In a position: exit when price reverts through VWAP.
        if self._direction is Side.BUY and bar.close >= vwap:
            self._direction = None
            return Signal(
                bar.time,
                self.instrument_token,
                SignalType.EXIT,
                Side.SELL,
                bar.close,
                "vwap_revert",
            )
        if self._direction is Side.SELL and bar.close <= vwap:
            self._direction = None
            return Signal(
                bar.time, self.instrument_token, SignalType.EXIT, Side.BUY, bar.close, "vwap_revert"
            )
        return None
