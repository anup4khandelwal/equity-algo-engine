import { PositionRow, formatINR, formatNumber } from "@/lib/api";

export function PositionsTable({ rows }: { rows?: PositionRow[] }) {
  return (
    <div className="table-wrap max-h-72 overflow-y-auto">
      <table>
        <thead>
          <tr>
            <th>Instrument</th>
            <th>Side</th>
            <th>Qty</th>
            <th>Entry</th>
            <th>Last</th>
            <th>Unrealised</th>
          </tr>
        </thead>
        <tbody>
          {(rows ?? []).length === 0 ? (
            <tr>
              <td colSpan={6} className="text-center text-muted">
                No open positions
              </td>
            </tr>
          ) : (
            rows!.map((r) => (
              <tr key={r.instrument_token}>
                <td>{r.instrument_token}</td>
                <td className={r.direction === "BUY" ? "text-up" : "text-down"}>{r.direction}</td>
                <td>{formatNumber(r.quantity)}</td>
                <td>{formatINR(r.entry_price)}</td>
                <td>{formatINR(r.last_price)}</td>
                <td className={(r.unrealized_pnl ?? 0) >= 0 ? "text-up" : "text-down"}>
                  {formatINR(r.unrealized_pnl)}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
