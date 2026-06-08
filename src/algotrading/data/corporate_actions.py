"""Corporate-action price adjustment.

Positional backtests on raw prices are wrong across splits/bonuses: a 1:5 split
looks like an 80% crash and corrupts momentum/returns. We back-adjust historical
prices by a cumulative ratio applied to every bar *before* each ex-date, and
adjust volume inversely so traded value is preserved.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from algotrading.strategies.base import Bar


@dataclass(frozen=True)
class CorporateAction:
    """An adjustment event. ``ratio`` multiplies prices *before* ``ex_date``."""

    instrument_token: int
    ex_date: date
    ratio: float
    kind: str = "split"  # split | bonus | dividend (informational)


def split_action(token: int, ex_date: date, old: int, new: int) -> CorporateAction:
    """Stock split where ``old`` shares become ``new`` (e.g. 1 -> 5)."""
    if old <= 0 or new <= 0:
        raise ValueError("old/new must be positive")
    return CorporateAction(token, ex_date, old / new, "split")


def bonus_action(token: int, ex_date: date, held: int, bonus: int) -> CorporateAction:
    """Bonus issue of ``bonus`` new shares for every ``held`` held (e.g. 1:1)."""
    if held <= 0 or bonus <= 0:
        raise ValueError("held/bonus must be positive")
    return CorporateAction(token, ex_date, held / (held + bonus), "bonus")


def load_corporate_actions(path: str | Path) -> list[CorporateAction]:
    """Load corporate actions from JSON.

    Accepts a bare list, or an object with an ``actions`` list. Each record:
    ``{"instrument_token", "ex_date" (YYYY-MM-DD), "ratio", "kind"?}``.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data["actions"] if isinstance(data, dict) else data
    return [
        CorporateAction(
            instrument_token=int(r["instrument_token"]),
            ex_date=date.fromisoformat(r["ex_date"]),
            ratio=float(r["ratio"]),
            kind=str(r.get("kind", "split")),
        )
        for r in items
    ]


def adjust_instrument_bars(
    bars: Sequence[Bar], actions: Sequence[CorporateAction], instrument_token: int
) -> list[Bar]:
    """Apply only the actions for ``instrument_token`` (no-op if none apply)."""
    relevant = [a for a in actions if a.instrument_token == instrument_token]
    return adjust_bars(bars, relevant) if relevant else list(bars)


def adjust_bars(bars: Sequence[Bar], actions: Sequence[CorporateAction]) -> list[Bar]:
    """Return back-adjusted bars. Prices scale by the cumulative pre-ex ratio."""
    acts = sorted(actions, key=lambda a: a.ex_date)
    adjusted: list[Bar] = []
    for bar in bars:
        factor = 1.0
        for action in acts:
            if bar.time.date() < action.ex_date:
                factor *= action.ratio
        adjusted.append(
            Bar(
                instrument_token=bar.instrument_token,
                time=bar.time,
                open=bar.open * factor,
                high=bar.high * factor,
                low=bar.low * factor,
                close=bar.close * factor,
                volume=int(bar.volume / factor) if factor else bar.volume,
            )
        )
    return adjusted
