"""Cross-sectional momentum ranking.

Unlike the single-instrument :class:`Strategy` interface, a cross-sectional
strategy ranks *many* instruments against each other at each rebalance and holds
the strongest. These pure helpers do the ranking; the multi-asset simulator in
``backtest/rotation.py`` turns the ranking into trades.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def momentum_scores(history: Mapping[int, Sequence[float]], lookback: int) -> dict[int, float]:
    """Trailing ``lookback``-bar return per instrument.

    Only instruments with at least ``lookback + 1`` observations are scored.
    """
    scores: dict[int, float] = {}
    for token, closes in history.items():
        if len(closes) >= lookback + 1:
            past = closes[-(lookback + 1)]
            if past > 0:
                scores[token] = (closes[-1] - past) / past
    return scores


def select_top(scores: Mapping[int, float], top_n: int, min_score: float = 0.0) -> list[int]:
    """Pick up to ``top_n`` instruments with score strictly above ``min_score``.

    Ties break by token id for determinism.
    """
    eligible = [(token, s) for token, s in scores.items() if s > min_score]
    eligible.sort(key=lambda item: (-item[1], item[0]))
    return [token for token, _ in eligible[:top_n]]
