"use client";

import useSWR from "swr";
import {
  API_BASE,
  AttributionRow,
  Candle,
  ClosedTrade,
  EquityPoint,
  PnlSummary,
  PositionRow,
  RegimeRow,
  StrategyPnlRow,
  TradeRow,
  fetcher,
} from "@/lib/api";
import { SummaryCards } from "@/components/SummaryCards";
import { EquityChart } from "@/components/EquityChart";
import { CandleChart } from "@/components/CandleChart";
import { PositionsTable } from "@/components/PositionsTable";
import { TradesTable } from "@/components/TradesTable";
import { AttributionTable } from "@/components/AttributionTable";
import { StrategyPnlTable } from "@/components/StrategyPnlTable";
import { ClosedTradesTable } from "@/components/ClosedTradesTable";

const REFRESH_MS = 5000;

function useApi<T>(path: string) {
  return useSWR<T>(path, (p: string) => fetcher<T>(p), {
    refreshInterval: REFRESH_MS,
    keepPreviousData: true,
  });
}

export default function Dashboard() {
  const pnl = useApi<PnlSummary>("/pnl");
  const equity = useApi<EquityPoint[]>("/equity");
  const positions = useApi<PositionRow[]>("/positions");
  const trades = useApi<TradeRow[]>("/trades");
  const attribution = useApi<AttributionRow[]>("/attribution");
  const candles = useApi<Candle[]>("/candles");
  const regimes = useApi<RegimeRow[]>("/regimes");
  const strategyPnl = useApi<StrategyPnlRow[]>("/strategy-pnl");
  const closedTrades = useApi<ClosedTrade[]>("/closed-trades");

  const offline = pnl.error || equity.error;

  return (
    <main className="mx-auto max-w-6xl space-y-5 p-5">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">equity-algo-engine</h1>
          <p className="text-sm text-muted">Read-only paper-trading dashboard · NSE/BSE</p>
        </div>
        <div className="text-right text-xs text-muted">
          <div>
            API: <span className="text-white/80">{API_BASE}</span>
          </div>
          <div className={offline ? "text-down" : "text-up"}>
            {offline ? "● disconnected" : `● live · refresh ${REFRESH_MS / 1000}s`}
          </div>
        </div>
      </header>

      {offline && (
        <div className="card border-down/40 text-down">
          Cannot reach the API. Start it with{" "}
          <code className="text-white/80">uv run python scripts/dashboard.py --demo</code>.
        </div>
      )}

      <SummaryCards pnl={pnl.data} />
      <CandleChart candles={candles.data} trades={trades.data} regimes={regimes.data} />
      <EquityChart data={equity.data} />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <section className="space-y-2">
          <h2 className="text-sm font-medium text-muted">Strategy P&L (realised)</h2>
          <StrategyPnlTable rows={strategyPnl.data} />
        </section>
        <section className="space-y-2">
          <h2 className="text-sm font-medium text-muted">Open positions</h2>
          <PositionsTable rows={positions.data} />
        </section>
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted">Closed trades</h2>
        <ClosedTradesTable rows={closedTrades.data} />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted">Per-strategy activity</h2>
        <AttributionTable rows={attribution.data} />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted">Recent fills</h2>
        <TradesTable rows={trades.data} />
      </section>
    </main>
  );
}
