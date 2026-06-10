import { ClosedTrade, formatINR, formatNumber } from "@/lib/api";

function holding(seconds: number): string {
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}

export function ClosedTradesTable({ rows }: { rows?: ClosedTrade[] }) {
  const recent = (rows ?? []).slice(-50).reverse();
  return (
    <div className="table-wrap max-h-96 overflow-y-auto">
      <table>
        <thead>
          <tr>
            <th>Exit time</th>
            <th>Instrument</th>
            <th>Dir</th>
            <th>Qty</th>
            <th>Entry</th>
            <th>Exit</th>
            <th>Net P&L</th>
            <th>Held</th>
            <th>Strategy</th>
          </tr>
        </thead>
        <tbody>
          {recent.length === 0 ? (
            <tr>
              <td colSpan={9} className="text-center text-muted">
                No closed trades yet
              </td>
            </tr>
          ) : (
            recent.map((r, i) => (
              <tr key={`${r.exit_time}-${i}`}>
                <td className="whitespace-nowrap text-muted">
                  {new Date(r.exit_time).toLocaleString("en-IN", {
                    day: "2-digit",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </td>
                <td>{r.instrument_token}</td>
                <td className={r.direction === "BUY" ? "text-up" : "text-down"}>{r.direction}</td>
                <td>{formatNumber(r.quantity)}</td>
                <td>{formatINR(r.entry_price)}</td>
                <td>{formatINR(r.exit_price)}</td>
                <td className={r.net_pnl >= 0 ? "text-up" : "text-down"}>{formatINR(r.net_pnl)}</td>
                <td className="text-muted">{holding(r.holding_seconds)}</td>
                <td className="text-muted">{r.strategy}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
