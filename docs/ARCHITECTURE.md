# Architecture

A **local-first, paper-only** algorithmic-trading system for Indian equities on
Zerodha Kite Connect. The guiding principles:

- **One `Strategy` codebase** drives backtests *and* live paper-trading — no
  backtest-vs-live drift.
- **Every P&L is net** of the full Indian cost stack (brokerage, STT, exchange,
  SEBI, GST, stamp duty) plus slippage.
- **No real orders, ever** — `LiveGateway` is a stub that raises
  `NotImplementedError`; only `PaperGateway` executes.
- **Secrets never touch git** — read via `pydantic-settings` from a gitignored
  `.env`.

A rendered image of the diagram below lives at
[`docs/architecture.png`](./architecture.png) (source:
[`architecture.dot`](./architecture.dot)).

## System overview

```mermaid
flowchart TB
  subgraph EXT["External — Zerodha Kite Connect (paid market data)"]
    direction LR
    REST["Kite REST<br/>historical · account"]
    WS["KiteTicker<br/>WebSocket ticks"]
  end

  CFG["Settings (pydantic-settings)<br/>config/ ← .env (gitignored)"]
  CLI["CLIs (scripts/)<br/>refresh_token · backfill · backtest<br/>rotation · optimize · paper_trade · dashboard"]

  subgraph DATA["Broker & data layer"]
    BROKER["KiteClient<br/>throttle + TokenStore + auth"]
    REPO["Repositories<br/>instruments · ohlc · fills"]
    DOPS["backfill · calendar<br/>corporate-action adjust"]
  end

  subgraph STORE["State (docker-compose)"]
    TSDB[("TimescaleDB<br/>instruments · ohlc_bars hypertable<br/>5/15/60-min aggregates · fills")]
    REDIS[("Redis<br/>cache / throttle")]
  end

  subgraph CORE["Strategies & risk"]
    STRAT["Strategy ABC + ORB, Momentum,<br/>MA-cross, RSI2, VWAP, Supertrend,<br/>cross-sectional"]
    RISK["RiskManager + ATR sizing<br/>kill-switch · square-off · max positions"]
  end

  subgraph EXEC["Execution"]
    GW["OrderGateway (interface)"]
    PAPER["PaperGateway<br/>simulated fills + costs"]
    LIVE["LiveGateway<br/>NotImplementedError (disabled)"]
    PORT["Portfolio<br/>positions + net realised P&L"]
  end

  subgraph LIVELOOP["Live engine (engine.py + live/)"]
    FEED["KiteTickerFeed"]
    BB["BarBuilder<br/>ticks → 1-min bars"]
    ENG["PaperTradingEngine /<br/>MultiStrategyEngine"]
    TLOG["TradeLog"]
    NOTIF["Notifier (log / Telegram)"]
  end

  subgraph RESEARCH["Backtesting & research (backtest/)"]
    SIM["Event-driven simulator"]
    COST["Cost model"]
    MET["Metrics<br/>net P&L · Sharpe · Sortino · DD · turnover"]
    OPT["Walk-forward optimizer"]
    ROT["Rotation backtester"]
  end

  subgraph WEB["Read-only dashboard"]
    SVC["DashboardState + read-models<br/>api/service.py"]
    API["FastAPI app<br/>api/app.py (CORS, GET-only)"]
    UI["Next.js dashboard<br/>frontend/"]
    BROWSER["Browser"]
  end

  CFG --> BROKER
  CFG -. DATABASE_URL .-> REPO
  CLI -. run .-> DOPS
  DOPS --> BROKER --> REST
  DOPS --> REPO --> TSDB
  BROKER -. throttle buckets .-> REDIS

  WS --> FEED --> BB --> ENG
  ENG -->|on_bar → Signal| STRAT
  ENG -->|gate + size| RISK
  ENG --> GW
  GW -->|market| PAPER --> PORT
  GW -. live mode off .-> LIVE
  ENG --> PORT
  ENG --> TLOG
  ENG --> NOTIF
  ENG -. persist fills .-> REPO
  CLI -. paper_trade .-> ENG

  TSDB -->|bars| SIM
  SIM --> STRAT
  SIM --> COST --> MET
  OPT --> SIM
  ROT --> COST
  CLI -. backtest .-> SIM

  ENG -->|DashboardState.from_engine| SVC --> API --> UI --> BROWSER
  CLI -. dashboard .-> API

  classDef stub fill:#fde2df,stroke:#b0392f,color:#b0392f,stroke-dasharray:5 3;
  class LIVE stub;
  classDef store fill:#dfe4ea,stroke:#4a5568;
  class TSDB,REDIS store;
```

