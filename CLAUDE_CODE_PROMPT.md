# Claude Code Brief — Indian Equity Algo Trading System (Kite Connect)

> Paste this whole file as your first message to Claude Code in an empty repo.
> It is both the spec and the working agreement. Tell Claude Code to also save
> a condensed version of the "Hard constraints" + "Working style" sections into
> a `CLAUDE.md` at the repo root so it persists across sessions.

---

## Role & goal

You are building a **local-first algorithmic trading system for Indian equities
(NSE/BSE)** that integrates **Zerodha's Kite Connect API**. The system generates
**intraday** and **positional (multi-day)** signals, backtests them against
historical data, and **paper-trades** them against the live market.

Live order execution is intentionally **out of scope for now** (it requires a
registered static IP). But you must **architect for it from day one** through a
clean paper/live execution switch, so enabling live trading later is a config
change, not a rewrite.

This is a solo, personal project. Optimize for correctness, safety, and
incremental verifiable progress — not for scale or multi-tenancy.

---

## Hard constraints (read before writing any code)

1. **Local-first.** Everything runs on my machine. No cloud deployment, no
   Dockerfile for the app itself yet. Stateful services (DB, cache) run via a
   single `docker-compose.yml`; the Python engine runs on the host for fast
   iteration.

2. **Personal use only.** Under SEBI's framework a retail trader operating their
   own/immediate-family account, staying under 10 orders/sec, needs no exchange
   registration. **Do NOT build any multi-client, signal-selling, or
   strategy-distribution features.** No user accounts, no auth-for-others, no
   public signal feed.

3. **Secrets NEVER touch git.**
   - `.gitignore` must cover `.env`, `*.token`, `*.session`, `secrets/`, data
     dumps, notebook outputs, `__pycache__`.
   - Commit a `.env.example` with empty placeholders documenting every required
     variable.
   - Add a `pre-commit` config with `gitleaks` (secret scanning) and `ruff`
     (lint+format). Wire it so it runs on every commit.
   - Read all secrets via `pydantic-settings` from env / `.env`. Never hardcode.

4. **Kite Connect realities** (bake these into the broker layer):
   - Order placement + account APIs are free; market-data APIs need a paid
     subscription on a Connect app. Build assuming I have data access.
   - **Live order placement requires a registered static IP** — this only
     affects live mode, so paper mode is fully usable locally.
   - The **access token expires every morning** and the login flow needs a
     browser redirect. Build a `scripts/refresh_token.py` that automates as much
     of this as possible and stores the token locally (gitignored).
   - Respect rate limits: ~10 req/sec combined across GET endpoints; order
     placement capped at 200/min. Add a token-bucket throttle in the broker
     wrapper.
   - Never redistribute Kite market data outside this local app.

5. **Realistic backtest costs are mandatory.** Every backtest must subtract
   brokerage (Zerodha: ₹20 or 0.03% per executed order, whichever lower; ₹0 for
   equity delivery), STT, exchange transaction charges, SEBI charges, GST, and
   stamp duty, plus a configurable slippage model. Report **net** P&L, not gross.
   A strategy that's only profitable gross is not profitable.

6. **No real orders in this phase, ever.** The `LiveGateway` implementation must
   be a stub that raises `NotImplementedError` until I explicitly ask to enable
   it. All runs default to paper mode.

---

## Tech stack

- **Language:** Python 3.12, managed with `uv` (`pyproject.toml`).
- **Broker SDK:** `kiteconnect` (`KiteConnect` for REST, `KiteTicker` for the
  websocket tick stream).
- **Storage:** PostgreSQL + **TimescaleDB** (use the `timescale/timescaledb`
  image) for OHLC/tick time-series via hypertables + continuous aggregates.
- **Cache / live state:** Redis (positions, signal cache, throttle buckets).
- **ORM / migrations:** SQLAlchemy 2.x + Alembic.
- **Config:** pydantic-settings.
- **Backtesting:** `vectorbt` for fast parameter research; a small custom
  event-driven simulator that **shares the strategy code** with the live engine
  to avoid backtest-vs-live drift.
