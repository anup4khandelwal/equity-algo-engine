"""Strategy base class and implementations (Phase 3)."""

from .base import Bar, Position, Side, Signal, SignalType, Strategy
from .cross_sectional import momentum_scores, select_top
from .momentum import Momentum
from .orb import OpeningRangeBreakout

__all__ = [
    "Bar",
    "Momentum",
    "OpeningRangeBreakout",
    "Position",
    "Side",
    "Signal",
    "SignalType",
    "Strategy",
    "momentum_scores",
    "select_top",
]
