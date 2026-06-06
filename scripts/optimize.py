#!/usr/bin/env python3
"""Walk-forward optimization of ORB parameters over stored bars.

Optimises the opening-range minutes and target multiple in-sample and reports
out-of-sample performance, so the numbers aren't curve-fit. Backfill first.

Example:
    uv run python scripts/optimize.py --exchange NSE --symbol INFY \\
        --from 2025-01-01 --to 2026-03-31 --train-days 60 --test-days 20
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from algotrading.backtest.optimize import walk_forward  # noqa: E402
from algotrading.backtest.simulator import BacktestConfig  # noqa: E402
from algotrading.data.db import session_scope  # noqa: E402
from algotrading.data.repositories import InstrumentRepository, OHLCRepository  # noqa: E402
from algotrading.strategies.base import Bar  # noqa: E402
from algotrading.strategies.orb import OpeningRangeBreakout  # noqa: E402


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exchange", default="NSE")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--from", dest="from_date", required=True)
    parser.add_argument("--to", dest="to_date", required=True)
    parser.add_argument("--train-days", type=int, default=60)
    parser.add_argument("--test-days", type=int, default=20)
    parser.add_argument("--capital", type=float, default=100_000.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    start = datetime.combine(date.fromisoformat(args.from_date), time.min)
    end = datetime.combine(date.fromisoformat(args.to_date), time.max)

    with session_scope() as session:
        instrument = InstrumentRepository(session).get_by_symbol(args.exchange, args.symbol)
        if instrument is None:
            print(f"{args.exchange}:{args.symbol} not found — backfill first.", file=sys.stderr)
            return 1
        rows = OHLCRepository(session).get_range(instrument.instrument_token, start, end)
        token = instrument.instrument_token

    if not rows:
        print("No bars found. Backfill first.", file=sys.stderr)
        return 1

    bars = [Bar(r.instrument_token, r.time, r.open, r.high, r.low, r.close, r.volume) for r in rows]

    def factory(params: dict) -> OpeningRangeBreakout:
        return OpeningRangeBreakout(token, **params)

    result = walk_forward(
        bars,
        factory,
        {"opening_range_minutes": [5, 15, 30], "target_multiple": [0.5, 1.0, 2.0]},
        train_days=args.train_days,
        test_days=args.test_days,
        config=BacktestConfig(initial_capital=args.capital),
    )

    print(f"\nWalk-forward — {args.exchange}:{args.symbol}, {len(result.folds)} folds\n")
    for i, fold in enumerate(result.folds, 1):
        print(
            f"Fold {i}: {fold.test_start}..{fold.test_end} "
            f"params={fold.params} "
            f"IS net={fold.in_sample.net_pnl:,.0f} OOS net={fold.out_sample.net_pnl:,.0f}"
        )
    print("\nAggregate out-of-sample:\n")
    print(result.out_sample_metrics.as_table())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
