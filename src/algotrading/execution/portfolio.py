"""A simple position book and P&L tracker.

Both paper and (future) live flows update a :class:`Portfolio` as fills arrive,
giving the risk layer a live view of open positions and day P&L. Realised P&L is
**net** of charges: each fill's charges are subtracted, and the price move is
booked when a position is closed or reduced.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from algotrading.execution.gateway import Fill, OrderStatus
from algotrading.strategies.base import Position, Side


@dataclass
class Portfolio:
    """Tracks open positions and realised P&L from fills."""

    positions: dict[int, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    total_charges: float = 0.0

    def open_position_count(self) -> int:
        return len(self.positions)

    def apply_fill(self, fill: Fill) -> None:
        """Update the book from a filled order. Non-fills are ignored."""
        if fill.status is not OrderStatus.FILLED or fill.quantity == 0:
            return

        self.realized_pnl -= fill.charges
        self.total_charges += fill.charges

        order = fill.order
        token = order.instrument_token
        existing = self.positions.get(token)
        signed_qty = fill.quantity if order.side is Side.BUY else -fill.quantity

        if existing is None:
            self.positions[token] = Position(
                direction=order.side,
                quantity=fill.quantity,
                entry_price=fill.fill_price,
                entry_time=fill.time,
            )
            return

        existing_signed = existing.sign * existing.quantity
        new_signed = existing_signed + signed_qty

        if existing_signed * signed_qty > 0:
            # Same direction: add to the position, update the average price.
            total_qty = existing.quantity + fill.quantity
            existing.entry_price = (
                existing.entry_price * existing.quantity + fill.fill_price * fill.quantity
            ) / total_qty
            existing.quantity = total_qty
            return

        # Opposite direction: realise P&L on the closed portion.
        closed = min(existing.quantity, fill.quantity)
        self.realized_pnl += existing.sign * (fill.fill_price - existing.entry_price) * closed

        if new_signed == 0:
            del self.positions[token]
        elif existing_signed * new_signed > 0:
            existing.quantity = abs(new_signed)
        else:
            # Flipped past flat: open a fresh position with the remainder.
            self.positions[token] = Position(
                direction=order.side,
                quantity=abs(new_signed),
                entry_price=fill.fill_price,
                entry_time=fill.time,
            )

    def unrealized_pnl(self, prices: dict[int, float]) -> float:
        """Mark open positions to market using ``prices`` (token -> last price)."""
        total = 0.0
        for token, pos in self.positions.items():
            price = prices.get(token)
            if price is not None:
                total += pos.sign * (price - pos.entry_price) * pos.quantity
        return total

    def day_pnl(self, prices: dict[int, float]) -> float:
        """Realised (net of charges) plus unrealised P&L."""
        return self.realized_pnl + self.unrealized_pnl(prices)
