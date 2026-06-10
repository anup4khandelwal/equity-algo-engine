"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickData,
  IChartApi,
  SeriesMarker,
  Time,
  UTCTimestamp,
  createChart,
} from "lightweight-charts";
import { Candle, RegimeRow, TradeRow } from "@/lib/api";

function toUnix(iso: string): UTCTimestamp {
  return Math.floor(new Date(iso).getTime() / 1000) as UTCTimestamp;
}

function regimeColor(regime: string): string {
  if (regime === "TRENDING") return "text-up";
  if (regime === "RANGING") return "text-down";
  return "text-muted";
}

export function CandleChart({
  candles,
  trades,
  regimes,
}: {
  candles?: Candle[];
  trades?: TradeRow[];
  regimes?: RegimeRow[];
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !candles || candles.length === 0) return;

    const chart = createChart(el, {
      height: 320,
      layout: { background: { color: "#141a24" }, textColor: "#8a97a8" },
      grid: {
        vertLines: { color: "#222b39" },
        horzLines: { color: "#222b39" },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
      rightPriceScale: { borderColor: "#222b39" },
    });
    chartRef.current = chart;

    const series = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    // De-duplicate by timestamp (lightweight-charts requires ascending unique times).
    const seen = new Set<number>();
    const data: CandlestickData[] = [];
    for (const c of candles) {
      const t = toUnix(c.time);
      if (seen.has(t)) continue;
      seen.add(t);
      data.push({ time: t as Time, open: c.open, high: c.high, low: c.low, close: c.close });
    }
    series.setData(data);

    if (trades && trades.length > 0) {
      const markers: SeriesMarker<Time>[] = trades
        .map((tr) => ({
          time: toUnix(tr.time) as Time,
          position: tr.side === "BUY" ? ("belowBar" as const) : ("aboveBar" as const),
          color: tr.side === "BUY" ? "#22c55e" : "#ef4444",
          shape: tr.side === "BUY" ? ("arrowUp" as const) : ("arrowDown" as const),
          text: `${tr.side} ${tr.quantity}`,
        }))
        .sort((a, b) => (a.time as number) - (b.time as number));
      series.setMarkers(markers);
    }

    chart.timeScale().fitContent();
    const onResize = () => chart.applyOptions({ width: el.clientWidth });
    onResize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [candles, trades]);

  const latestRegime = regimes && regimes.length > 0 ? regimes[0] : null;

  return (
    <div className="card">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-muted">Price · trades marked</span>
        {latestRegime && (
          <span className={`text-xs ${regimeColor(latestRegime.regime)}`}>
            ● {latestRegime.regime} · ADX {latestRegime.adx.toFixed(1)}
          </span>
        )}
      </div>
      {!candles || candles.length === 0 ? (
        <div className="flex h-72 items-center justify-center text-muted">No bar data yet</div>
      ) : (
        <div ref={containerRef} className="w-full" />
      )}
    </div>
  );
}
