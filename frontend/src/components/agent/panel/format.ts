import type { AgentThreadSummary } from "../../../lib/types";

export function prettyDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function compactThreadName(thread: AgentThreadSummary): string {
  const source = (thread.title || "").trim();
  if (!source) {
    return "Untitled thread";
  }
  const normalized = source.replace(/\s+/g, " ");
  return normalized.slice(0, 20);
}

export function formatUsageTokens(value: number | null): string {
  return value === null ? "-" : value.toLocaleString();
}

export function formatUsdCost(value: number | null): string {
  if (value === null) {
    return "-";
  }
  const abs = Math.abs(value);
  const fractionDigits = abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits
  }).format(value);
}
