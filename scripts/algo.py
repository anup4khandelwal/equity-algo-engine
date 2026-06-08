#!/usr/bin/env python3
"""Unified entry point: `algo <command> [args...]`.

Examples:
    uv run python scripts/algo.py backtest --symbol INFY --from 2026-01-01 --to 2026-03-31
    uv run python scripts/algo.py dashboard --demo
    uv run python scripts/algo.py            # list commands

Tip: alias it -> alias algo="uv run python scripts/algo.py"
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from algotrading.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
