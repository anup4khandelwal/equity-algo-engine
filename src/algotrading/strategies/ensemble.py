"""Ensemble meta-strategy: combine several strategies into one signal.

Instead of acting on a single indicator, the ensemble tracks each member
strategy's *stance* (long / short / flat, updated from its signals) and takes a
weighted vote each bar. Members can be gated to the market regimes they were
designed for (e.g. trend-followers only vote in a TRENDING market, mean-
reverters in a RANGING one), so the book adapts as conditions change.

The ensemble is itself a :class:`Strategy`, so it backtests and paper-trades
through the exact same engines as any single strategy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import Bar, Side, Signal, SignalType, Strategy
from .regime import Regime, RegimeDetector


@dataclass
class Member:
    """One voting member of the ensemble.

    ``regimes`` restricts when the member's vote counts (``None`` = always).
    The member strategy still sees every bar so its indicators stay warm.
    """

    strategy: Strategy
    weight: float = 1.0
    regimes: frozenset[Regime] | None = None
    stance: int = field(default=0, init=False)  # +1 long, -1 short, 0 flat

    def active_in(self, regime: Regime | None) -> bool:
        if self.regimes is None:
            return True
        return regime is not None and regime in self.regimes


class EnsembleStrategy(Strategy):
    name = "ensemble"

    def __init__(
        self,
        instrument_token: int,
        members: list[Member],
        *,
        entry_threshold: float = 0.5,
        exit_threshold: float = 0.0,
        detector: RegimeDetector | None = None,
    ) -> None:
        if not members:
            raise ValueError("ensemble needs at least one member")
        if not 0 < entry_threshold <= 1:
            raise ValueError("entry_threshold must be in (0, 1]")
        self.instrument_token = instrument_token
        self.members = members
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.detector = detector
        self.reset()

    def reset(self) -> None:
        for member in self.members:
            member.strategy.reset()
            member.stance = 0
        if self.detector is not None:
            self.detector.reset()
        self._direction: Side | None = None
        self.last_score = 0.0
        self.last_regime: Regime | None = None

    def _update_stances(self, bar: Bar) -> None:
        for member in self.members:
            signal = member.strategy.generate_signal(bar)
            if signal is None:
                continue
            if signal.type is SignalType.ENTRY:
                member.stance = 1 if signal.side is Side.BUY else -1
            else:
                member.stance = 0

    def _score(self, regime: Regime | None) -> float:
        """Weighted net stance of active members, normalised to [-1, 1]."""
        active = [m for m in self.members if m.active_in(regime)]
        total = sum(m.weight for m in active)
        if total <= 0:
            return 0.0
        return sum(m.stance * m.weight for m in active) / total

    def generate_signal(self, bar: Bar) -> Signal | None:
        regime = self.detector.update(bar) if self.detector is not None else None
        self.last_regime = regime
        self._update_stances(bar)
        score = self._score(regime)
        self.last_score = score

        if self._direction is None:
            if score >= self.entry_threshold:
                self._direction = Side.BUY
                return self._signal(bar, SignalType.ENTRY, Side.BUY, f"ensemble_long({score:.2f})")
            if score <= -self.entry_threshold:
                self._direction = Side.SELL
                return self._signal(
                    bar, SignalType.ENTRY, Side.SELL, f"ensemble_short({score:.2f})"
                )
            return None

        if self._direction is Side.BUY and score <= self.exit_threshold:
            self._direction = None
            return self._signal(bar, SignalType.EXIT, Side.SELL, f"ensemble_exit({score:.2f})")
        if self._direction is Side.SELL and score >= -self.exit_threshold:
            self._direction = None
            return self._signal(bar, SignalType.EXIT, Side.BUY, f"ensemble_exit({score:.2f})")
        return None

    def _signal(self, bar: Bar, type_: SignalType, side: Side, reason: str) -> Signal:
        return Signal(bar.time, self.instrument_token, type_, side, bar.close, reason)
