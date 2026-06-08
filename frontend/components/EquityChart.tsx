"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { EquityPoint, formatINR } from "@/lib/api";

export function EquityChart({ data }: { data?: EquityPoint[] }) {
  const points = (data ?? []).map((p) => ({
    time: new Date(p.time).toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    }),
    equity: p.equity,
  }));

  return (
    <div className="card h-72">
      <div className="mb-2 text-sm font-medium text-muted">Equity curve</div>
      {points.length === 0 ? (
        <div className="flex h-full items-center justify-center text-muted">No data yet</div>
      ) : (
        <ResponsiveContainer width="100%" height="90%">
          <LineChart data={points} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
            <CartesianGrid stroke="#222b39" strokeDasharray="3 3" />
            <XAxis dataKey="time" tick={{ fill: "#8a97a8", fontSize: 11 }} minTickGap={40} />
            <YAxis
              tick={{ fill: "#8a97a8", fontSize: 11 }}
              domain={["auto", "auto"]}
              tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
              width={48}
            />
            <Tooltip
              contentStyle={{ background: "#141a24", border: "1px solid #222b39" }}
              labelStyle={{ color: "#8a97a8" }}
              formatter={(v: number) => [formatINR(v), "Equity"]}
            />
            <Line
              type="monotone"
              dataKey="equity"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
