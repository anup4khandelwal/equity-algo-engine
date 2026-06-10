"""India-aware execution model for the backtest simulator.

Real NSE/BSE fills differ from "fill at the close" in ways that make or break an
intraday backtest:

- **No look-ahead** — a strategy decides on a bar's close but actually fills at
  the *next* bar's open.
- **Tick size** — equity prices move in ₹0.05 ticks; fills snap to the tick.
- **Circuit / price bands** — a stock at its upper/lower circuit can't be bought/
  sold through the band, so entries beyond the band are rejected and exits are
  clamped to it.
- **Liquidity** — you can't realistically take more than a fraction of a bar's
  traded volume without moving the price.

This model captures all four. It's plugged into the simulator via
``BacktestConfig.execution``; when unset, the simulator keeps its simple
fill-at-close behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass

from algotrading.strategies.base import Side


@dataclass(frozen=True)
class ExecutionModel:
    """Configurable NSE/BSE fill assumptions."""

    tick_size: float = 0.05  # NSE equity tick
    slippage_bps: float = 1.0
    circuit_pct: float | None = None  # daily price band vs prev close (e.g. 0.10 = 10%)
    max_participation: float | None = None  # cap fill qty to this fraction of bar volume
    fill_at: str = "next_open"  # "next_open" (realistic) or "close"

    def __post_init__(self) -> None:
        if self.fill_at not in ("next_open", "close"):
            raise ValueError("fill_at must be 'next_open' or 'close'")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive")

    def round_to_tick(self, price: float) -> float:
        return round(price / self.tick_size) * self.tick_size

    def _slipped(self, price: float, side: Side) -> float:
        factor = self.slippage_bps / 10_000.0
        return price * (1 + factor) if side is Side.BUY else price * (1 - factor)

    def fill_price(self, reference_price: float, side: Side) -> float:
        """Apply adverse slippage, then snap to the tick."""
        return self.round_to_tick(self._slipped(reference_price, side))

    def within_band(self, price: float, prev_close: float | None) -> bool:
        """Whether ``price`` is inside the daily circuit band around ``prev_close``."""
        if self.circuit_pct is None or prev_close is None or prev_close <= 0:
            return True
        return prev_close * (1 - self.circuit_pct) <= price <= prev_close * (1 + self.circuit_pct)

    def clamp_to_band(self, price: float, prev_close: float | None) -> float:
        """Clamp ``price`` into the circuit band (used for exits)."""
        if self.circuit_pct is None or prev_close is None or prev_close <= 0:
            return price
        lo = prev_close * (1 - self.circuit_pct)
        hi = prev_close * (1 + self.circuit_pct)
        return self.round_to_tick(min(max(price, lo), hi))

    def cap_quantity(self, desired: int, bar_volume: int) -> int:
        """Cap fill quantity to a fraction of the bar's traded volume.

        A non-positive volume (common in synthetic/sparse data) disables the cap.
        """
        if self.max_participation is None or bar_volume <= 0:
            return desired
        return min(desired, int(bar_volume * self.max_participation))
