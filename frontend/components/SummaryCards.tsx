import { PnlSummary, formatINR } from "@/lib/api";

function Card({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "up" | "down" | "neutral";
}) {
  const color =
    tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-white";
  return (
    <div className="card">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${color}`}>{value}</div>
    </div>
  );
}

export function SummaryCards({ pnl }: { pnl?: PnlSummary }) {
  const tone = (v?: number) =>
    v === undefined ? "neutral" : v > 0 ? "up" : v < 0 ? "down" : "neutral";
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Card label="Total P&L" value={formatINR(pnl?.total_pnl)} tone={tone(pnl?.total_pnl)} />
      <Card label="Realised" value={formatINR(pnl?.realized_pnl)} tone={tone(pnl?.realized_pnl)} />
      <Card label="Unrealised" value={formatINR(pnl?.unrealized_pnl)} tone={tone(pnl?.unrealized_pnl)} />
      <Card label="Open positions" value={pnl ? String(pnl.open_positions) : "—"} />
    </div>
  );
}
