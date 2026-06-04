#!/usr/bin/env python3
"""Run the live paper-trading loop for one instrument (ORB strategy).

Streams the Kite tick feed into the engine, which paper-trades via the
PaperGateway. No real orders are ever placed. Requires a valid access token
(run scripts/refresh_token.py first) and a market-data subscription.

Example:
    uv run python scripts/paper_trade.py --exchange NSE --symbol INFY
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Make `algotrading` (under src/) and `config` (repo root) importable.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from config.settings import get_settings  # noqa: E402

from algotrading.data.db import session_scope  # noqa: E402
from algotrading.data.repositories import InstrumentRepository  # noqa: E402
from algotrading.engine import EngineConfig, PaperTradingEngine  # noqa: E402
from algotrading.live.feed import KiteTickerFeed  # noqa: E402
from algotrading.strategies.orb import OpeningRangeBreakout  # noqa: E402


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exchange", default="NSE")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--or-minutes", type=int, default=15)
    parser.add_argument("--capital", type=float, default=100_000.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args(argv)
    settings = get_settings()

    if settings.kite_access_token is None:
        print("No access token — run scripts/refresh_token.py first.", file=sys.stderr)
        return 1

    with session_scope() as session:
        instrument = InstrumentRepository(session).get_by_symbol(args.exchange, args.symbol)
        if instrument is None:
            print(
                f"{args.exchange}:{args.symbol} not found — run scripts/backfill.py "
                "--sync-instruments first.",
                file=sys.stderr,
            )
            return 1
        token = instrument.instrument_token

    engine = PaperTradingEngine(
        OpeningRangeBreakout(token, opening_range_minutes=args.or_minutes),
        config=EngineConfig(capital=args.capital),
    )

    feed = KiteTickerFeed(
        api_key=settings.kite_api_key,
        access_token=settings.kite_access_token,
        instrument_tokens=[token],
        on_bar=engine.on_bar,
    )
    print(f"Paper-trading {args.exchange}:{args.symbol} (token {token}). Ctrl-C to stop.")
    feed.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
