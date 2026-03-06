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
  if (value === null) {
    return "-";
  }
  return `${(value / 1000).toFixed(2)}K`;
}

export function formatUsagePercent(value: number | null): string {
  if (value === null) {
    return "-";
  }
  const percentValue = value * 100;
  const fractionDigits = percentValue >= 10 ? 0 : 1;
  return `${percentValue.toFixed(fractionDigits)}%`;
}

export function formatUsdCost(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    minimumSignificantDigits: 2,
    maximumSignificantDigits: 2
  }).format(value);
}
