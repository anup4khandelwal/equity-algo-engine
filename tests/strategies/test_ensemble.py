"""Tests for the ensemble meta-strategy."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from algotrading.strategies.base import Bar, Side, Signal, SignalType, Strategy
from algotrading.strategies.ensemble import EnsembleStrategy, Member
from algotrading.strategies.regime import Regime

TOKEN = 1
T0 = datetime(2026, 1, 1, 9, 30)


def _bar(i: int, close: float = 100.0) -> Bar:
    return Bar(TOKEN, T0 + timedelta(minutes=i), close, close, close, close)


class ScriptedMember(Strategy):
    """Emits a fixed sequence of stances via ENTRY/EXIT signals."""

    name = "scripted"

    def __init__(self, stances: list[int]) -> None:
        self._stances = stances
        self.reset()

    def reset(self) -> None:
        self._i = 0
        self._last = 0

    def generate_signal(self, bar: Bar) -> Signal | None:
        stance = self._stances[min(self._i, len(self._stances) - 1)]
        self._i += 1
        if stance == self._last:
            return None
        self._last = stance
        if stance == 0:
            return Signal(bar.time, TOKEN, SignalType.EXIT, Side.SELL, bar.close, "x")
        side = Side.BUY if stance > 0 else Side.SELL
        return Signal(bar.time, TOKEN, SignalType.ENTRY, side, bar.close, "x")


class FixedDetector:
    """Stand-in RegimeDetector returning a preset regime."""

    def __init__(self, regime: Regime) -> None:
        self.regime = regime

    def reset(self) -> None:  # pragma: no cover - trivial
        pass

    def update(self, bar: Bar) -> Regime:
        return self.regime


def test_majority_long_vote_enters_and_exit_on_flip() -> None:
    ens = EnsembleStrategy(
        TOKEN,
        [
            Member(ScriptedMember([1, 1, 0])),
            Member(ScriptedMember([1, 1, -1])),
            Member(ScriptedMember([0, 1, -1])),
        ],
        entry_threshold=0.6,
    )
    # bar 0: stances (1,1,0) → score 2/3 ≥ 0.6 → enter long
    s0 = ens.generate_signal(_bar(0))
    assert s0 is not None and s0.type is SignalType.ENTRY and s0.side is Side.BUY
    s1 = ens.generate_signal(_bar(1))  # stances (1,1,1) → still long, no signal
    assert s1 is None
    s2 = ens.generate_signal(_bar(2))  # stances (0,-1,-1) → score < 0 → exit
    assert s2 is not None and s2.type is SignalType.EXIT and s2.side is Side.SELL


def test_short_entry_on_negative_score() -> None:
    ens = EnsembleStrategy(
        TOKEN,
        [Member(ScriptedMember([-1])), Member(ScriptedMember([-1]))],
        entry_threshold=0.9,
    )
    sig = ens.generate_signal(_bar(0))
    assert sig is not None and sig.side is Side.SELL and sig.type is SignalType.ENTRY


def test_weights_tilt_the_vote() -> None:
    # One heavy long voter vs two light shorts → net positive.
    ens = EnsembleStrategy(
        TOKEN,
        [
            Member(ScriptedMember([1]), weight=3.0),
            Member(ScriptedMember([-1]), weight=1.0),
            Member(ScriptedMember([-1]), weight=1.0),
        ],
        entry_threshold=0.2,
    )
    sig = ens.generate_signal(_bar(0))
    assert sig is not None and sig.side is Side.BUY
    assert ens.last_score == pytest.approx((3 - 1 - 1) / 5)


def test_regime_gating_silences_mismatched_members() -> None:
    trend_only = Member(ScriptedMember([1]), regimes=frozenset({Regime.TRENDING}))
    always = Member(ScriptedMember([0]))
    ens = EnsembleStrategy(
        TOKEN,
        [trend_only, always],
        entry_threshold=0.4,
        detector=FixedDetector(Regime.RANGING),
    )
    # Trend-follower votes long but the market is RANGING → its vote is ignored.
    assert ens.generate_signal(_bar(0)) is None
    assert ens.last_score == 0.0

    ens2 = EnsembleStrategy(
        TOKEN,
        [
            Member(ScriptedMember([1]), regimes=frozenset({Regime.TRENDING})),
            Member(ScriptedMember([0])),
        ],
        entry_threshold=0.4,
        detector=FixedDetector(Regime.TRENDING),
    )
    sig = ens2.generate_signal(_bar(0))  # now the vote counts: score 1/2 = 0.5
    assert sig is not None and sig.side is Side.BUY


def test_invalid_construction() -> None:
    with pytest.raises(ValueError):
        EnsembleStrategy(TOKEN, [])
    with pytest.raises(ValueError):
        EnsembleStrategy(TOKEN, [Member(ScriptedMember([1]))], entry_threshold=0.0)
