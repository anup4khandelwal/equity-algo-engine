"""Opening Range Breakout (ORB) — an intraday strategy.

For each trading day:
1. Build the "opening range" from the high/low of the first
   ``opening_range_minutes`` of the session.
2. After the range is fixed, take the **first** breakout: go long when a bar
   closes above the range high, short when it closes below the range low.
3. Manage the trade with a stop at the opposite end of the range and a target
   ``target_multiple`` range-widths beyond the breakout level.
4. Square off any open position at ``square_off`` time.

Only one trade is taken per day. State is reset at each new date, so the same
instance can run across a multi-day series (and, unchanged, in the live engine).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .base import Bar, Side, Signal, SignalType, Strategy


class OpeningRangeBreakout(Strategy):
    name = "opening_range_breakout"

    def __init__(
        self,
        instrument_token: int,
        *,
        opening_range_minutes: int = 15,
        target_multiple: float = 1.0,
        session_start: time = time(9, 15),
        square_off: time = time(15, 15),
    ) -> None:
        self.instrument_token = instrument_token
        self.opening_range_minutes = opening_range_minutes
        self.target_multiple = target_multiple
        self.session_start = session_start
        self.square_off = square_off
        # End of the opening-range window (exclusive).
        self._range_end = (
            datetime.combine(date.min, session_start) + timedelta(minutes=opening_range_minutes)
        ).time()
        self.reset()

    def reset(self) -> None:
        self._date: date | None = None
        self._range_high = float("-inf")
        self._range_low = float("inf")
        self._traded_today = False
        self._in_trade = False
        self._direction: Side | None = None
        self._stop = 0.0
        self._target = 0.0

    def _reset_day(self, day: date) -> None:
        self._date = day
        self._range_high = float("-inf")
        self._range_low = float("inf")
        self._traded_today = False
        self._in_trade = False
        self._direction = None
        self._stop = 0.0
        self._target = 0.0

    def _exit(self, when: datetime, price: float, reason: str) -> Signal:
        assert self._direction is not None
        closing_side = Side.SELL if self._direction is Side.BUY else Side.BUY
        self._in_trade = False
        self._direction = None
        return Signal(
            time=when,
            instrument_token=self.instrument_token,
            type=SignalType.EXIT,
            side=closing_side,
            price=price,
            reason=reason,
        )

    def generate_signal(self, bar: Bar) -> Signal | None:
        bar_date = bar.time.date()
        bar_time = bar.time.time()

        if bar_date != self._date:
            self._reset_day(bar_date)

        # 1. Build the opening range.
        if self.session_start <= bar_time < self._range_end:
            self._range_high = max(self._range_high, bar.high)
            self._range_low = min(self._range_low, bar.low)
            return None

        # 2. Manage an open trade (square-off, then stop/target).
        if self._in_trade:
            if bar_time >= self.square_off:
                return self._exit(bar.time, bar.close, "square_off")
            if self._direction is Side.BUY:
                if bar.low <= self._stop:
                    return self._exit(bar.time, self._stop, "stop")
                if bar.high >= self._target:
                    return self._exit(bar.time, self._target, "target")
            else:
                if bar.high >= self._stop:
                    return self._exit(bar.time, self._stop, "stop")
                if bar.low <= self._target:
                    return self._exit(bar.time, self._target, "target")
            return None

        # 3. Look for the first breakout (range must be fixed and valid).
        range_ready = self._range_high > float("-inf") and self._range_low < float("inf")
        if not range_ready or self._traded_today or bar_time >= self.square_off:
            return None

        width = self._range_high - self._range_low
        offset = self.target_multiple * width
        if bar.close > self._range_high:
            return self._enter(bar, Side.BUY, self._range_low, bar.close + offset)
        if bar.close < self._range_low:
            return self._enter(bar, Side.SELL, self._range_high, bar.close - offset)
        return None

    def _enter(self, bar: Bar, side: Side, stop: float, target: float) -> Signal:
        self._in_trade = True
        self._traded_today = True
        self._direction = side
        self._stop = stop
        self._target = target
        return Signal(
            time=bar.time,
            instrument_token=self.instrument_token,
            type=SignalType.ENTRY,
            side=side,
            price=bar.close,
            reason="breakout",
        )
