"""Engine-level risk controls.

Gates new entries on: the daily-loss kill-switch, the max-open-positions cap,
and a cut-off after which no new intraday trades are taken. Also exposes the
square-off time used by the live loop to flatten positions before close.

Time-of-day checks use naive ``datetime.time`` in exchange-local (IST) terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class RiskLimits:
    """Configurable risk limits (sensible intraday defaults)."""

    max_open_positions: int = 3
    daily_loss_limit: float = 5_000.0  # absolute ₹; kill-switch threshold
    no_new_trades_after: time = time(15, 0)
    square_off_at: time = time(15, 15)


class RiskManager:
    """Stateful gatekeeper for new entries and the daily kill-switch.

    The kill-switch latches: once tripped it stays on until :meth:`reset_day`,
    so a brief P&L recovery can't silently re-enable trading.
    """

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()
        self._halted = False

    @property
    def halted(self) -> bool:
        return self._halted

    def update_pnl(self, day_pnl: float) -> None:
        """Trip (and latch) the kill-switch if the day loss breaches the limit."""
        if day_pnl <= -self.limits.daily_loss_limit:
            self._halted = True

    def can_enter(self, *, now: time, open_positions: int, day_pnl: float) -> bool:
        """Whether a new entry is permitted right now."""
        self.update_pnl(day_pnl)
        if self._halted:
            return False
        if open_positions >= self.limits.max_open_positions:
            return False
        if now >= self.limits.no_new_trades_after:
            return False
        return True

    def should_square_off(self, now: time) -> bool:
        """Whether open intraday positions should be flattened by now."""
        return now >= self.limits.square_off_at

    def reset_day(self) -> None:
        """Clear the latched kill-switch at the start of a new session."""
        self._halted = False
