"""Paper-trading orchestrators.

The same :class:`Strategy` objects used in backtests drive these engines; signals
are gated by the :class:`RiskManager`, sized with ATR, executed through an
:class:`OrderGateway` (PaperGateway by default), and booked in a
:class:`Portfolio`. Switching to live is a matter of swapping the gateway — and
``LiveGateway`` stays stubbed.

- :class:`PaperTradingEngine`: one strategy on one instrument.
- :class:`MultiStrategyEngine`: many strategies (one per instrument) sharing a
  single portfolio and risk budget (max-positions and the daily-loss kill-switch
  apply across all of them).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from algotrading.backtest.costs import Product
from algotrading.execution.gateway import (
    Fill,
    Order,
    OrderGateway,
    OrderStatus,
    OrderType,
    PaperGateway,
)
from algotrading.execution.portfolio import Portfolio
from algotrading.live.notifier import LoggingNotifier, Notifier
from algotrading.live.trade_log import TradeLog
from algotrading.risk.manager import RiskManager
from algotrading.risk.sizing import atr_position_size, average_true_range
from algotrading.risk.stops import ProtectiveStops, StopConfig
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
    # Engine-level protective stops (apply to every strategy; None = disabled).
    stop_loss_pct: float | None = None
    trailing_pct: float | None = None


@dataclass
class _OrderRouter:
    """Shared sizing, risk-gating, and execution used by both engines.

    Stateless with respect to prices/positions (those live in the shared
    :class:`Portfolio`), so multiple strategies can route through one instance.
    """

    gateway: OrderGateway
    risk: RiskManager
    portfolio: Portfolio
    notifier: Notifier
    trade_log: TradeLog
    config: EngineConfig
    fill_listener: Callable[[Fill], None] | None = None

    def size(self, bars: Sequence[Bar], price: float) -> int:
        if self.config.fixed_quantity is not None:
            return self.config.fixed_quantity
        if self.config.use_atr_sizing:
            atr = average_true_range(bars, self.config.atr_period)
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

    def execute(self, order: Order, when) -> None:
        fill = self.gateway.place_order(order, now=when)
        if fill.status is OrderStatus.FILLED:
            self.portfolio.apply_fill(fill)
            self.trade_log.record(fill)
            if self.fill_listener is not None:
                self.fill_listener(fill)
            self.notifier.notify(
                f"{fill.order.side} {fill.quantity} {fill.order.instrument_token} "
                f"@ {fill.fill_price:.2f} [{fill.order.tag}]"
            )
        else:
            self.notifier.notify(f"Order {fill.status}: {fill.message}")

    def try_enter(
        self,
        *,
        strategy_name: str,
        bar: Bar,
        signal: Signal,
        bars: Sequence[Bar],
        day_pnl: float,
    ) -> None:
        if not self.risk.can_enter(
            now=signal.time.time(),
            open_positions=self.portfolio.open_position_count(),
            day_pnl=day_pnl,
        ):
            self.notifier.notify(f"Entry blocked by risk for {bar.instrument_token}")
            return
        price = signal.price if signal.price is not None else bar.close
        qty = self.size(bars, price)
        if qty <= 0:
            return
        self.execute(
            Order(
                instrument_token=bar.instrument_token,
                side=signal.side,
                quantity=qty,
                order_type=OrderType.MARKET,
                reference_price=price,
                product=self.config.product,
                tag=strategy_name,
                reason=signal.reason or "entry",
            ),
            bar.time,
        )

    def exit_position(
        self,
        *,
        strategy_name: str,
        bar: Bar,
        position: Position,
        ref_price: float,
        reason: str,
    ) -> None:
        exit_side = Side.SELL if position.direction is Side.BUY else Side.BUY
        self.execute(
            Order(
                instrument_token=bar.instrument_token,
                side=exit_side,
                quantity=position.quantity,
                order_type=OrderType.MARKET,
                reference_price=ref_price,
                product=self.config.product,
                tag=strategy_name,
                reason=reason,
            ),
            bar.time,
        )


def _process_bar(
    *,
    router: _OrderRouter,
    strategy: Strategy,
    bar: Bar,
    bars: list[Bar],
    last_prices: dict[int, float],
    stops: ProtectiveStops | None = None,
) -> None:
    """Route one bar for one strategy through risk → execution (shared logic)."""
    token = bar.instrument_token
    position = router.portfolio.positions.get(token)

    # Engine-level protective stops take precedence over the strategy's logic.
    if position is None:
        if stops is not None:
            stops.on_close(token)
    elif stops is not None:
        hit = stops.update_and_check(token, position, bar)
        if hit is not None:
            router.exit_position(
                strategy_name=strategy.name,
                bar=bar,
                position=position,
                ref_price=hit.price,
                reason=hit.reason,
            )
            stops.on_close(token)
            return

    signal = strategy.on_bar(bar, position)

    if position is not None and router.risk.should_square_off(bar.time.time()):
        if signal is None or signal.type is not SignalType.EXIT:
            router.exit_position(
                strategy_name=strategy.name,
                bar=bar,
                position=position,
                ref_price=bar.close,
                reason="square_off",
            )
            return

    if signal is None:
        return
    if signal.type is SignalType.ENTRY and position is None:
        router.try_enter(
            strategy_name=strategy.name,
            bar=bar,
            signal=signal,
            bars=bars,
            day_pnl=router.portfolio.day_pnl(last_prices),
        )
    elif signal.type is SignalType.EXIT and position is not None:
        router.exit_position(
            strategy_name=strategy.name,
            bar=bar,
            position=position,
            ref_price=signal.price if signal.price is not None else bar.close,
            reason=signal.reason or "exit",
        )


def _build_stops(config: EngineConfig) -> ProtectiveStops | None:
    cfg = StopConfig(config.stop_loss_pct, config.trailing_pct)
    return ProtectiveStops(cfg) if cfg.enabled else None


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
    fill_listener: Callable[[Fill], None] | None = None

    def __post_init__(self) -> None:
        self._router = _OrderRouter(
            self.gateway,
            self.risk,
            self.portfolio,
            self.notifier,
            self.trade_log,
            self.config,
            self.fill_listener,
        )
        self._stops = _build_stops(self.config)
        self._bars: list[Bar] = []
        self._date = None
        self.equity_curve: list[tuple] = []
        self.last_prices: dict[int, float] = {}

    def on_bar(self, bar: Bar) -> None:
        """Process one completed bar end-to-end."""
        if self._date != bar.time.date():
            self._date = bar.time.date()
            self.risk.reset_day()

        self._bars.append(bar)
        if len(self._bars) > self.config.history_size:
            self._bars = self._bars[-self.config.history_size :]
        self.last_prices[bar.instrument_token] = bar.close

        _process_bar(
            router=self._router,
            strategy=self.strategy,
            bar=bar,
            bars=self._bars,
            last_prices=self.last_prices,
            stops=self._stops,
        )

        day_pnl = self.portfolio.day_pnl(self.last_prices)
        self.risk.update_pnl(day_pnl)
        self.equity_curve.append((bar.time, self.config.capital + day_pnl))


@dataclass
class MultiStrategyEngine:
    """Runs several strategies (one per instrument) sharing one portfolio and
    risk budget. Max-open-positions and the daily-loss kill-switch span every
    strategy, so the book can't exceed the configured limits in aggregate."""

    gateway: OrderGateway = field(default_factory=PaperGateway)
    risk: RiskManager = field(default_factory=RiskManager)
    portfolio: Portfolio = field(default_factory=Portfolio)
    notifier: Notifier = field(default_factory=LoggingNotifier)
    trade_log: TradeLog = field(default_factory=TradeLog)
    config: EngineConfig = field(default_factory=EngineConfig)
    fill_listener: Callable[[Fill], None] | None = None

    def __post_init__(self) -> None:
        self._router = _OrderRouter(
            self.gateway,
            self.risk,
            self.portfolio,
            self.notifier,
            self.trade_log,
            self.config,
            self.fill_listener,
        )
        self._stops = _build_stops(self.config)
        self._strategies: dict[int, Strategy] = {}
        self._history: dict[int, list[Bar]] = {}
        self._date = None
        self.equity_curve: list[tuple] = []
        self.last_prices: dict[int, float] = {}

    def add_strategy(self, strategy: Strategy, instrument_token: int | None = None) -> None:
        """Register a strategy for an instrument (one strategy per instrument)."""
        token = instrument_token
        if token is None:
            token = getattr(strategy, "instrument_token", None)
        if token is None:
            raise ValueError("instrument_token is required (strategy has no .instrument_token)")
        if token in self._strategies:
            raise ValueError(f"a strategy is already registered for instrument {token}")
        self._strategies[token] = strategy
        self._history[token] = []

    def on_bar(self, bar: Bar) -> None:
        """Route a bar to the strategy registered for its instrument."""
        if self._date != bar.time.date():
            self._date = bar.time.date()
            self.risk.reset_day()

        self.last_prices[bar.instrument_token] = bar.close
        strategy = self._strategies.get(bar.instrument_token)
        if strategy is not None:
            history = self._history[bar.instrument_token]
            history.append(bar)
            if len(history) > self.config.history_size:
                del history[: -self.config.history_size]
            _process_bar(
                router=self._router,
                strategy=strategy,
                bar=bar,
                bars=history,
                last_prices=self.last_prices,
                stops=self._stops,
            )

        day_pnl = self.portfolio.day_pnl(self.last_prices)
        self.risk.update_pnl(day_pnl)
        self.equity_curve.append((bar.time, self.config.capital + day_pnl))
