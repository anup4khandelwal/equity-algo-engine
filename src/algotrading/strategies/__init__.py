"""Strategy base class and implementations (Phase 3, 6, 10)."""

from .base import Bar, Position, Side, Signal, SignalType, Strategy
from .cross_sectional import momentum_scores, select_top
from .ensemble import EnsembleStrategy, Member
from .ma_crossover import MovingAverageCrossover
from .momentum import Momentum
from .orb import OpeningRangeBreakout
from .regime import Regime, RegimeDetector, adx, realized_volatility
from .rsi2 import RSI2
from .supertrend import Supertrend
from .vwap import VWAPReversion

__all__ = [
    "RSI2",
    "Bar",
    "EnsembleStrategy",
    "Member",
    "Momentum",
    "MovingAverageCrossover",
    "OpeningRangeBreakout",
    "Position",
    "Regime",
    "RegimeDetector",
    "Side",
    "Signal",
    "SignalType",
    "Strategy",
    "Supertrend",
    "VWAPReversion",
    "adx",
    "momentum_scores",
    "realized_volatility",
    "select_top",
]
