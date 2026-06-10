"""Broker ↔ internal position reconciliation.

A live system must continuously check that what the broker thinks it holds
matches what the engine thinks it holds. Drift means a missed fill, a manual
trade, or a bug — and trading on a wrong position is dangerous. :func:`reconcile`
diffs the internal :class:`Portfolio` against broker-reported positions and
surfaces every mismatch.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from algotrading.strategies.base import Side

from .portfolio import Portfolio


@dataclass(frozen=True)
class Discrepancy:
    """A per-instrument position mismatch (quantities are signed)."""

    instrument_token: int
    internal_qty: int
    broker_qty: int

    @property
    def diff(self) -> int:
        """Broker minus internal — how many shares the engine is out by."""
        return self.broker_qty - self.internal_qty


def internal_positions(portfolio: Portfolio) -> dict[int, int]:
    """Signed net quantity per instrument held internally."""
    out: dict[int, int] = {}
    for token, pos in portfolio.positions.items():
        qty = pos.quantity if pos.direction is Side.BUY else -pos.quantity
        if qty != 0:
            out[token] = qty
    return out


def reconcile(portfolio: Portfolio, broker_positions: Mapping[int, int]) -> list[Discrepancy]:
    """Return every instrument where internal and broker positions disagree."""
    internal = internal_positions(portfolio)
    tokens = set(internal) | set(broker_positions)
    discrepancies = [
        Discrepancy(token, internal.get(token, 0), broker_positions.get(token, 0))
        for token in sorted(tokens)
    ]
    return [d for d in discrepancies if d.diff != 0]
