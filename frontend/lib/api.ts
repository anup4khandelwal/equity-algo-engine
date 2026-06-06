// Typed client for the read-only FastAPI dashboard API.
// Base URL is configurable via NEXT_PUBLIC_API_BASE (defaults to local FastAPI).

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export interface PnlSummary {
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  total_charges: number;
  open_positions: number;
}

export interface PositionRow {
  instrument_token: number;
  direction: string;
  quantity: number;
  entry_price: number;
  last_price: number | null;
  unrealized_pnl: number | null;
}

export interface TradeRow {
  time: string;
  instrument_token: number;
  side: string;
  quantity: number;
  fill_price: number;
  charges: number;
  strategy: string;
  reason: string;
}

export interface EquityPoint {
  time: string;
  equity: number;
}

export interface AttributionRow {
  strategy: string;
  fills: number;
  quantity: number;
  charges: number;
  traded_value: number;
}

export async function fetcher<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export function formatINR(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN").format(value);
}
