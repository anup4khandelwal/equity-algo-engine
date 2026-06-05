"""Small, dependency-free technical indicators.

Implemented directly (not via pandas-ta) so they are deterministic and trivially
testable; pandas-ta remains available in the ``indicators`` extra for research.
Each function expects enough data and is called by strategies on their own
rolling buffers.
"""

from __future__ import annotations

from collections.abc import Sequence


def sma(values: Sequence[float], period: int) -> float:
    """Simple moving average of the last ``period`` values."""
    window = values[-period:]
    return sum(window) / len(window)


def rsi(values: Sequence[float], period: int) -> float:
    """Relative Strength Index over ``period`` (simple-average variant).

    Returns 100.0 when there are no losses in the window. Requires at least
    ``period + 1`` values.
    """
    window = values[-(period + 1) :]
    gains = 0.0
    losses = 0.0
    for prev, curr in zip(window, window[1:], strict=False):
        change = curr - prev
        if change > 0:
            gains += change
        elif change < 0:
            losses -= change
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)
