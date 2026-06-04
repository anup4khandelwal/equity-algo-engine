"""Core strategy abstractions shared by the backtester and the live engine.

The same ``Strategy`` instances drive both the event-driven simulator (Phase 3)
and the live paper-trading loop (Phase 5), so there is no backtest-vs-live drift:
both feed bars to ``on_bar`` and act on the returned :class:`Signal`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Side(StrEnum):
    """Order side."""

    BUY = "BUY"
    SELL = "SELL"


class SignalType(StrEnum):
    """Whether a signal opens or closes a position."""

    ENTRY = "ENTRY"
    EXIT = "EXIT"


@dataclass(frozen=True)
class Bar:
    """A single OHLC bar fed to a strategy."""

    instrument_token: int
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


@dataclass(frozen=True)
class Signal:
    """A strategy's intent for a bar.

    ``price`` is the strategy's intended execution price (e.g. a breakout level
    or a stop/target level). The executor applies slippage on top of it; when
    ``None`` the executor fills at the bar close.
    """

    time: datetime
    instrument_token: int
    type: SignalType
    side: Side
    price: float | None = None
    reason: str = ""


@dataclass
class Position:
    """An open position, as seen by a strategy's risk check."""

    direction: Side
    quantity: int
    entry_price: float
    entry_time: datetime

    @property
    def sign(self) -> int:
        """+1 for a long position, -1 for a short."""
        return 1 if self.direction is Side.BUY else -1


class Strategy(ABC):
    """Base class for all strategies.

    Subclasses implement :meth:`generate_signal` (the trading logic) and may
    override :meth:`risk_check` (a gate that can veto or modify a signal — the
    risk module in Phase 4 plugs in here). :meth:`on_bar` is the single entry
    point used by both the simulator and the live engine.
    """

    name: str = "strategy"

    def reset(self) -> None:  # noqa: B027 - optional hook, no-op by default
        """Clear any per-run internal state. Called before a backtest run."""

    @abstractmethod
    def generate_signal(self, bar: Bar) -> Signal | None:
        """Return a signal for this bar, or ``None`` to do nothing."""

    def risk_check(self, signal: Signal, position: Position | None) -> Signal | None:
        """Approve, modify, or veto a signal. Default: pass through unchanged."""
        return signal

    def on_bar(self, bar: Bar, position: Position | None = None) -> Signal | None:
        signal = self.generate_signal(bar)
        if signal is None:
            return None
        return self.risk_check(signal, position)
