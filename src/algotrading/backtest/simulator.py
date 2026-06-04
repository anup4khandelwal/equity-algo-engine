"""Event-driven backtest simulator.

Replays a bar series through a :class:`Strategy`, executing the signals it emits
with realistic slippage and the full transaction-cost stack, and records the
resulting trades and equity curve. Every reported P&L is **net** of costs.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from algotrading.strategies.base import Bar, Position, Side, SignalType, Strategy

from .costs import CostConfig, Product, charges_for_fill


@dataclass(frozen=True)
class BacktestConfig:
    """Execution assumptions for a backtest run."""

    initial_capital: float = 100_000.0
    product: Product = Product.INTRADAY
    slippage_bps: float = 1.0
    # Position sizing: explicit `quantity` wins; otherwise size by notional.
    quantity: int | None = None
    capital_per_trade: float | None = None
    costs: CostConfig = field(default_factory=CostConfig)


@dataclass(frozen=True)
class Trade:
    """A completed round-trip trade."""

    instrument_token: int
    direction: Side
    quantity: int
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    gross_pnl: float
    costs: float
    net_pnl: float
    exit_reason: str


@dataclass(frozen=True)
class BacktestResult:
    """Output of a backtest run."""

    trades: list[Trade]
    equity_curve: list[tuple[datetime, float]]
    initial_capital: float
    final_equity: float


def _apply_slippage(price: float, side: Side, slippage_bps: float) -> float:
    """Move the fill price adversely: buys pay up, sells receive less."""
    factor = slippage_bps / 10_000.0
    return price * (1 + factor) if side is Side.BUY else price * (1 - factor)


def _size_position(config: BacktestConfig, fill_price: float) -> int:
    if config.quantity is not None:
        return config.quantity
    notional = config.capital_per_trade or config.initial_capital
    return max(1, int(notional // fill_price))


def _unrealized(position: Position | None, price: float) -> float:
    if position is None:
        return 0.0
    return position.sign * (price - position.entry_price) * position.quantity


def run(
    strategy: Strategy,
    bars: Iterable[Bar],
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run ``strategy`` over ``bars`` and return trades + equity curve."""
    cfg = config or BacktestConfig()
    strategy.reset()

    position: Position | None = None
    entry_cost = 0.0
    realized = 0.0
    trades: list[Trade] = []
    equity_curve: list[tuple[datetime, float]] = []

    for bar in bars:
        signal = strategy.on_bar(bar, position)

        if signal is not None and signal.type is SignalType.ENTRY and position is None:
            ref_price = signal.price if signal.price is not None else bar.close
            fill = _apply_slippage(ref_price, signal.side, cfg.slippage_bps)
            qty = _size_position(cfg, fill)
            position = Position(
                direction=signal.side,
                quantity=qty,
                entry_price=fill,
                entry_time=bar.time,
            )
            entry_cost = charges_for_fill(signal.side, fill, qty, cfg.product, cfg.costs).total

        elif signal is not None and signal.type is SignalType.EXIT and position is not None:
            exit_side = Side.SELL if position.direction is Side.BUY else Side.BUY
            ref_price = signal.price if signal.price is not None else bar.close
            fill = _apply_slippage(ref_price, exit_side, cfg.slippage_bps)
            exit_cost = charges_for_fill(
                exit_side, fill, position.quantity, cfg.product, cfg.costs
            ).total
            gross = position.sign * (fill - position.entry_price) * position.quantity
            costs = entry_cost + exit_cost
            net = gross - costs
            realized += net
            trades.append(
                Trade(
                    instrument_token=bar.instrument_token,
                    direction=position.direction,
                    quantity=position.quantity,
                    entry_time=position.entry_time,
                    entry_price=position.entry_price,
                    exit_time=bar.time,
                    exit_price=fill,
                    gross_pnl=gross,
                    costs=costs,
                    net_pnl=net,
                    exit_reason=signal.reason,
                )
            )
            position = None
            entry_cost = 0.0

        equity = cfg.initial_capital + realized + _unrealized(position, bar.close)
        equity_curve.append((bar.time, equity))

    final_equity = equity_curve[-1][1] if equity_curve else cfg.initial_capital
    return BacktestResult(
        trades=trades,
        equity_curve=equity_curve,
        initial_capital=cfg.initial_capital,
        final_equity=final_equity,
    )


def equity_values(result: BacktestResult) -> Sequence[float]:
    """Convenience: just the equity numbers from a result."""
    return [value for _, value in result.equity_curve]
