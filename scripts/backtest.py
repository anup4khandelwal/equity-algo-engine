#!/usr/bin/env python3
"""Run an Opening Range Breakout backtest over stored 1-minute bars.

Loads bars from the database (backfill them first with scripts/backfill.py),
runs the event-driven simulator with realistic costs, and prints net metrics.

Example:
    uv run python scripts/backtest.py \\
        --exchange NSE --symbol INFY \\
        --from 2026-01-01 --to 2026-03-31 \\
        --or-minutes 15 --target-multiple 1.0 \\
        --capital 100000 --slippage-bps 1
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

from algotrading.backtest.costs import CostConfig, Product  # noqa: E402
from algotrading.backtest.metrics import compute_metrics  # noqa: E402
from algotrading.backtest.simulator import BacktestConfig, run  # noqa: E402
from algotrading.data.db import session_scope  # noqa: E402
from algotrading.data.repositories import (  # noqa: E402
    InstrumentRepository,
    OHLCRepository,
)
from algotrading.strategies.base import Bar  # noqa: E402
from algotrading.strategies.orb import OpeningRangeBreakout  # noqa: E402


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exchange", default="NSE")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--from", dest="from_date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--or-minutes", type=int, default=15)
    parser.add_argument("--target-multiple", type=float, default=1.0)
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--quantity", type=int, default=None)
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument(
        "--product", choices=[p.value for p in Product], default=Product.INTRADAY.value
    )
    parser.add_argument("--corp-actions", help="JSON of corporate actions to back-adjust prices.")
    parser.add_argument(
        "--warn-gaps",
        action="store_true",
        help="Warn about trading days (config/nse_holidays.json) with no bars.",
    )
    parser.add_argument(
        "--monte-carlo",
        type=int,
        default=0,
        metavar="N",
        help="Bootstrap trades N times for a confidence band (0 = off).",
    )
    parser.add_argument(
        "--report", metavar="PATH", help="Write a self-contained HTML report to PATH."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    start = datetime.combine(date.fromisoformat(args.from_date), time.min)
    end = datetime.combine(date.fromisoformat(args.to_date), time.max)

    with session_scope() as session:
        instrument = InstrumentRepository(session).get_by_symbol(args.exchange, args.symbol)
        if instrument is None:
            print(
                f"{args.exchange}:{args.symbol} not found — run scripts/backfill.py first.",
                file=sys.stderr,
            )
            return 1

        rows = OHLCRepository(session).get_range(instrument.instrument_token, start, end)

    if not rows:
        print("No bars found for that range. Backfill first.", file=sys.stderr)
        return 1

    bars = [
        Bar(
            instrument_token=row.instrument_token,
            time=row.time,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
        )
        for row in rows
    ]

    if args.corp_actions:
        from algotrading.data.corporate_actions import (
            adjust_instrument_bars,
            load_corporate_actions,
        )

        actions = load_corporate_actions(args.corp_actions)
        bars = adjust_instrument_bars(bars, actions, instrument.instrument_token)
        print(f"Applied {len(actions)} corporate action(s) (split/bonus adjustment).")

    if args.warn_gaps:
        from pathlib import Path as _Path

        from algotrading.data.calendar import TradingCalendar

        holidays = _Path("config/nse_holidays.json")
        cal = TradingCalendar.from_file(holidays) if holidays.exists() else TradingCalendar()
        present = {b.time.date() for b in bars}
        missing = cal.missing_sessions(
            date.fromisoformat(args.from_date), date.fromisoformat(args.to_date), present
        )
        if missing:
            print(f"Warning: {len(missing)} trading day(s) in range have no bars.", file=sys.stderr)

    strategy = OpeningRangeBreakout(
        instrument.instrument_token,
        opening_range_minutes=args.or_minutes,
        target_multiple=args.target_multiple,
    )
    config = BacktestConfig(
        initial_capital=args.capital,
        product=Product(args.product),
        slippage_bps=args.slippage_bps,
        quantity=args.quantity,
        costs=CostConfig(),
    )

    result = run(strategy, bars, config)
    metrics = compute_metrics(result)

    print(
        f"\nORB backtest — {args.exchange}:{args.symbol} "
        f"({args.from_date} → {args.to_date}), {len(bars)} bars\n"
    )
    print(metrics.as_table())

    if args.monte_carlo > 0:
        from algotrading.backtest.montecarlo import monte_carlo

        mc = monte_carlo(result, n_simulations=args.monte_carlo, seed=42)
        print(f"\nMonte-Carlo bootstrap ({args.monte_carlo} sims):\n")
        print(mc.as_table())

    if args.report:
        from pathlib import Path as _Path

        from algotrading.backtest.report import render_html

        title = f"ORB backtest — {args.exchange}:{args.symbol} ({args.from_date} → {args.to_date})"
        _Path(args.report).write_text(
            render_html(metrics, result.equity_curve, title), encoding="utf-8"
        )
        print(f"\nReport written to {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
