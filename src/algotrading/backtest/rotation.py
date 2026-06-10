"""Multi-asset momentum-rotation backtester.

A cross-sectional engine: at each rebalance it ranks instruments by momentum,
holds the top ``top_n`` equally weighted, and rotates out the rest. It books the
full transaction-cost stack (equity *delivery* by default, since this is
positional) and reports **net** P&L. Output is a :class:`BacktestResult`, so the
same :func:`compute_metrics` used for single-asset backtests applies.

A "panel" is a time-ordered sequence of ``(timestamp, {token: close})`` — one
entry per bar/day, holding each instrument's close for that timestamp.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from algotrading.risk.sizing import inverse_vol_weights, return_volatility
from algotrading.strategies.base import Bar, Side
from algotrading.strategies.cross_sectional import momentum_scores, select_top

from .costs import CostConfig, Product, charges_for_fill
from .simulator import BacktestResult, Trade

Panel = Sequence[tuple[datetime, Mapping[int, float]]]


@dataclass(frozen=True)
class RotationConfig:
    """Configuration for a momentum-rotation backtest."""

    lookback: int = 90
    top_n: int = 5
    rebalance_every: int = 21
    initial_capital: float = 1_000_000.0
    product: Product = Product.DELIVERY
    slippage_bps: float = 5.0
    min_momentum: float = 0.0
    weighting: str = "equal"  # "equal" or "inverse_vol" (risk parity)
    vol_lookback: int = 20
    costs: CostConfig = field(default_factory=CostConfig)


@dataclass
class _Holding:
    quantity: int
    entry_price: float
    entry_charges: float


def build_panel(series: Mapping[int, Sequence[Bar]]) -> list[tuple[datetime, dict[int, float]]]:
    """Align per-instrument bar series into a panel keyed by timestamp."""
    by_time: dict[datetime, dict[int, float]] = {}
    for token, bars in series.items():
        for bar in bars:
            by_time.setdefault(bar.time, {})[token] = bar.close
    return [(ts, by_time[ts]) for ts in sorted(by_time)]


class _Book:
    """Mutable holdings + cash, with cost-aware buy/sell that records trades."""

    def __init__(self, cfg: RotationConfig) -> None:
        self.cfg = cfg
        self.cash = cfg.initial_capital
        self.holdings: dict[int, _Holding] = {}
        self.trades: list[Trade] = []

    def _slip(self, price: float, side: Side) -> float:
        factor = self.cfg.slippage_bps / 10_000.0
        return price * (1 + factor) if side is Side.BUY else price * (1 - factor)

    def buy(self, token: int, qty: int, price: float, when: datetime) -> None:
        if qty <= 0:
            return
        fill = self._slip(price, Side.BUY)
        charges = charges_for_fill(Side.BUY, fill, qty, self.cfg.product, self.cfg.costs).total
        self.cash -= fill * qty + charges
        holding = self.holdings.get(token)
        if holding is None:
            self.holdings[token] = _Holding(qty, fill, charges)
        else:
            total = holding.quantity + qty
            holding.entry_price = (holding.entry_price * holding.quantity + fill * qty) / total
            holding.entry_charges += charges
            holding.quantity = total

    def sell(self, token: int, qty: int, price: float, when: datetime, reason: str) -> None:
        holding = self.holdings[token]
        qty = min(qty, holding.quantity)
        if qty <= 0:
            return
        fill = self._slip(price, Side.SELL)
        exit_charges = charges_for_fill(
            Side.SELL, fill, qty, self.cfg.product, self.cfg.costs
        ).total
        self.cash += fill * qty - exit_charges

        # Amortise the buy-side charges across the shares being sold.
        alloc_entry = holding.entry_charges * qty / holding.quantity
        gross = (fill - holding.entry_price) * qty
        costs = exit_charges + alloc_entry
        self.trades.append(
            Trade(
                instrument_token=token,
                direction=Side.BUY,
                quantity=qty,
                entry_time=when,
                entry_price=holding.entry_price,
                exit_time=when,
                exit_price=fill,
                gross_pnl=gross,
                costs=costs,
                net_pnl=gross - costs,
                exit_reason=reason,
            )
        )

        holding.entry_charges -= alloc_entry
        holding.quantity -= qty
        if holding.quantity == 0:
            del self.holdings[token]

    def market_value(self, prices: Mapping[int, float]) -> float:
        return sum(h.quantity * prices.get(t, h.entry_price) for t, h in self.holdings.items())


def run_rotation(panel: Panel, config: RotationConfig | None = None) -> BacktestResult:
    """Run the momentum-rotation backtest over ``panel``."""
    cfg = config or RotationConfig()
    book = _Book(cfg)
    history: dict[int, list[float]] = {}
    last_price: dict[int, float] = {}
    equity_curve: list[tuple[datetime, float]] = []

    for idx, (when, prices) in enumerate(panel):
        for token, price in prices.items():
            if price > 0:
                history.setdefault(token, []).append(price)
                last_price[token] = price

        if idx % cfg.rebalance_every == 0:
            _rebalance(book, history, prices, when, cfg, last_price)

        equity = book.cash + book.market_value(last_price)
        equity_curve.append((when, equity))

    _liquidate(book, panel, last_price)
    if equity_curve:
        equity_curve[-1] = (equity_curve[-1][0], book.cash)

    final_equity = equity_curve[-1][1] if equity_curve else cfg.initial_capital
    return BacktestResult(book.trades, equity_curve, cfg.initial_capital, final_equity)


def _rebalance(
    book: _Book,
    history: dict[int, list[float]],
    prices: Mapping[int, float],
    when: datetime,
    cfg: RotationConfig,
    last_price: Mapping[int, float],
) -> None:
    scores = momentum_scores(history, cfg.lookback)
    tradable = {t: s for t, s in scores.items() if prices.get(t, 0.0) > 0}
    targets = select_top(tradable, cfg.top_n, cfg.min_momentum)

    # Exit holdings that are no longer targets (and are priceable today).
    for token in list(book.holdings):
        if token not in targets and prices.get(token, 0.0) > 0:
            book.sell(token, book.holdings[token].quantity, prices[token], when, "rotate_out")

    if not targets:
        return

    portfolio_value = book.cash + book.market_value(last_price)
    weights = _target_weights(targets, history, cfg)
    for token in targets:
        price = prices[token]
        target_value = portfolio_value * weights[token]
        desired = int(target_value // (price * (1 + cfg.slippage_bps / 10_000.0)))
        current = book.holdings[token].quantity if token in book.holdings else 0
        if desired > current:
            book.buy(token, desired - current, price, when)
        elif desired < current:
            book.sell(token, current - desired, price, when, "rebalance")


def _target_weights(
    targets: list[int], history: dict[int, list[float]], cfg: RotationConfig
) -> dict[int, float]:
    """Capital weights per target: equal, or inverse-vol (risk parity)."""
    if cfg.weighting == "inverse_vol":
        vols = {
            t: max(return_volatility(history.get(t, []), cfg.vol_lookback), 1e-9) for t in targets
        }
        weights = inverse_vol_weights(vols)
        if len(weights) == len(targets):
            return weights
    # Fall back to equal weighting.
    equal = 1.0 / len(targets)
    return {t: equal for t in targets}


def _liquidate(book: _Book, panel: Panel, last_price: Mapping[int, float]) -> None:
    if not panel:
        return
    when, prices = panel[-1]
    for token in list(book.holdings):
        price = prices.get(token) or last_price.get(token) or book.holdings[token].entry_price
        book.sell(token, book.holdings[token].quantity, price, when, "final")
