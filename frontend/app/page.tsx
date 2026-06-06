"use client";

import useSWR from "swr";
import {
  API_BASE,
  AttributionRow,
  EquityPoint,
  PnlSummary,
  PositionRow,
  TradeRow,
  fetcher,
} from "@/lib/api";
import { SummaryCards } from "@/components/SummaryCards";
import { EquityChart } from "@/components/EquityChart";
import { PositionsTable } from "@/components/PositionsTable";
import { TradesTable } from "@/components/TradesTable";
import { AttributionTable } from "@/components/AttributionTable";

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

  const offline = pnl.error || equity.error;

  return (
    <main className="mx-auto max-w-6xl space-y-5 p-5">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">equity-algo-engine</h1>
          <p className="text-sm text-muted">Read-only paper-trading dashboard</p>
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
      <EquityChart data={equity.data} />

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted">Open positions</h2>
        <PositionsTable rows={positions.data} />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted">Per-strategy attribution</h2>
        <AttributionTable rows={attribution.data} />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted">Recent trades</h2>
        <TradesTable rows={trades.data} />
      </section>
    </main>
  );
}
