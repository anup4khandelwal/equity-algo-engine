#!/usr/bin/env python3
"""Backfill instruments and historical 1-minute bars from Kite into the DB.

Examples:
    # Refresh the instrument master, then backfill two symbols:
    uv run python scripts/backfill.py --sync-instruments \\
        --exchange NSE --symbols INFY,RELIANCE \\
        --from 2026-01-01 --to 2026-03-31

    # Just refresh the instrument master:
    uv run python scripts/backfill.py --sync-instruments --exchange NSE

All Kite calls go through the rate-limited KiteClient.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# Make `algotrading` (under src/) and `config` (repo root) importable.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from algotrading.broker.client import KiteClient  # noqa: E402
from algotrading.data.backfill import backfill_bars, sync_instruments  # noqa: E402
from algotrading.data.db import session_scope  # noqa: E402
from algotrading.data.repositories import (  # noqa: E402
    InstrumentRepository,
    OHLCRepository,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sync-instruments",
        action="store_true",
        help="Refresh the instrument master before backfilling.",
    )
    parser.add_argument("--exchange", default="NSE", help="Exchange (default: NSE).")
    parser.add_argument(
        "--symbols",
        default="",
        help="Comma-separated trading symbols to backfill (e.g. INFY,RELIANCE).",
    )
    parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD).")
    parser.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD).")
    parser.add_argument("--interval", default="minute", help="Kite interval (default: minute).")
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=60,
        help="Max days per Kite request (default: 60).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    if symbols and not (args.from_date and args.to_date):
        print("Error: --from and --to are required when backfilling symbols.", file=sys.stderr)
        return 2

    client = KiteClient.from_settings()

    with session_scope() as session:
        if args.sync_instruments:
            count = sync_instruments(client, InstrumentRepository(session), args.exchange)
            print(f"Synced {count} instruments for {args.exchange}.")

        if not symbols:
            return 0

        start = date.fromisoformat(args.from_date)
        end = date.fromisoformat(args.to_date)
        instrument_repo = InstrumentRepository(session)
        ohlc_repo = OHLCRepository(session)

        for symbol in symbols:
            instrument = instrument_repo.get_by_symbol(args.exchange, symbol)
            if instrument is None:
                print(
                    f"  {args.exchange}:{symbol} not found — run with --sync-instruments first.",
                    file=sys.stderr,
                )
                continue
            stored = backfill_bars(
                client,
                ohlc_repo,
                instrument.instrument_token,
                start,
                end,
                interval=args.interval,
                chunk_days=args.chunk_days,
            )
            print(f"  {args.exchange}:{symbol}: stored {stored} bars.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
