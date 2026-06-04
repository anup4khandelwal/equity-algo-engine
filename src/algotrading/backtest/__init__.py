"""Event-driven simulator, transaction-cost model, and metrics (Phase 3)."""

from .costs import Charges, CostConfig, Product, charges_for_fill
from .metrics import (
    Metrics,
    compute_metrics,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)
from .simulator import BacktestConfig, BacktestResult, Trade, run

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "Charges",
    "CostConfig",
    "Metrics",
    "Product",
    "Trade",
    "charges_for_fill",
    "compute_metrics",
    "max_drawdown",
    "run",
    "sharpe_ratio",
    "sortino_ratio",
]
