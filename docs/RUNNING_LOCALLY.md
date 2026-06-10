# Running locally

A step-by-step guide to running **equity-algo-engine** on your own machine. It is
**local-first** and **paper-only** — no cloud, and no real orders are ever placed
(`LiveGateway` is a stub).

> ⚠️ All commands run on **your machine**. Secrets live in a gitignored `.env`
> and never leave your host.

---

## 1. Prerequisites

| Tool | Why | Install |
|---|---|---|
| **Python 3.12** | the engine | via `uv` (below) |
| [**uv**](https://docs.astral.sh/uv/) | deps + venv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Docker + Compose** | TimescaleDB + Redis | [docs.docker.com](https://docs.docker.com/get-docker/) |
| **Node 22 + npm** | the Next.js dashboard (optional) | [nodejs.org](https://nodejs.org/) |

A **Zerodha Kite Connect** subscription is only needed for *real* data
(backfill / live paper-trading). You can explore the backtester and dashboard
**without Kite** using synthetic/demo data.

---

## 2. Clone & install

```bash
git clone https://github.com/anup4khandelwal/equity-algo-engine.git
cd equity-algo-engine
uv sync                 # runtime + dev deps
uv sync --extra api     # add FastAPI/uvicorn for the dashboard API
uv run pre-commit install   # wire gitleaks + ruff hooks (once)
```

### Fastest "see it work" (no DB, no Kite)

```bash
uv run python scripts/dashboard.py --demo   # serves API on http://127.0.0.1:8000
```
Open `http://127.0.0.1:8000/pnl` (and `/positions /trades /equity /attribution
/candles /regimes /strategy-pnl /closed-trades /health`). For the full UI, see
[§8](#8-web-dashboard-nextjs).

---

## 3. Start the databases

```bash
docker compose up -d        # TimescaleDB :5432, Redis :6379
docker compose ps           # both should report (healthy)
```

`docker-compose.yml` uses `algo/algo/algo` by default — matching `.env.example`.

---

## 4. Configure secrets

```bash
cp .env.example .env
```
Edit `.env`:

```ini
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret           # regenerate if ever exposed
KITE_ACCESS_TOKEN=                         # filled by refresh_token.py
DATABASE_URL=postgresql+psycopg://algo:algo@localhost:5432/algo
REDIS_URL=redis://localhost:6379/0
TRADING_MODE=paper                         # paper is the only supported mode
```

`.env` is gitignored; `gitleaks` blocks it from ever being committed.

---

## 5. Create the schema

```bash
uv run alembic upgrade head     # instruments, ohlc_bars hypertable, aggregates, fills
```

---

## 6. Daily Kite login (token refresh)

The Kite access token expires every morning:

```bash
uv run python scripts/refresh_token.py
```
Opens the login URL, you paste the redirect, and it stores the token in
`secrets/kite_token.json` (gitignored).

---

## 7. The workflow (CLIs)

Every tool is reachable through the unified **`algo`** command:

```bash
uv run python scripts/algo.py            # list commands
# optional alias:
alias algo="uv run python scripts/algo.py"
```

### a) Backfill history

```bash
algo backfill --sync-instruments --exchange NSE \
  --symbols INFY,TCS,RELIANCE \
  --from 2026-01-01 --to 2026-03-31 \
  --check-gaps                            # report sessions with no bars
```

### b) Backtest (Opening Range Breakout)

```bash
algo backtest --exchange NSE --symbol INFY \
  --from 2026-01-01 --to 2026-03-31 --or-minutes 15 \
  --slippage-bps 1 \
  --corp-actions corp_actions.json \      # optional: split/bonus back-adjust
  --warn-gaps \                           # optional: flag missing sessions
  --monte-carlo 1000 \                    # optional: bootstrap confidence band
  --report report.html                    # optional: shareable HTML report
```
Prints a **net-of-cost** metrics table (P&L, CAGR, Sharpe/Sortino, profit factor,
max drawdown, Calmar, turnover). `report.html` is self-contained (open in a browser).

### c) Momentum rotation (multi-asset)

```bash
algo rotation --exchange NSE \
  --symbols INFY,TCS,RELIANCE,HDFCBANK,ITC,SBIN \
  --from 2025-01-01 --to 2026-03-31 \
  --lookback 90 --top-n 3 --rebalance-every 21
```

### d) Walk-forward optimization

```bash
algo optimize --exchange NSE --symbol INFY \
  --from 2025-01-01 --to 2026-03-31 \
  --train-days 60 --test-days 20          # out-of-sample, not curve-fit
```

### e) Live paper-trading

```bash
algo paper-trade --exchange NSE --symbol INFY --or-minutes 15
```
Streams the Kite tick feed → engine → **PaperGateway** (simulated fills + costs),
persists fills to the DB on shutdown. **No real orders.**

---

## 8. Web dashboard (Next.js)

Two processes:

```bash
# 1) backend API (demo data, or a real engine state)
uv run python scripts/dashboard.py --demo
#    or replay stored bars:
uv run python scripts/dashboard.py --symbol INFY --from 2026-01-01 --to 2026-03-31

# 2) frontend
cd frontend
npm install
npm run dev          # http://localhost:3000
```
The UI polls the API every 5s. Set a custom API URL with
`echo 'NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000' > frontend/.env.local`.

---

## 9. Tests & linting

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest -v
```
DB-integration tests run automatically when `DATABASE_URL` points at a reachable
Postgres; otherwise they skip. CI runs everything against a real TimescaleDB.

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `... not found — run scripts/backfill.py first` | backfill the symbol/instrument master first |
| `No bars found for that range` | check dates; run backfill with `--check-gaps` |
| `No access token — run scripts/refresh_token.py` | refresh the daily Kite token |
| dashboard shows "disconnected" | start the API (`scripts/dashboard.py --demo`) and check CORS/port |
| `docker compose` services unhealthy | `docker compose logs`; ensure ports 5432/6379 are free |
| `alembic upgrade` fails | confirm TimescaleDB is up and `DATABASE_URL` is correct |

---

## Architecture

For how the pieces fit together, see [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md)
(system, deployment, DB schema, and class diagrams).