## Flow 1 — Live paper-trading

The engine is the **only** component that touches a gateway; swapping
`PaperGateway` for `LiveGateway` is the paper→live switch (and live stays
stubbed).

```mermaid
sequenceDiagram
  autonumber
  participant WS as KiteTicker
  participant BB as BarBuilder
  participant E as Engine
  participant S as Strategy
  participant R as RiskManager
  participant G as PaperGateway
  participant P as Portfolio
  participant DB as DB (fills)

  WS->>BB: tick (price, ts, volume)
  BB->>E: completed 1-min bar
  E->>S: on_bar(bar)
  S-->>E: Signal (entry / exit) or none
  alt entry signal
    E->>R: can_enter? (kill-switch, max-positions, cutoff)
    R-->>E: allowed
    E->>R: size (ATR-based)
    E->>G: place_order(market, reference_price)
    G-->>E: Fill (price ± slippage, charges)
    E->>P: apply_fill (net of costs)
    E->>DB: persist fill
  else square-off time
    E->>G: flatten open position
  end
```

## Flow 2 — Backtesting & optimization

Research reuses the **same** `Strategy` and cost model as live, so results carry
over without drift.

```mermaid
flowchart LR
  DB[("TimescaleDB<br/>1-min bars")] --> SIM["Event-driven simulator<br/>(slippage + costs per fill)"]
  STR["Strategy"] --> SIM
  SIM --> TR["Trades (net P&L)"]
  SIM --> EQ["Equity curve"]
  TR --> MET["Metrics<br/>net/gross P&L · Sharpe · Sortino<br/>max DD · win rate · turnover"]
  EQ --> MET
  OPT["Walk-forward optimizer<br/>in-sample → out-of-sample"] --> SIM
  ROT["Rotation backtester<br/>cross-sectional momentum"] --> MET
```

## Layer responsibilities

| Layer | Package | Responsibility |
|---|---|---|
| Config | `config/` | Typed settings from `.env` (secrets never hardcoded) |
| Broker | `broker/` | Kite REST wrapper, token-bucket throttle, daily token refresh |
| Data | `data/` | TimescaleDB models, repositories, backfill, calendar, corp-actions |
| Strategies | `strategies/` | `Strategy` ABC + implementations; pure decision logic |
| Backtest | `backtest/` | Simulator, cost model, metrics, rotation, walk-forward |
| Risk | `risk/` | ATR sizing, daily-loss kill-switch, square-off, max positions |
| Execution | `execution/` | `OrderGateway` → `PaperGateway` / `LiveGateway` (stub), `Portfolio` |
| Live | `live/` | Tick→bar aggregation, notifier, trade log, KiteTicker feed |
| Engine | `engine.py` | `PaperTradingEngine`, `MultiStrategyEngine` (shared risk budget) |
| API | `api/` | Read-only FastAPI dashboard service + app |
| Frontend | `frontend/` | Next.js dashboard (separate Node app over the API) |

## Safety boundaries

- **`LiveGateway`** raises `NotImplementedError` — paper is the only execution
  path until live is deliberately enabled (needs a registered static IP).
- **Costs are mandatory** and centralised in `backtest/costs.py`; the simulator
  and `PaperGateway` both apply them, so reported P&L is always net.
- **Secrets** are read via `pydantic-settings` from a gitignored `.env`;
  `gitleaks` runs on every commit and in CI.
- **Stateful services** (TimescaleDB, Redis) run via `docker-compose`; the
  Python engine runs on the host.
