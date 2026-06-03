"""A thin, rate-limited wrapper around the Kite Connect REST client.

Every outbound call passes through the :class:`RateLimiter` so we stay under
Kite's server-side limits. The underlying client is injectable, which keeps the
wrapper fully unit-testable with a mock — **no live API calls in tests/CI**.

Order-placement methods exist here for completeness, but per the project's
hard constraints only ``LiveGateway`` (Phase 4, currently stubbed) is permitted
to call them. Nothing in paper mode places real orders.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .throttle import RateCategory, RateLimiter
from .token_store import TokenStore

if TYPE_CHECKING:
    from config.settings import Settings


class KiteClient:
    """Rate-limited facade over a ``KiteConnect``-compatible client."""

    def __init__(self, kite: Any, rate_limiter: RateLimiter | None = None) -> None:
        self._kite = kite
        self._rl = rate_limiter or RateLimiter()

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        *,
        token_store: TokenStore | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> KiteClient:
        """Build a client from configuration, applying a stored access token.

        The token is read from the local :class:`TokenStore` first (refreshed
        daily by ``scripts/refresh_token.py``), falling back to
        ``settings.kite_access_token``. The wrapper is usable without a token for
        login, but data/account calls will fail until one is set.
        """
        # Imported lazily so the package imports cleanly without `config` on path.
        from config.settings import get_settings
        from kiteconnect import KiteConnect

        settings = settings or get_settings()
        kite = KiteConnect(api_key=settings.kite_api_key)

        store = token_store or TokenStore()
        stored = store.load()
        access_token = stored.access_token if stored else settings.kite_access_token
        if access_token:
            kite.set_access_token(access_token)

        return cls(kite, rate_limiter=rate_limiter)

    def _call(self, category: RateCategory, method_name: str, *args: Any, **kwargs: Any) -> Any:
        self._rl.acquire(category)
        return getattr(self._kite, method_name)(*args, **kwargs)

    # --- Account ------------------------------------------------------------
    def profile(self) -> Any:
        return self._call(RateCategory.general, "profile")

    def margins(self, segment: str | None = None) -> Any:
        if segment is None:
            return self._call(RateCategory.general, "margins")
        return self._call(RateCategory.general, "margins", segment)

    def positions(self) -> Any:
        return self._call(RateCategory.general, "positions")

    def holdings(self) -> Any:
        return self._call(RateCategory.general, "holdings")

    # --- Instruments --------------------------------------------------------
    def instruments(self, exchange: str | None = None) -> Any:
        if exchange is None:
            return self._call(RateCategory.general, "instruments")
        return self._call(RateCategory.general, "instruments", exchange)

    # --- Market data --------------------------------------------------------
    def ltp(self, instruments: Any) -> Any:
        return self._call(RateCategory.quote, "ltp", instruments)

    def quote(self, instruments: Any) -> Any:
        return self._call(RateCategory.quote, "quote", instruments)

    def ohlc(self, instruments: Any) -> Any:
        return self._call(RateCategory.quote, "ohlc", instruments)

    def historical_data(
        self,
        instrument_token: int,
        from_date: Any,
        to_date: Any,
        interval: str,
        *,
        continuous: bool = False,
        oi: bool = False,
    ) -> Any:
        return self._call(
            RateCategory.historical,
            "historical_data",
            instrument_token,
            from_date,
            to_date,
            interval,
            continuous=continuous,
            oi=oi,
        )

    # --- Orders (LiveGateway only — Phase 4) --------------------------------
    def place_order(self, **kwargs: Any) -> Any:
        return self._call(RateCategory.order, "place_order", **kwargs)

    def modify_order(self, **kwargs: Any) -> Any:
        return self._call(RateCategory.order, "modify_order", **kwargs)

    def cancel_order(self, **kwargs: Any) -> Any:
        return self._call(RateCategory.order, "cancel_order", **kwargs)

    def orders(self) -> Any:
        return self._call(RateCategory.general, "orders")
