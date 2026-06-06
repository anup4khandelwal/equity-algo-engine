"""Time-series momentum — a positional (multi-day) strategy.

Goes long when the trailing ``lookback``-bar return exceeds ``entry_threshold``
and exits when it falls below ``exit_threshold``. Unlike ORB this holds across
days (no intraday square-off), which exercises the framework on a positional
horizon and confirms strategy code generalises beyond intraday.

Note: a full cross-sectional Nifty-200 rotation (rank-and-rotate across many
names) needs a multi-asset portfolio layer; that is future work. This
single-instrument time-series momentum proves the same Strategy interface
supports positional logic today.
"""

from __future__ import annotations

from .base import Bar, Side, Signal, SignalType, Strategy


class Momentum(Strategy):
    name = "momentum"

    def __init__(
        self,
        instrument_token: int,
        *,
        lookback: int = 20,
        entry_threshold: float = 0.0,
        exit_threshold: float = 0.0,
    ) -> None:
        if lookback < 1:
            raise ValueError("lookback must be >= 1")
        self.instrument_token = instrument_token
        self.lookback = lookback
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.reset()

    def reset(self) -> None:
        self._closes: list[float] = []
        self._in_position = False

    def generate_signal(self, bar: Bar) -> Signal | None:
        self._closes.append(bar.close)
        if len(self._closes) > self.lookback + 1:
            self._closes = self._closes[-(self.lookback + 1) :]

        if len(self._closes) <= self.lookback:
            return None

        past = self._closes[0]
        if past == 0:
            return None
        momentum = (bar.close - past) / past

        if not self._in_position and momentum > self.entry_threshold:
            self._in_position = True
            return Signal(
                time=bar.time,
                instrument_token=self.instrument_token,
                type=SignalType.ENTRY,
                side=Side.BUY,
                price=bar.close,
                reason="momentum",
            )
        if self._in_position and momentum < self.exit_threshold:
            self._in_position = False
            return Signal(
                time=bar.time,
                instrument_token=self.instrument_token,
                type=SignalType.EXIT,
                side=Side.SELL,
                price=bar.close,
                reason="momentum_exit",
            )
        return None
