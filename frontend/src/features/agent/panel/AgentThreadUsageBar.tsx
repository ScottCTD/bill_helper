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
  const metrics = [
    { label: "Context", value: formatUsageTokens(totals.context) },
    { label: "Total input", value: formatUsageTokens(totals.input) },
    { label: "Output", value: formatUsageTokens(totals.output) },
    { label: "Cache read", value: formatUsageTokens(totals.cacheRead) },
    { label: "Cache hit rate", value: formatUsagePercent(cacheHitRate) },
    { label: "Total cost", value: formatUsdCost(totals.totalCost), emphasize: true }
  ];

  return (
    <div className="agent-thread-usage" aria-label="Thread usage and cost">
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className={metric.emphasize ? "agent-thread-usage-item agent-thread-usage-item-emphasis" : "agent-thread-usage-item"}
          title={`${metric.label}: ${metric.value}`}
        >
          <span className="agent-thread-usage-label">{metric.label}</span>
          <span className="agent-thread-usage-value">{metric.value}</span>
        </div>
      ))}
    </div>
  );
}
