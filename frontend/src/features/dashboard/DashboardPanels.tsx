/**
 * CALLING SPEC:
 * - Purpose: render dashboard tab panel content for the dashboard route.
 * - Inputs: derived dashboard route state, chart datasets, and typed dashboard read models.
 * - Outputs: tab panel React elements.
 * - Side effects: React rendering only.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { StatBlock } from "../../components/layout/StatBlock";
import { Badge } from "../../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import { formatMinor } from "../../lib/format";
import type { Dashboard } from "../../lib/types";
import { cn } from "../../lib/utils";
import { DashboardSankeyChart } from "./DashboardSankeyChart";
import {
  CHART_COLORS,
  DASHBOARD_PIE_ANIMATION_PROPS,
  DashboardChartContainer,
  type DashboardViewMode,
  axisTick,
  buildYearLargestExpenses,
  buildYearlyFilterGroupsWithTagTotals,
  builtinGroupColor,
  dashboardBarColor,
  dashboardPieColor,
  filterGroupTotalForMonth,
  formatDayFromDate,
  formatDelta,
  formatMonthLong,
  formatMonthShort,
  shiftMonthKey,
  sumFilterGroupForMonths,
  tooltipAmount,
  tooltipAmountWithName
} from "./helpers";

type DashboardOverviewPanelProps = {
  viewMode: DashboardViewMode;
  selectedYear: number;
  data: Dashboard;
  primaryFilterGroup: Dashboard["filter_groups"][number] | null;
  yearlyQueriesLoading: boolean;
  yearlyQueryError?: Error;
  selectedYearExpenseTotalMinor: number;
  selectedYearIncomeTotalMinor: number;
  selectedYearNetTotalMinor: number;
  yearlyPrimaryFilterGroupTotalMinor: number;
  selectedYearMonths: string[];
  yearlyDashboardsByMonth: Map<string, Dashboard>;
};

export function DashboardOverviewPanel({
  viewMode,
  selectedYear,
  data,
  primaryFilterGroup,
  yearlyQueriesLoading,
  yearlyQueryError,
  selectedYearExpenseTotalMinor,
  selectedYearIncomeTotalMinor,
  selectedYearNetTotalMinor,
  yearlyPrimaryFilterGroupTotalMinor,
  selectedYearMonths,
  yearlyDashboardsByMonth
}: DashboardOverviewPanelProps) {
  return (
    <section className="stack-lg" role="tabpanel" id="dashboard-panel-overview" aria-labelledby="dashboard-tab-overview">
      {viewMode === "month" ? (
        <>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <StatBlock label="Expense" value={formatMinor(data.kpis.expense_total_minor, data.currency_code)} tone="warning" />
            <StatBlock label="Income" value={formatMinor(data.kpis.income_total_minor, data.currency_code)} tone="success" />
            <StatBlock label="Net" value={formatMinor(data.kpis.net_total_minor, data.currency_code)} />
            <StatBlock
              label={primaryFilterGroup ? primaryFilterGroup.name : "Primary group"}
              value={primaryFilterGroup ? formatMinor(primaryFilterGroup.total_minor, data.currency_code) : "-"}
            />
          </section>

          <Card>
            <CardHeader>
              <CardTitle>Expense Flow by Filter Group &amp; Tags</CardTitle>
            </CardHeader>
            <CardContent className="h-[32rem] min-w-0">
              {data.kpis.expense_total_minor === 0 ? (
                <p className="muted">No expense activity this month.</p>
              ) : (
                <DashboardSankeyChart filterGroups={data.filter_groups} currencyCode={data.currency_code} />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Projection (Current Month)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2 md:grid-cols-3">
                <p className="rounded-md border border-border/70 bg-muted/30 px-3 py-2 text-sm">
                  <span className="block text-xs text-muted-foreground">Spent to date</span>
                  <strong>{formatMinor(data.projection.spent_to_date_minor, data.currency_code)}</strong>
                </p>
                <p className="rounded-md border border-border/70 bg-muted/30 px-3 py-2 text-sm">
                  <span className="block text-xs text-muted-foreground">Projected total</span>
                  <strong>
                    {data.projection.projected_total_minor === null
                      ? "Not a current month"
                      : formatMinor(data.projection.projected_total_minor, data.currency_code)}
                  </strong>
                </p>
                <p className="rounded-md border border-border/70 bg-muted/30 px-3 py-2 text-sm">
                  <span className="block text-xs text-muted-foreground">Projected remaining</span>
                  <strong>
                    {data.projection.projected_remaining_minor === null
                      ? "-"
                      : formatMinor(data.projection.projected_remaining_minor, data.currency_code)}
                  </strong>
                </p>
              </div>
              <div className="rounded-lg border border-border/70">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Filter group</TableHead>
                      <TableHead>Projected total</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.filter_groups.map((group) => (
                      <TableRow key={group.key}>
                        <TableCell>{group.name}</TableCell>
                        <TableCell>
                          {data.projection.projected_total_minor === null
                            ? "-"
                            : formatMinor(data.projection.projected_filter_group_totals[group.key] ?? 0, data.currency_code)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      ) : (
        <>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <StatBlock label={`${selectedYear} expense`} value={formatMinor(selectedYearExpenseTotalMinor, data.currency_code)} tone="warning" />
            <StatBlock label={`${selectedYear} income`} value={formatMinor(selectedYearIncomeTotalMinor, data.currency_code)} tone="success" />
            <StatBlock label={`${selectedYear} net`} value={formatMinor(selectedYearNetTotalMinor, data.currency_code)} />
            <StatBlock
              label={primaryFilterGroup ? `${primaryFilterGroup.name} (${selectedYear})` : "Primary group"}
              value={primaryFilterGroup ? formatMinor(yearlyPrimaryFilterGroupTotalMinor, data.currency_code) : "-"}
            />
          </section>

          <Card>
            <CardHeader>
              <CardTitle>{selectedYear} Expense Flow by Filter Group &amp; Tags</CardTitle>
            </CardHeader>
            <CardContent className="h-[32rem] min-w-0">
              {yearlyQueriesLoading ? (
                <p className="muted">Loading yearly data...</p>
              ) : yearlyQueryError ? (
                <p className="error">Failed to load yearly data: {yearlyQueryError.message}</p>
              ) : selectedYearExpenseTotalMinor === 0 ? (
                <p className="muted">No expense activity this year.</p>
              ) : (
                <DashboardSankeyChart
                  filterGroups={buildYearlyFilterGroupsWithTagTotals(data.filter_groups, selectedYearMonths, yearlyDashboardsByMonth)}
                  currencyCode={data.currency_code}
                />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{selectedYear} Filter Group Monthly Bars</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="muted text-sm">Each saved filter group gets its own month-by-month bar chart for the selected year.</p>
              {yearlyQueriesLoading ? (
                <p className="muted">Loading filter-group yearly bars...</p>
              ) : yearlyQueryError ? (
                <p className="error">Failed to load filter-group yearly bars: {yearlyQueryError.message}</p>
              ) : (
                <div className="grid gap-4 xl:grid-cols-2">
                  {data.filter_groups.map((group, index) => {
                    const groupYearData = selectedYearMonths.map((monthKey) => ({
                      month: formatMonthShort(monthKey),
                      total_minor: filterGroupTotalForMonth(yearlyDashboardsByMonth.get(monthKey), group.key)
                    }));
                    return (
                      <div key={group.key} className="rounded-xl border border-border/70 p-4">
                        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="font-medium">{group.name}</p>
                            <p className="muted text-xs">{selectedYear}</p>
                          </div>
                          <Badge variant="outline" style={{ borderColor: dashboardBarColor(index), color: dashboardBarColor(index) }}>
                            {formatMinor(sumFilterGroupForMonths(selectedYearMonths, yearlyDashboardsByMonth, group.key), data.currency_code)}
                          </Badge>
                        </div>
                        <div className="h-56 min-w-0">
                          <DashboardChartContainer>
                            {({ width, height }) => (
                              <BarChart width={width} height={height} data={groupYearData}>
                                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                                <XAxis dataKey="month" />
                                <YAxis tickFormatter={axisTick} />
                                <Tooltip formatter={(value, name) => tooltipAmountWithName(data.currency_code, value, name)} />
                                <Bar dataKey="total_minor" name={group.name} fill={dashboardBarColor(index)} radius={[4, 4, 0, 0]} />
                              </BarChart>
                            )}
                          </DashboardChartContainer>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </section>
  );
}

type DashboardDailyPanelProps = {
  viewMode: DashboardViewMode;
  selectedYear: number;
  data: Dashboard;
  dailyChartData: Array<Record<string, unknown>>;
  month: string;
  previousMonthDashboard: Dashboard | undefined;
  yearlyQueriesLoading: boolean;
  yearlyQueryError?: Error;
  yearlyOverviewData: Array<Record<string, unknown>>;
  yearlyAverageExpenseMonthMinor: number;
  yearlyMedianExpenseMonthMinor: number;
  selectedYearMonths: string[];
  previousYearMonths: string[];
  yearlyDashboardsByMonth: Map<string, Dashboard>;
};

export function DashboardDailyPanel({
  viewMode,
  selectedYear,
  data,
  dailyChartData,
  month,
  previousMonthDashboard,
  yearlyQueriesLoading,
  yearlyQueryError,
  yearlyOverviewData,
  yearlyAverageExpenseMonthMinor,
  yearlyMedianExpenseMonthMinor,
  selectedYearMonths,
  previousYearMonths,
  yearlyDashboardsByMonth
}: DashboardDailyPanelProps) {
  const dayToDayColor = builtinGroupColor("day_to_day");
  return (
    <section className="stack-lg" role="tabpanel" id="dashboard-panel-daily" aria-labelledby="dashboard-tab-daily">
      {viewMode === "month" ? (
        <>
          <section className="grid gap-4 md:grid-cols-3">
            <StatBlock label="Average Daily Spend (Day-to-Day)" value={formatMinor(data.kpis.average_day_to_day_minor ?? 0, data.currency_code)} />
            <StatBlock label="Median Daily Spend (Day-to-Day)" value={formatMinor(data.kpis.median_day_to_day_minor ?? 0, data.currency_code)} />
            <StatBlock label="Tracked groups" value={data.filter_groups.length} />
          </section>

          <Card>
            <CardHeader>
              <CardTitle>Daily Spending (Day-to-Day)</CardTitle>
            </CardHeader>
            <CardContent className="min-w-0 overflow-hidden">
              <div className="flex min-w-0 flex-col">
                <div className="h-80 min-w-0">
                  <DashboardChartContainer>
                    {({ width, height }) => (
                      <BarChart width={width} height={height} data={dailyChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                    <XAxis dataKey="date" tickFormatter={(v) => formatDayFromDate(String(v ?? ""))} />
                    <YAxis tickFormatter={axisTick} />
                    <Tooltip formatter={(value) => tooltipAmount(data.currency_code, value)} />
                    <ReferenceLine
                      y={data.kpis.average_day_to_day_minor ?? 0}
                      stroke={dashboardBarColor(1)}
                      strokeWidth={3}
                      strokeDasharray="6 4"
                      label={{
                        value: "Mean",
                        position: "right",
                        fill: dashboardBarColor(1),
                        fontSize: 13,
                        fontWeight: 600
                      }}
                    />
                    <ReferenceLine
                      y={data.kpis.median_day_to_day_minor ?? 0}
                      stroke={dashboardBarColor(2)}
                      strokeWidth={3}
                      strokeDasharray="2 4"
                      label={{
                        value: "Median",
                        position: "right",
                        fill: dashboardBarColor(2),
                        fontSize: 13,
                        fontWeight: 600
                      }}
                    />
                    <Bar dataKey="day_to_day" name="Day-to-Day" fill={dayToDayColor} radius={[4, 4, 0, 0]} />
                  </BarChart>
                )}
              </DashboardChartContainer>
                </div>
              <div className="mt-3 flex w-full min-w-0 flex-wrap gap-4 overflow-hidden text-sm" role="list" aria-label="Reference line legend">
                <span className="flex min-w-0 max-w-full shrink items-center gap-2">
                  <svg width={20} height={4} aria-hidden="true" className="shrink-0">
                    <line
                      x1={0}
                      y1={2}
                      x2={20}
                      y2={2}
                      stroke={dashboardBarColor(1)}
                      strokeWidth={2}
                      strokeDasharray="6 4"
                    />
                  </svg>
                  <span className="truncate">Mean</span>
                </span>
                <span className="flex items-center gap-2">
                  <svg width={20} height={4} aria-hidden="true" className="shrink-0">
                    <line
                      x1={0}
                      y1={2}
                      x2={20}
                      y2={2}
                      stroke={dashboardBarColor(2)}
                      strokeWidth={2}
                      strokeDasharray="2 4"
                    />
                  </svg>
                  <span className="truncate">Median</span>
                </span>
              </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Monthly Spend by Filter Group</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border border-border/70">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Filter Group</TableHead>
                      <TableHead>Monthly Spend</TableHead>
                      <TableHead>Delta to Last Month</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.filter_groups.map((group) => {
                      const prev = filterGroupTotalForMonth(previousMonthDashboard, group.key);
                      const delta = group.total_minor - prev;
                      const pct = prev > 0 ? ((delta / prev) * 100).toFixed(1) : null;
                      return (
                        <TableRow key={group.key}>
                          <TableCell className="font-medium">{group.name}</TableCell>
                          <TableCell>{formatMinor(group.total_minor, data.currency_code)}</TableCell>
                          <TableCell>
                            {prev === 0 && group.total_minor === 0 ? (
                              <span className="text-muted-foreground">—</span>
                            ) : (
                              <span className={cn(delta > 0 ? "text-red-500" : delta < 0 ? "text-green-500" : "text-muted-foreground")}>
                                {formatDelta(delta, data.currency_code)}
                                {pct !== null ? ` (${delta > 0 ? "+" : ""}${pct}%)` : ""}
                              </span>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      ) : (
        <>
          <section className="grid gap-4 md:grid-cols-3">
            <StatBlock label="Average expense month" value={formatMinor(yearlyAverageExpenseMonthMinor, data.currency_code)} />
            <StatBlock label="Median expense month" value={formatMinor(yearlyMedianExpenseMonthMinor, data.currency_code)} />
            <StatBlock label="Tracked groups" value={data.filter_groups.length} />
          </section>

          <Card>
            <CardHeader>
              <CardTitle>{selectedYear} Monthly Filter Group Trend</CardTitle>
            </CardHeader>
            <CardContent className="h-80 min-w-0">
              {yearlyQueriesLoading ? (
                <p className="muted">Loading yearly monthly trend...</p>
              ) : yearlyQueryError ? (
                <p className="error">Failed to load yearly monthly trend: {yearlyQueryError.message}</p>
              ) : (
                <DashboardChartContainer>
                  {({ width, height }) => (
                    <BarChart width={width} height={height} data={yearlyOverviewData}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                      <XAxis dataKey="month" />
                      <YAxis tickFormatter={axisTick} />
                      <Tooltip formatter={(value, name) => tooltipAmountWithName(data.currency_code, value, name)} />
                      <Legend />
                      {data.filter_groups.map((group, index) => (
                        <Bar
                          key={group.key}
                          dataKey={group.key}
                          name={group.name}
                          stackId="yearly-group-spend"
                          fill={dashboardBarColor(index)}
                          radius={[4, 4, 0, 0]}
                        />
                      ))}
                    </BarChart>
                  )}
                </DashboardChartContainer>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </section>
  );
}

type DashboardBreakdownsPanelProps = {
  viewMode: DashboardViewMode;
  month: string;
  data: Dashboard;
};

export function DashboardBreakdownsPanel({ viewMode, month, data }: DashboardBreakdownsPanelProps) {
  return (
    <section className="grid gap-4 xl:grid-cols-3" role="tabpanel" id="dashboard-panel-breakdowns" aria-labelledby="dashboard-tab-breakdowns">
      {viewMode === "year" ? (
        <div className="dashboard-scope-note xl:col-span-3">
          Breakdowns remain anchored to <strong>{formatMonthLong(month)}</strong>. Use `Overview` and `Spending` for year-level trend charts.
        </div>
      ) : null}
      <Card className="xl:col-span-1">
        <CardHeader>
          <CardTitle>Spending by Tags</CardTitle>
        </CardHeader>
        <CardContent className="h-80 min-w-0">
          {data.spending_by_tag.length === 0 ? (
            <p className="muted">No expense-tag data for this month.</p>
          ) : (
            <DashboardChartContainer>
              {({ width, height }) => (
                <PieChart width={width} height={height}>
                  <Pie
                    data={data.spending_by_tag}
                    dataKey="total_minor"
                    nameKey="label"
                    outerRadius={95}
                    {...DASHBOARD_PIE_ANIMATION_PROPS}
                  >
                    {data.spending_by_tag.map((item, index) => (
                      <Cell key={item.label} fill={dashboardPieColor(index)} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => tooltipAmount(data.currency_code, value)} />
                  <Legend />
                </PieChart>
              )}
            </DashboardChartContainer>
          )}
        </CardContent>
      </Card>

      <Card className="xl:col-span-2">
        <CardHeader>
          <CardTitle>Spending by Destination</CardTitle>
        </CardHeader>
        <CardContent className="h-80 min-w-0">
          {data.spending_by_to.length === 0 ? (
            <p className="muted">No destination breakdown yet.</p>
          ) : (
            <DashboardChartContainer>
              {({ width, height }) => (
                <BarChart width={width} height={height} data={data.spending_by_to} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                  <XAxis type="number" tickFormatter={axisTick} />
                  <YAxis dataKey="label" type="category" width={140} />
                  <Tooltip formatter={(value) => tooltipAmount(data.currency_code, value)} />
                  <Bar dataKey="total_minor" name="Total" fill={CHART_COLORS.destination} radius={[0, 6, 6, 0]} />
                </BarChart>
              )}
            </DashboardChartContainer>
          )}
        </CardContent>
      </Card>

      <Card className="xl:col-span-3">
        <CardHeader>
          <CardTitle>Spending by Source (`from`)</CardTitle>
        </CardHeader>
        <CardContent className="h-72 min-w-0">
          {data.spending_by_from.length === 0 ? (
            <p className="muted">No source breakdown yet.</p>
          ) : (
            <DashboardChartContainer>
              {({ width, height }) => (
                <BarChart width={width} height={height} data={data.spending_by_from}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                  <XAxis dataKey="label" />
                  <YAxis tickFormatter={axisTick} />
                  <Tooltip formatter={(value) => tooltipAmount(data.currency_code, value)} />
                  <Bar dataKey="total_minor" name="Total" fill={CHART_COLORS.source} radius={[6, 6, 0, 0]} />
                </BarChart>
              )}
            </DashboardChartContainer>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

type DashboardInsightsPanelProps = {
  viewMode: DashboardViewMode;
  selectedYear: number;
  month: string;
  data: Dashboard;
  insightsLargestExpenses: Dashboard["largest_expenses"];
  groupNamesByKey: Map<string, string>;
};

export function DashboardInsightsPanel({
  viewMode,
  selectedYear,
  month,
  data,
  insightsLargestExpenses,
  groupNamesByKey
}: DashboardInsightsPanelProps) {
  const title = viewMode === "year" ? "Largest Expenses (Year)" : "Largest Expenses";
  const emptyText = viewMode === "year" ? "No expense entries in this selected year." : "No expense entries in this month.";
  const scopeMonth = viewMode === "year" ? selectedYear : formatMonthLong(month);

  return (
    <section className="stack-lg" role="tabpanel" id="dashboard-panel-insights" aria-labelledby="dashboard-tab-insights">
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          {insightsLargestExpenses.length === 0 ? (
            <p className="muted">{emptyText}</p>
          ) : (
            <>
              <p className="muted mb-4 text-sm">Scope: {scopeMonth}</p>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Groups</TableHead>
                    <TableHead>Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {insightsLargestExpenses.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell>{entry.occurred_at}</TableCell>
                      <TableCell>{entry.name}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {entry.matching_filter_group_keys.length > 0 ? (
                            entry.matching_filter_group_keys.map((key) => (
                              <Badge key={key} variant="outline">
                                {groupNamesByKey.get(key) ?? key}
                              </Badge>
                            ))
                          ) : (
                            <Badge variant="outline">Unmatched</Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>{formatMinor(entry.amount_minor, data.currency_code)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
