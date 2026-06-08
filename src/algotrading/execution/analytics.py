"""Reconstruct completed round-trip trades from a fill stream.

The portfolio tracks *positions*; this turns the raw fill history into explicit
entry→exit trades (FIFO-matched per instrument) with net P&L, charges, and
holding time — so the live history can show realised trades, not just fills.
Works off either execution ``Fill`` objects or persisted ``FillRecord`` rows.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class FillEvent:
    """Normalised fill, decoupled from Fill vs FillRecord shapes."""

    instrument_token: int
    side: str  # "BUY" | "SELL"
    quantity: int
    price: float
    charges: float
    time: datetime
    strategy: str


@dataclass(frozen=True)
class RoundTrip:
    """A completed entry→exit trade."""

    instrument_token: int
    strategy: str
    direction: str  # entry side: "BUY" (long) or "SELL" (short)
    quantity: int
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    gross_pnl: float
    charges: float
    net_pnl: float
    holding_seconds: float


@dataclass(frozen=True)
class StrategyPnl:
    """Realised P&L for one strategy, from its completed round trips."""

    strategy: str
    trades: int
    net_pnl: float
    gross_pnl: float
    charges: float
    win_rate: float


def pnl_by_strategy(trips: Sequence[RoundTrip]) -> list[StrategyPnl]:
    """Aggregate completed round trips into per-strategy realised P&L."""
    groups: dict[str, list[RoundTrip]] = {}
    for trip in trips:
        groups.setdefault(trip.strategy, []).append(trip)

    out: list[StrategyPnl] = []
    for strategy, ts in sorted(groups.items()):
        wins = sum(1 for t in ts if t.net_pnl > 0)
        out.append(
            StrategyPnl(
                strategy=strategy,
                trades=len(ts),
                net_pnl=sum(t.net_pnl for t in ts),
                gross_pnl=sum(t.gross_pnl for t in ts),
                charges=sum(t.charges for t in ts),
                win_rate=wins / len(ts),
            )
        )
    return out


def event_from_fill(fill: Any) -> FillEvent:
    """Adapt an execution ``Fill`` to a :class:`FillEvent`."""
    order = fill.order
    return FillEvent(
        instrument_token=order.instrument_token,
        side=str(order.side.value),
        quantity=fill.quantity,
        price=fill.fill_price,
        charges=fill.charges,
        time=fill.time,
        strategy=order.tag,
    )


def event_from_record(record: Any) -> FillEvent:
    """Adapt a persisted ``FillRecord`` to a :class:`FillEvent`."""
    return FillEvent(
        instrument_token=record.instrument_token,
        side=str(record.side),
        quantity=record.quantity,
        price=record.price,
        charges=record.charges,
        time=record.time,
        strategy=record.strategy,
    )


@dataclass
class _Lot:
    sign: int  # +1 long, -1 short
    quantity: int
    price: float
    time: datetime
    strategy: str
    charges: float  # remaining (un-amortised) entry charges


def round_trips(events: Sequence[FillEvent]) -> list[RoundTrip]:
    """FIFO-match fills per instrument into completed round trips (time order)."""
    trips: list[RoundTrip] = []
    open_lots: dict[int, list[_Lot]] = {}

    for ev in sorted(events, key=lambda e: e.time):
        if ev.quantity <= 0:
            continue
        sign = 1 if ev.side == "BUY" else -1
        remaining = ev.quantity
        charge_per_unit = ev.charges / ev.quantity
        lots = open_lots.setdefault(ev.instrument_token, [])

        # Close against opposing lots first (FIFO).
        while remaining > 0 and lots and lots[0].sign == -sign:
            lot = lots[0]
            matched = min(lot.quantity, remaining)
            entry_charge = lot.charges * matched / lot.quantity
            exit_charge = charge_per_unit * matched
            gross = lot.sign * (ev.price - lot.price) * matched
            charges = entry_charge + exit_charge
            trips.append(
                RoundTrip(
                    instrument_token=ev.instrument_token,
                    strategy=lot.strategy,
                    direction="BUY" if lot.sign > 0 else "SELL",
                    quantity=matched,
                    entry_time=lot.time,
                    entry_price=lot.price,
                    exit_time=ev.time,
                    exit_price=ev.price,
                    gross_pnl=gross,
                    charges=charges,
                    net_pnl=gross - charges,
                    holding_seconds=(ev.time - lot.time).total_seconds(),
                )
            )
            lot.quantity -= matched
            lot.charges -= entry_charge
            remaining -= matched
            if lot.quantity == 0:
                lots.pop(0)

        # Anything left opens a new lot (same direction, or a flip past flat).
        if remaining > 0:
            lots.append(
                _Lot(
                    sign=sign,
                    quantity=remaining,
                    price=ev.price,
                    time=ev.time,
                    strategy=ev.strategy,
                    charges=charge_per_unit * remaining,
                )
            )

    return trips
