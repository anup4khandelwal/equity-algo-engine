"""A simple in-memory trade log with optional JSONL persistence."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from algotrading.execution.gateway import Fill

logger = logging.getLogger("algotrading.trade_log")


@dataclass
class TradeLog:
    """Records fills as they happen."""

    fills: list[Fill] = field(default_factory=list)

    def record(self, fill: Fill) -> None:
        self.fills.append(fill)
        logger.info(
            "FILL %s %s x%d @ %.2f (charges %.2f)",
            fill.order.side,
            fill.order.instrument_token,
            fill.quantity,
            fill.fill_price,
            fill.charges,
        )

    def to_jsonl(self, path: str | Path) -> None:
        """Append the recorded fills to a JSONL file."""
        lines = [
            json.dumps(
                {
                    "time": fill.time.isoformat(),
                    "instrument_token": fill.order.instrument_token,
                    "side": fill.order.side.value,
                    "quantity": fill.quantity,
                    "fill_price": fill.fill_price,
                    "charges": fill.charges,
                    "strategy": fill.order.tag,
                    "reason": fill.order.reason,
                }
            )
            for fill in self.fills
        ]
        with Path(path).open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + ("\n" if lines else ""))
