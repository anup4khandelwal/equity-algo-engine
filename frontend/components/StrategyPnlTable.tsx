import { StrategyPnlRow, formatINR, formatNumber } from "@/lib/api";

export function StrategyPnlTable({ rows }: { rows?: StrategyPnlRow[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Strategy</th>
            <th>Trades</th>
            <th>Net P&L</th>
            <th>Gross P&L</th>
            <th>Charges</th>
            <th>Win rate</th>
          </tr>
        </thead>
        <tbody>
          {(rows ?? []).length === 0 ? (
            <tr>
              <td colSpan={6} className="text-center text-muted">
                No completed trades yet
              </td>
            </tr>
          ) : (
            rows!.map((r) => (
              <tr key={r.strategy}>
                <td className="font-medium">{r.strategy}</td>
                <td>{formatNumber(r.trades)}</td>
                <td className={r.net_pnl >= 0 ? "text-up" : "text-down"}>
                  {formatINR(r.net_pnl)}
                </td>
                <td className="text-muted">{formatINR(r.gross_pnl)}</td>
                <td className="text-muted">{formatINR(r.charges)}</td>
                <td>{(r.win_rate * 100).toFixed(0)}%</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
