import { AttributionRow, formatINR, formatNumber } from "@/lib/api";

export function AttributionTable({ rows }: { rows?: AttributionRow[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Strategy</th>
            <th>Fills</th>
            <th>Qty</th>
            <th>Charges</th>
            <th>Traded value</th>
          </tr>
        </thead>
        <tbody>
          {(rows ?? []).length === 0 ? (
            <tr>
              <td colSpan={5} className="text-center text-muted">
                No activity yet
              </td>
            </tr>
          ) : (
            rows!.map((r) => (
              <tr key={r.strategy}>
                <td className="font-medium">{r.strategy}</td>
                <td>{formatNumber(r.fills)}</td>
                <td>{formatNumber(r.quantity)}</td>
                <td className="text-muted">{formatINR(r.charges)}</td>
                <td>{formatINR(r.traded_value)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
