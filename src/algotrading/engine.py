"""Paper-trading orchestrator.

Ties the feed → strategy → risk → execution chain together. The same
:class:`Strategy` used in backtests drives this engine; signals are gated by the
:class:`RiskManager`, sized with ATR, executed through an
:class:`OrderGateway` (PaperGateway by default), and booked in a
:class:`Portfolio`. Switching to live is a matter of swapping the gateway — and
``LiveGateway`` stays stubbed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from algotrading.backtest.costs import Product
from algotrading.execution.gateway import Order, OrderGateway, OrderStatus, OrderType, PaperGateway
from algotrading.execution.portfolio import Portfolio
from algotrading.live.notifier import LoggingNotifier, Notifier
from algotrading.live.trade_log import TradeLog
from algotrading.risk.manager import RiskManager
from algotrading.risk.sizing import atr_position_size, average_true_range
from algotrading.strategies.base import Bar, Position, Side, Signal, SignalType, Strategy


@dataclass
class EngineConfig:
    """Engine sizing/execution configuration."""

    capital: float = 100_000.0
    product: Product = Product.INTRADAY
    use_atr_sizing: bool = True
    risk_per_trade: float = 0.01
    atr_period: int = 14
    atr_stop_multiple: float = 1.5
    fixed_quantity: int | None = None
    history_size: int = 200


@dataclass
class PaperTradingEngine:
    """Single-strategy paper-trading engine driven bar by bar."""

    strategy: Strategy
    gateway: OrderGateway = field(default_factory=PaperGateway)
    risk: RiskManager = field(default_factory=RiskManager)
    portfolio: Portfolio = field(default_factory=Portfolio)
    notifier: Notifier = field(default_factory=LoggingNotifier)
    trade_log: TradeLog = field(default_factory=TradeLog)
    config: EngineConfig = field(default_factory=EngineConfig)

    def __post_init__(self) -> None:
        self._bars: list[Bar] = []
        self._date = None
        # Recorded for the dashboard (Phase 6).
        self.equity_curve: list[tuple] = []
        self.last_prices: dict[int, float] = {}

    def _position(self, token: int) -> Position | None:
        return self.portfolio.positions.get(token)

    def on_bar(self, bar: Bar) -> None:
        """Process one completed bar end-to-end."""
        if self._date != bar.time.date():
            self._date = bar.time.date()
            self.risk.reset_day()

        self._bars.append(bar)
        if len(self._bars) > self.config.history_size:
            self._bars = self._bars[-self.config.history_size :]

        now_t = bar.time.time()
        position = self._position(bar.instrument_token)
        signal = self.strategy.on_bar(bar, position)

        # Enforce square-off independently of the strategy.
        if position is not None and self.risk.should_square_off(now_t):
            if signal is None or signal.type is not SignalType.EXIT:
                self._flatten(bar, position, reason="square_off")
                return

        if signal is not None:
            self._handle_signal(signal, bar, position)

        self.last_prices[bar.instrument_token] = bar.close
        day_pnl = self.portfolio.day_pnl(self.last_prices)
        self.risk.update_pnl(day_pnl)
        self.equity_curve.append((bar.time, self.config.capital + day_pnl))

    def _handle_signal(self, signal: Signal, bar: Bar, position: Position | None) -> None:
        if signal.type is SignalType.ENTRY and position is None:
            day_pnl = self.portfolio.day_pnl({bar.instrument_token: bar.close})
            if not self.risk.can_enter(
                now=signal.time.time(),
                open_positions=self.portfolio.open_position_count(),
                day_pnl=day_pnl,
            ):
                self.notifier.notify(f"Entry blocked by risk for {bar.instrument_token}")
                return
            qty = self._size(bar, signal)
            if qty <= 0:
                return
            self._execute(
                Order(
                    instrument_token=bar.instrument_token,
                    side=signal.side,
                    quantity=qty,
                    order_type=OrderType.MARKET,
                    reference_price=signal.price if signal.price is not None else bar.close,
                    product=self.config.product,
                    tag=self.strategy.name,
                ),
                bar,
            )
        elif signal.type is SignalType.EXIT and position is not None:
            exit_side = Side.SELL if position.direction is Side.BUY else Side.BUY
            self._execute(
                Order(
                    instrument_token=bar.instrument_token,
                    side=exit_side,
                    quantity=position.quantity,
                    order_type=OrderType.MARKET,
                    reference_price=signal.price if signal.price is not None else bar.close,
                    product=self.config.product,
                    tag=signal.reason,
                ),
                bar,
            )

    def _flatten(self, bar: Bar, position: Position, reason: str) -> None:
        exit_side = Side.SELL if position.direction is Side.BUY else Side.BUY
        self._execute(
            Order(
                instrument_token=bar.instrument_token,
                side=exit_side,
                quantity=position.quantity,
                order_type=OrderType.MARKET,
                reference_price=bar.close,
                product=self.config.product,
                tag=reason,
            ),
            bar,
        )

    def _execute(self, order: Order, bar: Bar) -> None:
        fill = self.gateway.place_order(order, now=bar.time)
        if fill.status is OrderStatus.FILLED:
            self.portfolio.apply_fill(fill)
            self.trade_log.record(fill)
            self.notifier.notify(
                f"{fill.order.side} {fill.quantity} {fill.order.instrument_token} "
                f"@ {fill.fill_price:.2f} [{fill.order.tag}]"
            )
        else:
            self.notifier.notify(f"Order {fill.status}: {fill.message}")

    def _size(self, bar: Bar, signal: Signal) -> int:
        price = signal.price if signal.price is not None else bar.close
        if self.config.fixed_quantity is not None:
            return self.config.fixed_quantity
        if self.config.use_atr_sizing:
            atr = average_true_range(self._bars, self.config.atr_period)
            qty = atr_position_size(
                self.config.capital,
                self.config.risk_per_trade,
                atr,
                atr_stop_multiple=self.config.atr_stop_multiple,
                price=price,
                max_notional=self.config.capital,
            )
            if qty > 0:
                return qty
        return max(1, int(self.config.capital // price))
