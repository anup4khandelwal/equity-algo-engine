# CLAUDE.md — Working agreement & hard constraints

Condensed from `CLAUDE_CODE_PROMPT.md`. This file persists the rules that must
hold across every session. Read it before writing code.

## What this is

A **local-first** algorithmic trading system for **Indian equities (NSE/BSE)**
integrating **Zerodha Kite Connect**. It generates intraday and positional
signals, backtests them with realistic costs, and **paper-trades** against the
live market. Live order execution is **out of scope** but the architecture keeps
a clean paper/live switch so enabling it later is a config change, not a rewrite.
Solo, personal project — optimize for correctness, safety, and incremental
verifiable progress.

## Hard constraints

1. **Local-first.** Everything runs on the host. Stateful services (TimescaleDB,
   Redis) run via a single `docker-compose.yml`; the Python engine runs on the
   host. No cloud deploy, no app Dockerfile yet.
2. **Personal use only.** No multi-client, signal-selling, auth-for-others, or
   public signal feeds. Stay within SEBI's retail self-trading framework
   (<10 orders/sec).
3. **Secrets NEVER touch git.** `.env`, `*.token`, `*.session`, `secrets/`, data
   dumps, and notebook outputs are gitignored. Read all secrets via
   `pydantic-settings` from env/`.env` — never hardcode. `gitleaks` + `ruff` run
   on every commit (pre-commit) and in CI.
4. **Kite Connect realities.** Market-data APIs need a paid subscription; build
   assuming data access. Live order placement needs a registered static IP
   (live mode only). Access token expires every morning —
   `scripts/refresh_token.py` automates the daily login. Respect rate limits
   (~10 req/sec combined GET; 200 orders/min) via a token-bucket throttle. Never
   redistribute Kite market data.
5. **Realistic backtest costs are mandatory.** Every backtest subtracts
   brokerage (Zerodha: ₹20 or 0.03%/order, whichever lower; ₹0 equity delivery),
   STT, exchange charges, SEBI charges, GST, stamp duty, plus configurable
   slippage. Report **net** P&L, never gross.
6. **No real orders, ever, in this phase.** `LiveGateway` raises
   `NotImplementedError` until explicitly enabled. All runs default to paper.

## Tech stack

Python 3.12 (managed with `uv`) · `kiteconnect` (REST + KiteTicker) ·
PostgreSQL + **TimescaleDB** · Redis · SQLAlchemy 2.x + Alembic ·
pydantic-settings · `vectorbt` + a custom event-driven simulator that **shares
strategy code** with the live engine · pandas/numpy/pandas-ta · FastAPI (later) ·
ruff, pytest, gitleaks, pre-commit.

**Ask before adding any dependency not listed above.**

## Working style (the agreement)

- Work **one phase at a time** (see build order in `CLAUDE_CODE_PROMPT.md`).
  After each phase, run `ruff` + `pytest`, show the output, and **wait for
  go-ahead** before starting the next.
- Open a **PR per phase** so the diff is reviewable.
- Write tests **alongside** code. **Mock all Kite calls** — no live API access
  in tests/CI.
- Type hints everywhere; pydantic models for structured data.
- Keep the paper/live boundary clean — only `LiveGateway` touches real order
  endpoints, and it stays stubbed.
- Small, focused commits with clear messages.
- If a design decision is ambiguous, **ask a focused question** rather than
  guessing.
- Never commit secrets or real market data. Confirm `gitleaks` passes before
  every push.

## Common commands

```bash
uv sync                      # install runtime + dev deps
docker compose up -d         # start TimescaleDB + Redis
uv run ruff check . && uv run ruff format --check .
uv run pytest -v
uv run pre-commit install    # wire up commit hooks (once)
```
