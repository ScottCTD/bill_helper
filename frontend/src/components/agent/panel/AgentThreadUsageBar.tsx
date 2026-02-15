import { formatUsdCost, formatUsageTokens } from "./format";

interface AgentThreadUsageBarProps {
  selectedThreadId: string;
  totals: {
    input: number | null;
    output: number | null;
    cacheRead: number | null;
    cacheWrite: number | null;
    totalCost: number | null;
  };
}

export function AgentThreadUsageBar(props: AgentThreadUsageBarProps) {
  const { selectedThreadId, totals } = props;
  if (!selectedThreadId) {
    return null;
  }

  return (
    <div className="agent-thread-usage" aria-label="Thread usage and cost">
      <span>Input: {formatUsageTokens(totals.input)}</span>
      <span>Output: {formatUsageTokens(totals.output)}</span>
      <span>Cache read: {formatUsageTokens(totals.cacheRead)}</span>
      <span>Cache write: {formatUsageTokens(totals.cacheWrite)}</span>
      <span className="agent-thread-usage-total">Total cost: {formatUsdCost(totals.totalCost)}</span>
    </div>
  );
}
