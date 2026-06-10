#!/usr/bin/env python3
"""Backtest the cross-sectional momentum-rotation strategy over stored bars.

Ranks the given universe by trailing momentum and holds the top names, rotating
on a fixed cadence. Reports net-of-cost metrics. Backfill the symbols first.

Example:
    uv run python scripts/rotation_backtest.py --exchange NSE \\
        --symbols INFY,TCS,RELIANCE,HDFCBANK,ITC,SBIN \\
        --from 2025-01-01 --to 2026-03-31 \\
        --lookback 90 --top-n 3 --rebalance-every 21
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time
from pathlib import Path

# Make `algotrading` (under src/) and `config` (repo root) importable.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from algotrading.backtest.metrics import compute_metrics  # noqa: E402
from algotrading.backtest.rotation import RotationConfig, build_panel, run_rotation  # noqa: E402
from algotrading.data.db import session_scope  # noqa: E402
from algotrading.data.repositories import InstrumentRepository, OHLCRepository  # noqa: E402
from algotrading.strategies.base import Bar  # noqa: E402


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exchange", default="NSE")
    parser.add_argument("--symbols", required=True, help="Comma-separated universe.")
    parser.add_argument("--from", dest="from_date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--lookback", type=int, default=90)
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--rebalance-every", type=int, default=21)
    parser.add_argument("--capital", type=float, default=1_000_000.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument(
        "--weighting",
        choices=["equal", "inverse_vol"],
        default="equal",
        help="Capital allocation: equal-weight or inverse-vol (risk parity).",
    )
    parser.add_argument("--vol-lookback", type=int, default=20)
    parser.add_argument("--corp-actions", help="JSON of corporate actions to back-adjust prices.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    start = datetime.combine(date.fromisoformat(args.from_date), time.min)
    end = datetime.combine(date.fromisoformat(args.to_date), time.max)

    series: dict[int, list[Bar]] = {}
    with session_scope() as session:
        instruments = InstrumentRepository(session)
        ohlc = OHLCRepository(session)
        for symbol in symbols:
            instrument = instruments.get_by_symbol(args.exchange, symbol)
            if instrument is None:
                print(f"  {args.exchange}:{symbol} not found — skipping.", file=sys.stderr)
                continue
            rows = ohlc.get_range(instrument.instrument_token, start, end)
            series[instrument.instrument_token] = [
                Bar(r.instrument_token, r.time, r.open, r.high, r.low, r.close, r.volume)
                for r in rows
            ]

    if not series:
        print("No data for the requested universe. Backfill first.", file=sys.stderr)
        return 1

    if args.corp_actions:
        from algotrading.data.corporate_actions import (
            adjust_instrument_bars,
            load_corporate_actions,
        )

        actions = load_corporate_actions(args.corp_actions)
        series = {t: adjust_instrument_bars(b, actions, t) for t, b in series.items()}
        print(f"Applied {len(actions)} corporate action(s) across the universe.")

    panel = build_panel(series)
    config = RotationConfig(
        lookback=args.lookback,
        top_n=args.top_n,
        rebalance_every=args.rebalance_every,
        initial_capital=args.capital,
        slippage_bps=args.slippage_bps,
        weighting=args.weighting,
        vol_lookback=args.vol_lookback,
    )
    result = run_rotation(panel, config)
    metrics = compute_metrics(result)

    print(
        f"\nMomentum rotation — {len(series)} names "
        f"({args.from_date} → {args.to_date}), top {args.top_n}, "
        f"lookback {args.lookback}, rebalance every {args.rebalance_every}\n"
    )
    print(metrics.as_table())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
