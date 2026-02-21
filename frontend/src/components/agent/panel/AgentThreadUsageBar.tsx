import { formatUsdCost, formatUsagePercent, formatUsageTokens } from "./format";

interface AgentThreadUsageBarProps {
  selectedThreadId: string;
  totals: {
    context: number | null;
    input: number | null;
    output: number | null;
    cacheRead: number | null;
    totalCost: number | null;
  };
}

export function AgentThreadUsageBar(props: AgentThreadUsageBarProps) {
  const { selectedThreadId, totals } = props;
  if (!selectedThreadId) {
    return null;
  }
  const cacheHitRate =
    totals.input === null || totals.input <= 0 || totals.cacheRead === null ? null : totals.cacheRead / totals.input;

  return (
    <div className="agent-thread-usage" aria-label="Thread usage and cost">
      <span>Context: {formatUsageTokens(totals.context)}</span>
      <span>Input: {formatUsageTokens(totals.input)}</span>
      <span>Output: {formatUsageTokens(totals.output)}</span>
      <span>Cache read: {formatUsageTokens(totals.cacheRead)}</span>
      <span>Cache hit rate: {formatUsagePercent(cacheHitRate)}</span>
      <span className="agent-thread-usage-total">Total cost: {formatUsdCost(totals.totalCost)}</span>
    </div>
  );
}
