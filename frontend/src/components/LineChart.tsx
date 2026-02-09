import type { DailyExpensePoint } from "../lib/types";

interface LineChartProps {
  points: DailyExpensePoint[];
  currencyCode: string;
}

export function LineChart({ points, currencyCode }: LineChartProps) {
  const filtered = points.filter((point) => point.currency_code === currencyCode);
  if (filtered.length === 0) {
    return <p className="muted">No expense points for {currencyCode} in this month.</p>;
  }

  const width = 640;
  const height = 220;
  const padding = 24;
  const maxY = Math.max(...filtered.map((point) => point.total_minor), 1);
  const minX = 0;
  const maxX = Math.max(filtered.length - 1, 1);
  const axisColor = "hsl(var(--border))";
  const trendColor = "hsl(var(--primary))";

  const coords = filtered.map((point, index) => {
    const x = padding + ((index - minX) / (maxX - minX || 1)) * (width - padding * 2);
    const y = height - padding - (point.total_minor / maxY) * (height - padding * 2);
    return { ...point, x, y };
  });

  const path = coords
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(" ");

  return (
    <svg className="line-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Daily expense trend">
      <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke={axisColor} />
      <line x1={padding} y1={padding} x2={padding} y2={height - padding} stroke={axisColor} />
      <path d={path} fill="none" stroke={trendColor} strokeWidth={2.5} />
      {coords.map((point) => (
        <circle key={point.date} cx={point.x} cy={point.y} r={3} fill={trendColor} />
      ))}
    </svg>
  );
}
