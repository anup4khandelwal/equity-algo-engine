"""Event-driven simulator, transaction-cost model, and metrics (Phase 3)."""

from .costs import Charges, CostConfig, Product, charges_for_fill
from .metrics import (
    BenchmarkStats,
    Metrics,
    compare_to_benchmark,
    compute_metrics,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)
from .optimize import (
    Fold,
    WalkForwardResult,
    expand_grid,
    grid_search,
    walk_forward,
)
from .rotation import RotationConfig, build_panel, run_rotation
from .simulator import BacktestConfig, BacktestResult, Trade, run

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "BenchmarkStats",
    "Charges",
    "CostConfig",
    "Fold",
    "Metrics",
    "Product",
    "RotationConfig",
    "Trade",
    "WalkForwardResult",
    "build_panel",
    "charges_for_fill",
    "compare_to_benchmark",
    "compute_metrics",
    "expand_grid",
    "grid_search",
    "max_drawdown",
    "run",
    "run_rotation",
    "sharpe_ratio",
    "sortino_ratio",
    "walk_forward",
]
