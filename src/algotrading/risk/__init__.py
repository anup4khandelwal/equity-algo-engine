"""Position sizing, stop-loss, and daily kill-switch (Phase 4)."""

from .manager import RiskLimits, RiskManager
from .sizing import atr_position_size, average_true_range
from .stops import ProtectiveStops, StopConfig, StopHit

__all__ = [
    "ProtectiveStops",
    "RiskLimits",
    "RiskManager",
    "StopConfig",
    "StopHit",
    "atr_position_size",
    "average_true_range",
]
