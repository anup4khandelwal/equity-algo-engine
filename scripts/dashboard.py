#!/usr/bin/env python3
"""Serve the read-only monitoring dashboard.

Two modes:

  * ``--demo``: replay synthetic ORB bars through the paper engine and serve the
    result — zero setup, no DB or Kite needed. Great for a quick look.
  * default: replay stored 1-minute bars for a symbol/date-range through the
    paper engine, then serve the live engine state (requires the DB + backfill).

Endpoints: /positions /pnl /trades /equity /attribution /health

Example:
    uv run python scripts/dashboard.py --demo
    uv run python scripts/dashboard.py --symbol INFY --from 2026-01-01 --to 2026-03-31
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

# Make `algotrading` (under src/) and `config` (repo root) importable.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from algotrading.api.app import create_app  # noqa: E402
from algotrading.api.service import DashboardState  # noqa: E402
from algotrading.engine import EngineConfig, PaperTradingEngine  # noqa: E402
from algotrading.strategies.base import Bar  # noqa: E402
from algotrading.strategies.orb import OpeningRangeBreakout  # noqa: E402


def _demo_bars(token: int = 256265) -> list[Bar]:
    """A few days of bars that trigger ORB long breakouts and target exits."""
    bars: list[Bar] = []
    for day in (2, 3, 4):
        base = datetime(2026, 6, day, 9, 15)
        spec = [
            (0, 100, 110, 100, 105),  # range build
            (1, 105, 108, 90, 100),  # range build (high 110, low 90)
            (16, 110, 112, 109, 111),  # breakout long
            (17, 111, 131, 110, 130),  # target hit
        ]
        for minute, o, h, low, c in spec:
            bars.append(Bar(token, base + timedelta(minutes=minute), o, h, low, c))
    return bars


def _run_engine(bars: list[Bar], token: int, capital: float) -> PaperTradingEngine:
    engine = PaperTradingEngine(
        OpeningRangeBreakout(token, opening_range_minutes=15),
        config=EngineConfig(capital=capital, use_atr_sizing=False, fixed_quantity=100),
    )
    for bar in bars:
        engine.on_bar(bar)
    return engine


def _load_db_bars(exchange: str, symbol: str, start: date, end: date) -> tuple[list[Bar], int]:
    from algotrading.data.db import session_scope
    from algotrading.data.repositories import InstrumentRepository, OHLCRepository

    with session_scope() as session:
        instrument = InstrumentRepository(session).get_by_symbol(exchange, symbol)
        if instrument is None:
            raise SystemExit(f"{exchange}:{symbol} not found — backfill first.")
        rows = OHLCRepository(session).get_range(
            instrument.instrument_token,
            datetime.combine(start, time.min),
            datetime.combine(end, time.max),
        )
        token = instrument.instrument_token
    bars = [Bar(r.instrument_token, r.time, r.open, r.high, r.low, r.close, r.volume) for r in rows]
    return bars, token


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Serve synthetic demo data.")
    parser.add_argument("--exchange", default="NSE")
    parser.add_argument("--symbol")
    parser.add_argument("--from", dest="from_date")
    parser.add_argument("--to", dest="to_date")
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.demo:
        token = 256265
        engine = _run_engine(_demo_bars(token), token, args.capital)
    else:
        if not (args.symbol and args.from_date and args.to_date):
            print("Provide --symbol/--from/--to, or use --demo.", file=sys.stderr)
            return 2
        bars, token = _load_db_bars(
            args.exchange,
            args.symbol,
            date.fromisoformat(args.from_date),
            date.fromisoformat(args.to_date),
        )
        engine = _run_engine(bars, token, args.capital)

    app = create_app(DashboardState.from_engine(engine))

    import uvicorn

    print(f"Dashboard at http://{args.host}:{args.port}  (Ctrl-C to stop)")
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
