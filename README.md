# equity-algo-engine

A **local-first** algorithmic trading system for **Indian equities (NSE/BSE)**
built on **Zerodha Kite Connect**. It generates intraday and positional signals,
backtests them with realistic transaction costs, and **paper-trades** them
against the live market.

> ⚠️ Live order execution is intentionally **out of scope** for now (it requires
> a registered static IP). The system runs in **paper mode** by default. See
> [`CLAUDE.md`](./CLAUDE.md) for the full working agreement and hard constraints,
> and [`CLAUDE_CODE_PROMPT.md`](./CLAUDE_CODE_PROMPT.md) for the complete brief
> and phased build order.

## Status

All phases from the brief are implemented:

- **Phase 0 — Scaffolding** — repo skeleton, env, tooling.
- **Phase 1 — Broker layer + auth** — rate-limited Kite client, daily token refresh.
- **Phase 2 — Data layer** — TimescaleDB hypertable + continuous aggregates, repositories, backfill.
- **Phase 3 — Strategy framework + backtester** — event-driven simulator, full cost model (net P&L), metrics, Opening Range Breakout.
- **Phase 4 — Risk + paper execution** — `OrderGateway`/`PaperGateway`/`LiveGateway` (stub), ATR sizing, kill-switch, square-off.
- **Phase 5 — Live paper-trading loop** — tick→bar aggregation, engine, trade log, notifier.
- **Phase 6 — Dashboard + second strategy** — read-only FastAPI views and a positional Momentum strategy.

Live order execution remains **stubbed** (`LiveGateway` raises `NotImplementedError`).

### Backtest a strategy

```bash
# Intraday Opening Range Breakout (single instrument)
uv run python scripts/backtest.py --exchange NSE --symbol INFY \
    --from 2026-01-01 --to 2026-03-31 --or-minutes 15

# Cross-sectional momentum rotation (multi-asset, positional)
uv run python scripts/rotation_backtest.py --exchange NSE \
    --symbols INFY,TCS,RELIANCE,HDFCBANK,ITC,SBIN \
    --from 2025-01-01 --to 2026-03-31 --lookback 90 --top-n 3 --rebalance-every 21
```

Strategies: `OpeningRangeBreakout` (intraday), `Momentum` (single-name
positional), and a cross-sectional momentum **rotation** backtester
(`backtest.run_rotation`) that ranks a universe and holds the top names.

### Serve the read-only dashboard

```bash
# Zero-setup demo (synthetic data, no DB/Kite):
uv run python scripts/dashboard.py --demo
# Or replay stored bars through the paper engine:
uv run python scripts/dashboard.py --symbol INFY --from 2026-01-01 --to 2026-03-31
```

Endpoints: `GET /positions /pnl /trades /equity /attribution /health`. Build a
state programmatically with `DashboardState.from_engine(engine)`.

## Requirements

- Python **3.12**
- [`uv`](https://docs.astral.sh/uv/) for dependency/environment management
- Docker + Docker Compose (for TimescaleDB and Redis)

## Setup

```bash
# 1. Install dependencies (runtime + dev) into a managed virtualenv
uv sync

# 2. Configure secrets and connection strings
cp .env.example .env
#   then edit .env and fill in your Kite Connect API key/secret

# 3. Start the stateful services (TimescaleDB + Redis)
docker compose up -d

# 4. Wire up the commit hooks (gitleaks + ruff)
uv run pre-commit install
```

### Verify the services are healthy

```bash
docker compose ps        # both services should report (healthy)
```

## Development

```bash
uv run ruff check .              # lint
uv run ruff format --check .     # format check
uv run pytest -v                 # tests
```

CI (`.github/workflows/ci.yml`) runs gitleaks secret scanning, ruff, and pytest
against a real TimescaleDB + Redis on every push/PR to `main`. All Kite/broker
calls are mocked — **no live API access in CI**.

## Project layout

```
.
├── config/                 # pydantic-settings configuration
├── src/algotrading/
│   ├── broker/             # Kite wrapper, token refresh, throttle   (Phase 1)
│   ├── data/               # ingestion, backfill, DB models          (Phase 2)
│   ├── strategies/         # Strategy base class + implementations   (Phase 3)
│   ├── backtest/           # event-driven simulator + cost model     (Phase 3)
│   ├── execution/          # OrderGateway, PaperGateway, LiveGateway  (Phase 4)
│   ├── risk/               # sizing, stop-loss, kill-switch           (Phase 4)
│   └── engine.py           # orchestrator (paper/live wiring)
├── scripts/                # refresh_token.py, backfill.py
├── migrations/             # alembic versions
└── tests/
```

## Safety & compliance

- **Personal use only** — no multi-client, signal-selling, or distribution
  features.
- **Secrets never touch git** — `.env`, tokens, sessions, and data dumps are
  gitignored; gitleaks enforces this on every commit and in CI.
- **Backtests report net P&L** after brokerage, STT, exchange/SEBI charges, GST,
  stamp duty, and slippage.
- **No real orders** — `LiveGateway` stays stubbed until explicitly enabled.
