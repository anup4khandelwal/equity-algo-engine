import { TradeRow, formatINR, formatNumber } from "@/lib/api";

export function TradesTable({ rows }: { rows?: TradeRow[] }) {
  const recent = (rows ?? []).slice(-50).reverse();
  return (
    <div className="table-wrap max-h-96 overflow-y-auto">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Instrument</th>
            <th>Side</th>
            <th>Qty</th>
            <th>Price</th>
            <th>Charges</th>
            <th>Strategy</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {recent.length === 0 ? (
            <tr>
              <td colSpan={8} className="text-center text-muted">
                No trades yet
              </td>
            </tr>
          ) : (
            recent.map((r, i) => (
              <tr key={`${r.time}-${i}`}>
                <td className="whitespace-nowrap text-muted">
                  {new Date(r.time).toLocaleString("en-IN", {
                    day: "2-digit",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </td>
                <td>{r.instrument_token}</td>
                <td className={r.side === "BUY" ? "text-up" : "text-down"}>{r.side}</td>
                <td>{formatNumber(r.quantity)}</td>
                <td>{formatINR(r.fill_price)}</td>
                <td className="text-muted">{formatINR(r.charges)}</td>
                <td>{r.strategy}</td>
                <td className="text-muted">{r.reason}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
