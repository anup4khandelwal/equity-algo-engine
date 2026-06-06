"""KiteTicker → BarBuilder adapter.

A thin wrapper that subscribes to the websocket tick stream and forwards
completed bars to a callback. ``kiteconnect`` is imported lazily so the rest of
the package (and the tests) never need the live SDK. This adapter is exercised
manually against the live feed, not in CI.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from algotrading.strategies.base import Bar

from .bars import BarBuilder


class KiteTickerFeed:
    """Streams ticks from KiteTicker and emits bars to ``on_bar``."""

    def __init__(
        self,
        api_key: str,
        access_token: str,
        instrument_tokens: Sequence[int],
        on_bar: Callable[[Bar], None],
        *,
        interval_seconds: int = 60,
    ) -> None:
        self.api_key = api_key
        self.access_token = access_token
        self.instrument_tokens = list(instrument_tokens)
        self.on_bar = on_bar
        self._builder = BarBuilder(interval_seconds)
        self._ticker = None

    def _handle_ticks(self, ticks: list[dict]) -> None:
        for tick in ticks:
            token = tick["instrument_token"]
            price = tick.get("last_price")
            if price is None:
                continue
            ts = tick.get("exchange_timestamp") or datetime.now(UTC)
            volume = tick.get("last_traded_quantity", 0) or 0
            bar = self._builder.add_tick(token, float(price), ts, int(volume))
            if bar is not None:
                self.on_bar(bar)

    def start(self) -> None:  # pragma: no cover - requires the live websocket
        from kiteconnect import KiteTicker

        ticker = KiteTicker(self.api_key, self.access_token)
        self._ticker = ticker

        def on_connect(ws, response):  # noqa: ANN001, ARG001
            ws.subscribe(self.instrument_tokens)
            ws.set_mode(ws.MODE_FULL, self.instrument_tokens)

        ticker.on_ticks = lambda ws, ticks: self._handle_ticks(ticks)  # noqa: ARG005
        ticker.on_connect = on_connect
        ticker.connect()

    def flush(self) -> None:
        """Emit any in-progress bars (call at session end)."""
        for bar in self._builder.flush():
            self.on_bar(bar)
