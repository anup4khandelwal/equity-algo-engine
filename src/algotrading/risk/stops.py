"""Engine-level protective stops.

A hard stop-loss and/or a trailing stop applied to *any* open position,
independent of the strategy that opened it. The engine checks these before the
strategy's own logic each bar, so even strategies without built-in stops are
protected. Stops fire intrabar (against the bar's high/low) at the stop level.
"""

from __future__ import annotations

from dataclasses import dataclass

from algotrading.strategies.base import Bar, Position, Side


@dataclass(frozen=True)
class StopConfig:
    """Stop distances as fractions of price (None disables that stop)."""

    stop_loss_pct: float | None = None  # e.g. 0.02 = exit 2% adverse to entry
    trailing_pct: float | None = None  # e.g. 0.03 = exit 3% off the best price

    @property
    def enabled(self) -> bool:
        return self.stop_loss_pct is not None or self.trailing_pct is not None


@dataclass(frozen=True)
class StopHit:
    """A triggered stop: the fill price and the reason tag."""

    price: float
    reason: str


class ProtectiveStops:
    """Tracks the favorable extreme per instrument and reports stop hits."""

    def __init__(self, config: StopConfig) -> None:
        self.config = config
        self._extreme: dict[int, float] = {}

    def on_close(self, instrument_token: int) -> None:
        self._extreme.pop(instrument_token, None)

    def update_and_check(
        self, instrument_token: int, position: Position, bar: Bar
    ) -> StopHit | None:
        """Update the trailing extreme and return a :class:`StopHit` if breached."""
        if not self.config.enabled:
            return None

        long = position.direction is Side.BUY
        entry = position.entry_price
        extreme = self._extreme.get(instrument_token, entry)
        extreme = max(extreme, bar.high) if long else min(extreme, bar.low)
        self._extreme[instrument_token] = extreme

        # Hard stop takes precedence (more conservative).
        if self.config.stop_loss_pct is not None:
            if long:
                level = entry * (1 - self.config.stop_loss_pct)
                if bar.low <= level:
                    return StopHit(level, "stop_loss")
            else:
                level = entry * (1 + self.config.stop_loss_pct)
                if bar.high >= level:
                    return StopHit(level, "stop_loss")

        if self.config.trailing_pct is not None:
            if long:
                level = extreme * (1 - self.config.trailing_pct)
                if bar.low <= level:
                    return StopHit(level, "trailing_stop")
            else:
                level = extreme * (1 + self.config.trailing_pct)
                if bar.high >= level:
                    return StopHit(level, "trailing_stop")
        return None