- **Data/compute:** pandas, numpy, `pandas-ta` (or `ta`) for indicators.
- **API/dashboard (later phase):** FastAPI + uvicorn.
- **Quality:** ruff, pytest, gitleaks, pre-commit.

Ask before adding any dependency not listed here.

---

## Target repo structure

```
algo-trading/
├── .github/workflows/ci.yml
├── .gitignore
├── .env.example
├── .pre-commit-config.yaml
├── CLAUDE.md
├── README.md
├── docker-compose.yml
├── pyproject.toml
├── alembic.ini
├── config/
│   └── settings.py            # pydantic-settings
├── src/algotrading/
│   ├── broker/                # kite wrapper, token refresh, throttle
│   ├── data/                  # ingestion, backfill, db models, repositories
│   ├── strategies/            # Strategy base class + implementations
│   ├── backtest/              # event-driven simulator + cost model + metrics
│   ├── execution/             # OrderGateway interface, PaperGateway, LiveGateway(stub)
│   ├── risk/                  # position sizing, stop-loss, daily kill-switch
│   └── engine.py              # orchestrator (paper/live mode wiring)
├── scripts/
│   ├── refresh_token.py
│   └── backfill.py
├── migrations/                # alembic versions
└── tests/
```

---

## Build order — do these as SEPARATE phases / PRs

Complete one phase fully (code + tests passing + a short note on how to run it)
and **stop for my review before starting the next.**

**Phase 0 — Scaffolding.** Repo skeleton, `pyproject.toml`, `docker-compose.yml`
(TimescaleDB + Redis with healthchecks), `.gitignore`, `.env.example`,
`.pre-commit-config.yaml`, `CLAUDE.md`, `README.md` with setup steps. Verify
`docker compose up` brings both services up healthy.

**Phase 1 — Broker layer + auth.** Kite client wrapper with the rate-limit
throttle, and `scripts/refresh_token.py` for the daily login/token flow. Mock
the Kite API in tests — no live calls in CI.

**Phase 2 — Data layer.** SQLAlchemy models + Alembic migration for instruments
and OHLC bars (TimescaleDB hypertable). `scripts/backfill.py` to pull and store
historical bars. Continuous aggregate to roll 1-min → 5/15/60-min.

**Phase 3 — Strategy framework + backtester.** `Strategy` ABC
(`on_bar`/`generate_signal`/`risk_check`), the event-driven simulator, the full
transaction-cost model, and metrics (net P&L, Sharpe, Sortino, max drawdown,
win rate, turnover). Implement **one** strategy end-to-end: Opening Range
Breakout (intraday). Add a config-driven backtest CLI.

**Phase 4 — Risk + paper execution.** `OrderGateway` interface; `PaperGateway`
(simulated fills against live/last price); `LiveGateway` stub raising
`NotImplementedError`. Risk module: ATR-based sizing, per-trade stop-loss, max
open positions, daily-loss kill-switch, intraday square-off timer.

**Phase 5 — Live paper-trading loop.** Wire `KiteTicker` → strategy engine →
PaperGateway, running during market hours with the square-off scheduler and a
trade log. Optional: a Telegram notifier for fills/errors.

**Phase 6 (later) — FastAPI dashboard.** Read-only views: positions, P&L, trade
log, equity curve, per-strategy attribution. Add a second positional strategy
(e.g. momentum rotation on Nifty 200) once the framework is proven.

---

## Working style (the agreement)

- Work **one phase at a time**; after each, run `ruff` + `pytest`, show me the
  output, and wait for my go-ahead.
- Write tests **alongside** code, not after. Mock all external (Kite) calls.
- Use type hints everywhere and pydantic models for structured data.
- Keep the paper/live boundary clean — only `LiveGateway` ever touches real
  order endpoints, and it stays stubbed.
- Make small, focused commits with clear messages. Open a PR per phase even
  though I'm solo, so the diff is reviewable.
- If a design decision is ambiguous, ask me a focused question rather than
  guessing.
- Never commit secrets or real market data. Confirm `gitleaks` passes before
  every push.

Start with **Phase 0** and stop when it's up and verified.
