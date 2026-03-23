/**
 * CALLING SPEC:
 * - Purpose: render the promoted overview charts for builtin group breakdown and filter-group trends.
 * - Inputs: period-scoped filter-group summaries, chart trend rows, currency metadata, and loading state.
 * - Outputs: dashboard overview chart cards for ranked builtin groups, per-group tag facets, and small-multiple trends.
 * - Side effects: React rendering only.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { Badge } from "../../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { formatMinor, formatMinorCompact } from "../../lib/format";
import type { Dashboard, DashboardFilterGroupSummary } from "../../lib/types";
import {
  BUILTIN_FILTER_GROUP_ORDER,
  CHART_COLORS,
  DashboardChartContainer,
  axisTick,
  builtinGroupColor,
  dashboardBarColor,
  formatMonthShort,
  isIncomeFilterGroupKey,
  toMinorValue,
  tooltipAmount
} from "./helpers";

const MAX_TAGS_PER_GROUP = 6;
const MAX_SMALL_MULTIPLES = 6;
const PROJECTION_SCALE_EXPONENT = 0.5;
const OVERVIEW_BUILTIN_GROUP_ORDER = ["day_to_day", "one_time", "transfers", "fixed", "untagged"] as const;

type TrendRow = Record<string, unknown>;

type RankedGroupRow = DashboardFilterGroupSummary & {
  chart_color: string;
};

type SmallMultiplePoint = {
  label: string;
  value: number;
};

type OverviewCardState = {
  titlePrefix: string;
  currencyCode: string;
  yearlyQueriesLoading: boolean;
  yearlyQueryError?: Error;
};

type DashboardOverviewGroupBreakdownCardProps = OverviewCardState & {
  filterGroups: DashboardFilterGroupSummary[];
};

type DashboardOverviewTrendSmallMultiplesCardProps = OverviewCardState & {
  filterGroups: DashboardFilterGroupSummary[];
  trendChartData: TrendRow[];
};

type DashboardProjectionChartProps = {
  projection: Dashboard["projection"];
  filterGroups: DashboardFilterGroupSummary[];
  currencyCode: string;
};

export function DashboardOverviewGroupBreakdownCard({
  titlePrefix,
  filterGroups,
  currencyCode,
  yearlyQueriesLoading,
  yearlyQueryError
}: DashboardOverviewGroupBreakdownCardProps) {
  const builtinGroups = buildBuiltinRankedGroups(filterGroups);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{titlePrefix}Builtin Filter Groups by Spend</CardTitle>
        <p className="text-xs text-muted-foreground">Sqrt scale on ranked and tag bars.</p>
      </CardHeader>
      <CardContent>
        {yearlyQueriesLoading ? (
          <p className="muted text-sm">Loading grouped spend breakdown...</p>
        ) : yearlyQueryError ? (
          <p className="error">Failed to load grouped spend breakdown: {yearlyQueryError.message}</p>
        ) : builtinGroups.length === 0 ? (
          <p className="muted text-sm">No builtin expense-group activity for this scope.</p>
        ) : (
          <div className="grid gap-6 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
            <div className="space-y-4">
              <div className="h-[24rem] min-w-0">
                <DashboardChartContainer>
                  {({ width, height }) => (
                    <BarChart width={width} height={height} data={buildRankedChartRows(builtinGroups)} layout="vertical" margin={{ left: 24, right: 12 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.18} />
                      <XAxis type="number" tickFormatter={axisTick} scale="sqrt" domain={[0, "dataMax"]} />
                      <YAxis dataKey="name" type="category" width={108} tick={{ fontSize: 12 }} />
                      <Tooltip cursor={{ fill: "hsl(var(--muted) / 0.18)" }} formatter={(value) => tooltipAmount(currencyCode, value)} />
                      <Bar dataKey="total_minor" radius={[0, 8, 8, 0]}>
                        {builtinGroups.map((group) => (
                          <Cell key={group.key} fill={group.chart_color} />
                        ))}
                      </Bar>
                    </BarChart>
                  )}
                </DashboardChartContainer>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {builtinGroups.map((group, index) => (
                  <div key={group.key} className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="flex items-center gap-2 font-medium">
                        <span className="inline-block size-2.5 rounded-sm" style={{ backgroundColor: group.chart_color }} />
                        {index + 1}. {group.name}
                      </span>
                      <span className="text-muted-foreground">{formatShare(group.share)}</span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{formatMinor(group.total_minor, currencyCode)}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {builtinGroups.map((group) => {
                const chartData = buildFacetChartRows(group);
                return (
                  <div key={group.key} className="rounded-xl border border-border/70 bg-muted/10 p-4">
                    <div className="mb-3 flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium">{group.name}</p>
                      </div>
                      <Badge variant="outline" style={{ borderColor: group.chart_color, color: group.chart_color }}>
                        {formatMinor(group.total_minor, currencyCode)}
                      </Badge>
                    </div>
                    <div className="h-48 min-w-0">
                      <DashboardChartContainer>
                        {({ width, height }) => (
                          <BarChart width={width} height={height} data={chartData} layout="vertical" margin={{ left: 8, right: 8 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.15} />
                            <XAxis type="number" tickFormatter={axisTick} scale="sqrt" domain={[0, "dataMax"]} hide />
                            <YAxis dataKey="tag" type="category" width={88} tick={{ fontSize: 11 }} />
                            <Tooltip formatter={(value) => tooltipAmount(currencyCode, value)} />
                            <Bar dataKey="total_minor" name="Amount" fill={group.chart_color} radius={[0, 4, 4, 0]} />
                          </BarChart>
                        )}
                      </DashboardChartContainer>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function DashboardProjectionChart({ projection, filterGroups, currencyCode }: DashboardProjectionChartProps) {
  if (projection.projected_total_minor === null) {
    return <p className="muted text-sm">Projection is only available for the current month.</p>;
  }

  const rows = buildProjectionRows(projection, filterGroups);
  const scaleTicks = buildProjectionScaleTicks(rows);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-2">
          <span className="inline-block size-2.5 rounded-sm bg-[rgb(var(--chart-expense))]" />
          Spent already
        </span>
        <span className="flex items-center gap-2">
          <span className="inline-block size-2.5 rounded-sm bg-[rgb(var(--chart-expense))] opacity-30" />
          Projected growth
        </span>
        <span>Sqrt scale</span>
      </div>
      <div className="space-y-3">
        <div className="grid grid-cols-[7rem_minmax(0,1fr)_16rem] items-end gap-3 text-[11px] uppercase tracking-wide text-muted-foreground">
          <span />
          <div className="relative h-4">
            {scaleTicks.map((tick) => (
              <span
                key={tick.value}
                className="absolute"
                style={{
                  left: `${tick.position_percent}%`,
                  transform:
                    tick.position_percent === 0
                      ? "translateX(0)"
                      : tick.position_percent === 100
                        ? "translateX(-100%)"
                        : "translateX(-50%)"
                }}
              >
                {tick.label}
              </span>
            ))}
          </div>
          <div className="grid grid-cols-[1fr_1.5rem_1fr] gap-2 text-left">
            <span>Spent</span>
            <span aria-hidden>→</span>
            <span>Predicted</span>
          </div>
        </div>
        <div className="space-y-4">
          {rows.map((row) => (
            <div key={row.key} className="grid grid-cols-[7rem_minmax(0,1fr)_16rem] items-center gap-3">
              <div className="text-sm font-medium text-foreground">{row.name}</div>
              <div className="relative h-12 overflow-hidden rounded-lg bg-muted/20">
                <div className="absolute inset-0 flex">
                  <div
                    className="h-full"
                    style={{
                      width: `${row.spent_percent}%`,
                      backgroundColor: row.color,
                      opacity: 0.95
                    }}
                  />
                  <div
                    className="h-full rounded-r-lg"
                    style={{
                      width: `${row.projected_growth_percent}%`,
                      backgroundColor: row.color,
                      opacity: 0.28
                    }}
                  />
                </div>
                <div className="pointer-events-none absolute inset-0">
                  {scaleTicks.slice(1, -1).map((tick) => (
                    <span
                      key={tick.value}
                      className="absolute inset-y-0 w-px bg-slate-400/20"
                      style={{ left: `${tick.position_percent}%` }}
                    />
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-[1fr_1.5rem_1fr] gap-2 text-[0.95rem] font-semibold tracking-tight tabular-nums text-foreground">
                <span className="text-left">{row.spent_label}</span>
                <span className="text-left text-muted-foreground" aria-hidden>→</span>
                <span className="text-left">{row.projected_label}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function DashboardOverviewTrendSmallMultiplesCard({
  titlePrefix,
  filterGroups,
  trendChartData,
  currencyCode,
  yearlyQueriesLoading,
  yearlyQueryError
}: DashboardOverviewTrendSmallMultiplesCardProps) {
  const groupsToShow = buildExpenseRankedGroups(filterGroups).slice(0, MAX_SMALL_MULTIPLES);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{titlePrefix}Small-Multiple Trends</CardTitle>

      </CardHeader>
      <CardContent>
        {yearlyQueriesLoading ? (
          <p className="muted text-sm">Loading filter-group trends...</p>
        ) : yearlyQueryError ? (
          <p className="error">Failed to load filter-group trends: {yearlyQueryError.message}</p>
        ) : groupsToShow.length === 0 ? (
          <p className="muted text-sm">No trend data for this scope.</p>
        ) : (
          <div className="grid gap-3 xl:grid-cols-2">
            {groupsToShow.map((group) => {
              const series = buildGroupTrendSeries(group.key, trendChartData);
              const latest = series[series.length - 1]?.value ?? 0;
              const first = series[0]?.value ?? 0;
              const delta = latest - first;
              return (
                <div key={group.key} className="rounded-xl border border-border/70 bg-muted/15 p-3">
                  <div className="mb-2 flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium">{group.name}</p>
                      <p className="text-xs text-muted-foreground">
                        Latest: {formatMinor(latest, currencyCode)}
                        {series.length > 1 ? ` (${formatTrendDelta(delta, currencyCode)})` : ""}
                      </p>
                    </div>
                    <Badge variant="outline" style={{ borderColor: group.chart_color, color: group.chart_color }}>
                      {formatMinor(group.total_minor, currencyCode)}
                    </Badge>
                  </div>
                  <div className="h-24 min-w-0">
                    {series.length === 0 ? (
                      <p className="muted text-xs">No trend points.</p>
                    ) : (
                      <DashboardChartContainer>
                        {({ width, height }) => (
                          <LineChart width={width} height={height} data={series} margin={{ top: 8, right: 4, left: 4, bottom: 4 }}>
                            <CartesianGrid vertical={false} strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.12} />
                            <XAxis dataKey="label" hide />
                            <YAxis hide domain={[0, "dataMax"]} />
                            <Tooltip formatter={(value) => tooltipAmount(currencyCode, value)} />
                            <Line
                              type="monotone"
                              dataKey="value"
                              stroke={group.chart_color}
                              strokeWidth={2.25}
                              dot={false}
                              activeDot={{ r: 4 }}
                            />
                          </LineChart>
                        )}
                      </DashboardChartContainer>
                    )}
                  </div>
                  <div className="mt-2 flex items-center justify-between text-[11px] uppercase tracking-wide text-muted-foreground">
                    <span>{series[0]?.label ?? "Start"}</span>
                    <span>{series[series.length - 1]?.label ?? "End"}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function buildRankedChartRows(groups: RankedGroupRow[]) {
  return groups.map((group) => ({
    name: group.name,
    total_minor: group.total_minor,
    fill: group.chart_color
  }));
}

function buildBuiltinRankedGroups(filterGroups: DashboardFilterGroupSummary[]): RankedGroupRow[] {
  return filterGroups
    .filter((group) => OVERVIEW_BUILTIN_GROUP_ORDER.includes(group.key as (typeof OVERVIEW_BUILTIN_GROUP_ORDER)[number]) && group.total_minor > 0)
    .map((group, index) => ({
      ...group,
      chart_color: builtinGroupColor(group.key) || dashboardBarColor(index)
    }))
    .sort(
      (left, right) =>
        OVERVIEW_BUILTIN_GROUP_ORDER.indexOf(left.key as (typeof OVERVIEW_BUILTIN_GROUP_ORDER)[number]) -
        OVERVIEW_BUILTIN_GROUP_ORDER.indexOf(right.key as (typeof OVERVIEW_BUILTIN_GROUP_ORDER)[number])
    );
}

function buildExpenseRankedGroups(filterGroups: DashboardFilterGroupSummary[]): RankedGroupRow[] {
  return filterGroups
    .filter((group) => !isIncomeFilterGroupKey(group.key) && group.total_minor > 0)
    .map((group, index) => ({
      ...group,
      chart_color: resolveGroupColor(group, index)
    }))
    .sort((left, right) => {
      if (right.total_minor !== left.total_minor) {
        return right.total_minor - left.total_minor;
      }
      const leftBuiltinIndex = BUILTIN_FILTER_GROUP_ORDER.indexOf(left.key as (typeof BUILTIN_FILTER_GROUP_ORDER)[number]);
      const rightBuiltinIndex = BUILTIN_FILTER_GROUP_ORDER.indexOf(right.key as (typeof BUILTIN_FILTER_GROUP_ORDER)[number]);
      if (leftBuiltinIndex !== rightBuiltinIndex) {
        if (leftBuiltinIndex === -1) {
          return 1;
        }
        if (rightBuiltinIndex === -1) {
          return -1;
        }
        return leftBuiltinIndex - rightBuiltinIndex;
      }
      return left.name.localeCompare(right.name);
    });
}

function resolveGroupColor(group: DashboardFilterGroupSummary, index: number): string {
  if (group.color) {
    return group.color;
  }
  if (BUILTIN_FILTER_GROUP_ORDER.includes(group.key as (typeof BUILTIN_FILTER_GROUP_ORDER)[number])) {
    return builtinGroupColor(group.key);
  }
  return dashboardBarColor(index + BUILTIN_FILTER_GROUP_ORDER.length);
}

function buildFacetChartRows(group: DashboardFilterGroupSummary) {
  const topTags = Object.entries(group.tag_totals ?? {})
    .sort((left, right) => right[1] - left[1])
    .slice(0, MAX_TAGS_PER_GROUP);
  const tagSum = topTags.reduce((sum, [, amount]) => sum + amount, 0);
  const remainder = Math.max(0, group.total_minor - tagSum);

  return [
    ...topTags.map(([tag, amount]) => ({ tag, total_minor: amount })),
    ...(remainder > 0 ? [{ tag: "other", total_minor: remainder }] : [])
  ];
}

function buildGroupTrendSeries(groupKey: string, trendChartData: TrendRow[]): SmallMultiplePoint[] {
  return trendChartData.map((row) => ({
    label: normalizeTrendLabel(String(row.month ?? "")),
    value: toMinorValue(row[groupKey])
  }));
}

function normalizeTrendLabel(label: string): string {
  if (/^\d{4}-\d{2}$/.test(label)) {
    return formatMonthShort(label);
  }
  return label;
}

function formatShare(share: number): string {
  return `${(share * 100).toFixed(0)}%`;
}

function formatTrendDelta(deltaMinor: number, currencyCode: string): string {
  const prefix = deltaMinor >= 0 ? "+" : "-";
  return `${prefix}${formatMinor(Math.abs(deltaMinor), currencyCode)}`;
}

function buildProjectionRows(
  projection: Dashboard["projection"],
  filterGroups: DashboardFilterGroupSummary[]
): Array<{
  key: string;
  name: string;
  color: string;
  spent_minor: number;
  projected_growth_minor: number;
  projected_total_minor: number;
  spent_label: string;
  projected_label: string;
  spent_percent: number;
  projected_growth_percent: number;
}> {
  const totalSpentMinor = projection.spent_to_date_minor;
  const totalProjectedMinor = projection.projected_total_minor ?? totalSpentMinor;
  const maxProjectedMinor = Math.max(
    totalProjectedMinor,
    ...filterGroups
      .filter((group) => !isIncomeFilterGroupKey(group.key))
      .map((group) => Math.max(projection.projected_filter_group_totals[group.key] ?? group.total_minor, group.total_minor))
  );
  const totalRow = {
    key: "total",
    name: "Total",
    color: CHART_COLORS.expense,
    spent_minor: totalSpentMinor,
    projected_growth_minor: Math.max(totalProjectedMinor - totalSpentMinor, 0),
    projected_total_minor: Math.max(totalProjectedMinor, totalSpentMinor),
    spent_label: formatMinorCompact(totalSpentMinor),
    projected_label: formatMinorCompact(Math.max(totalProjectedMinor, totalSpentMinor)),
    spent_percent: scaledPercentOf(totalSpentMinor, maxProjectedMinor),
    projected_growth_percent: scaledStackedPercent(
      Math.max(totalProjectedMinor, totalSpentMinor),
      totalSpentMinor,
      maxProjectedMinor
    )
  };

  const groupRows = filterGroups
    .filter((group) => !isIncomeFilterGroupKey(group.key))
    .map((group, index) => {
      const projectedTotalMinor = projection.projected_filter_group_totals[group.key] ?? group.total_minor;
      return {
        key: group.key,
        name: group.name,
        color: resolveGroupColor(group, index),
        spent_minor: group.total_minor,
        projected_growth_minor: Math.max(projectedTotalMinor - group.total_minor, 0),
        projected_total_minor: Math.max(projectedTotalMinor, group.total_minor),
        spent_label: formatMinorCompact(group.total_minor),
        projected_label: formatMinorCompact(Math.max(projectedTotalMinor, group.total_minor)),
        spent_percent: scaledPercentOf(group.total_minor, maxProjectedMinor),
        projected_growth_percent: scaledStackedPercent(
          Math.max(projectedTotalMinor, group.total_minor),
          group.total_minor,
          maxProjectedMinor
        )
      };
    })
    .filter((group) => group.spent_minor > 0 || group.projected_total_minor > 0);

  return [totalRow, ...groupRows];
}

function scaledPercentOf(value: number, maxValue: number): number {
  if (maxValue <= 0 || value <= 0) {
    return 0;
  }
  return Math.pow(value / maxValue, PROJECTION_SCALE_EXPONENT) * 100;
}

function buildProjectionScaleTicks(
  rows: Array<{ projected_total_minor: number }>
): Array<{ value: number; label: string; position_percent: number }> {
  const maxValue = Math.max(0, ...rows.map((row) => row.projected_total_minor));
  if (maxValue <= 0) {
    return [{ value: 0, label: formatMinorCompact(0), position_percent: 0 }];
  }

  return [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const tickValue = Math.round(maxValue * Math.pow(ratio, 1 / PROJECTION_SCALE_EXPONENT));
    return {
      value: ratio,
      label: formatMinorCompact(tickValue),
      position_percent: ratio * 100
    };
  });
}

function scaledStackedPercent(totalValue: number, baseValue: number, maxValue: number): number {
  return Math.max(scaledPercentOf(totalValue, maxValue) - scaledPercentOf(baseValue, maxValue), 0);
}
