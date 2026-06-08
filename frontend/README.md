# equity-algo-engine — dashboard (Next.js)

A read-only web dashboard for the paper-trading engine. It polls the FastAPI
read-only API (positions, P&L, equity curve, trades, per-strategy attribution)
and renders cards, an equity chart, and tables. It never mutates state.

## Run it locally

1. **Start the backend API** (from the repo root):
   ```bash
   uv run python scripts/dashboard.py --demo          # zero-setup demo data
   # or, against real engine state, serve create_app(DashboardState.from_engine(engine))
   ```
   The API listens on `http://127.0.0.1:8000` and allows CORS from
   `http://localhost:3000`.

2. **Start the frontend** (from `frontend/`):
   ```bash
   npm install
   npm run dev
   ```
   Open **http://localhost:3000**.

## Configuration

- `NEXT_PUBLIC_API_BASE` — API base URL (default `http://127.0.0.1:8000`).
  ```bash
  echo 'NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000' > .env.local
  ```

## Build

```bash
npm run build    # type-checks and produces a production build
npm run start    # serve the production build
```

## Stack

Next.js (App Router) · React · TypeScript · Tailwind CSS · SWR (polling) ·
Recharts (equity curve). Data flows one way: FastAPI → SWR → components.
