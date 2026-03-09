import { useEffect, useRef, useState, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { currentMonth, formatMinor } from "../lib/format";
import { getDashboard } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { cn } from "../lib/utils";

type DashboardTab = "overview" | "daily" | "breakdowns" | "insights";

const DASHBOARD_TABS: Array<{ id: DashboardTab; label: string; description: string }> = [
  { id: "overview", label: "Overview", description: "Month snapshot and projection" },
  { id: "daily", label: "Daily Spend", description: "Daily-tagged spending behavior" },
  { id: "breakdowns", label: "Breakdowns", description: "From / to / tag analysis" },
  { id: "insights", label: "Insights", description: "Weekdays, outliers, reconciliation" }
];

const CHART_COLORS = {
  income: "hsl(var(--success))",
  expense: "hsl(var(--warning))",
  daily: "hsl(var(--success))",
  nonDaily: "hsl(var(--destructive))",
  net: "hsl(var(--primary))",
  muted: "hsl(var(--muted-foreground))"
};

const PIE_COLORS = [
  "hsl(var(--primary))",
  "hsl(var(--success))",
  "hsl(var(--warning))",
  "hsl(var(--destructive))",
  "hsl(var(--accent-foreground))",
  "hsl(var(--muted-foreground))",
  "hsl(var(--primary) / 0.75)",
  "hsl(var(--success) / 0.75)"
];

function axisTick(value: number | string) {
  const numericValue = typeof value === "number" ? value : Number(value);
  return `${Math.round((Number.isFinite(numericValue) ? numericValue : 0) / 100).toLocaleString()}`;
}

function toMinorValue(value: unknown): number {
  if (Array.isArray(value) && value.length > 0) {
    return toMinorValue(value[0]);
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return 0;
}

function tooltipAmount(currencyCode: string, value: unknown): string {
  return formatMinor(toMinorValue(value), currencyCode);
}

function tooltipAmountWithName(currencyCode: string, value: unknown, name: string | number | undefined): [string, string] {
  return [tooltipAmount(currencyCode, value), String(name ?? "")];
}

type ChartDimensions = {
  width: number;
  height: number;
};

function DashboardChartContainer({ children }: { children: (dimensions: ChartDimensions) => ReactElement }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState<ChartDimensions | null>(null);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }

    const updateDimensions = () => {
      const nextWidth = Math.floor(element.clientWidth);
      const nextHeight = Math.floor(element.clientHeight);
      if (nextWidth <= 0 || nextHeight <= 0) {
        return;
      }

      setDimensions((current) => {
        if (current?.width === nextWidth && current?.height === nextHeight) {
          return current;
        }
        return { width: nextWidth, height: nextHeight };
      });
    };

    updateDimensions();
    if (typeof ResizeObserver === "undefined") {
      return;
    }

    const observer = new ResizeObserver(() => {
      updateDimensions();
    });
    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, []);

  return (
    <div ref={containerRef} className="h-full min-w-0">
      {dimensions ? children(dimensions) : null}
    </div>
  );
}

export function DashboardPage() {
  const [month, setMonth] = useState(currentMonth());
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
  const { data, isLoading, isError, error } = useQuery({
    queryKey: queryKeys.dashboard.month(month),
    queryFn: () => getDashboard(month)
  });

  if (isLoading) {
    return <p>Loading dashboard...</p>;
  }

  if (isError || !data) {
    return <p>Failed to load dashboard: {(error as Error).message}</p>;
  }

  const dailySpendSplit = [
    { name: "Daily", value: data.kpis.daily_expense_total_minor },
    { name: "Non-daily", value: data.kpis.non_daily_expense_total_minor }
  ];

  return (
    <div className="stack-lg">
      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="table-shell-header">
            <div>
              <h2 className="table-shell-title">Dashboard</h2>
            </div>
          </div>

          <div className="table-toolbar">
            <label className="field min-w-[220px]">
              <span>Month</span>
              <Input type="month" value={month} onChange={(event) => setMonth(event.target.value)} />
            </label>
            <div className="field min-w-[180px]">
              <span>Currency</span>
              <p className="rounded-md border border-input bg-muted/30 px-3 py-2 text-sm font-medium">{data.currency_code}</p>
            </div>
          </div>

          <div className="dashboard-tab-list" role="tablist" aria-label="Dashboard sections">
            {DASHBOARD_TABS.map((tab) => (
              <Button
                key={tab.id}
                id={`dashboard-tab-${tab.id}`}
                role="tab"
                aria-controls={`dashboard-panel-${tab.id}`}
                aria-selected={activeTab === tab.id}
                variant={activeTab === tab.id ? "default" : "outline"}
                size="sm"
                className={cn("dashboard-tab-button", activeTab === tab.id ? "dashboard-tab-active" : "")}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </Button>
            ))}
          </div>

          <p className="muted">{DASHBOARD_TABS.find((tab) => tab.id === activeTab)?.description}</p>
        </CardContent>
      </Card>

      {activeTab === "overview" ? (
        <section className="stack-lg" role="tabpanel" id="dashboard-panel-overview" aria-labelledby="dashboard-tab-overview">
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Expense (Month)</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">{formatMinor(data.kpis.expense_total_minor, data.currency_code)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Income (Month)</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">{formatMinor(data.kpis.income_total_minor, data.currency_code)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Net (Month)</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">{formatMinor(data.kpis.net_total_minor, data.currency_code)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Daily-Tagged Days</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">{data.kpis.daily_spending_days}</p>
              </CardContent>
            </Card>
          </section>

          <section className="grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle>Income vs Expense Trend</CardTitle>
              </CardHeader>
              <CardContent className="h-80 min-w-0">
                <DashboardChartContainer>
                  {({ width, height }) => (
                    <BarChart width={width} height={height} data={data.monthly_trend}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                      <XAxis dataKey="month" />
                      <YAxis tickFormatter={axisTick} />
                      <Tooltip
                        formatter={(value, name) => tooltipAmountWithName(data.currency_code, value, name)}
                        cursor={{ fill: "hsl(var(--muted) / 0.35)" }}
                      />
                      <Legend />
                      <Bar dataKey="income_total_minor" name="Income" fill={CHART_COLORS.income} radius={[6, 6, 0, 0]} />
                      <Bar dataKey="expense_total_minor" name="Expense" fill={CHART_COLORS.expense} radius={[6, 6, 0, 0]} />
                    </BarChart>
                  )}
                </DashboardChartContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Daily vs Non-daily Split</CardTitle>
              </CardHeader>
              <CardContent className="h-80 min-w-0">
                <DashboardChartContainer>
                  {({ width, height }) => (
                    <PieChart width={width} height={height}>
                      <Pie data={dailySpendSplit} dataKey="value" nameKey="name" innerRadius={56} outerRadius={90} paddingAngle={4}>
                        {dailySpendSplit.map((entry, index) => (
                          <Cell key={entry.name} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => tooltipAmount(data.currency_code, value)} />
                      <Legend />
                    </PieChart>
                  )}
                </DashboardChartContainer>
              </CardContent>
            </Card>
          </section>

          <Card>
            <CardHeader>
              <CardTitle>Projection (Current Month)</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2 md:grid-cols-3">
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
            </CardContent>
          </Card>
        </section>
      ) : null}

      {activeTab === "daily" ? (
        <section className="stack-lg" role="tabpanel" id="dashboard-panel-daily" aria-labelledby="dashboard-tab-daily">
          <section className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Average Daily Spend</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">{formatMinor(data.kpis.average_daily_expense_minor, data.currency_code)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Median Daily Spend</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">{formatMinor(data.kpis.median_daily_expense_minor, data.currency_code)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Daily-tagged total</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">{formatMinor(data.kpis.daily_expense_total_minor, data.currency_code)}</p>
              </CardContent>
            </Card>
          </section>

          <Card>
            <CardHeader>
              <CardTitle>Daily Spending (Selected Month)</CardTitle>
            </CardHeader>
            <CardContent className="h-80 min-w-0">
              <DashboardChartContainer>
                {({ width, height }) => (
                  <AreaChart width={width} height={height} data={data.daily_spending}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                    <XAxis dataKey="date" />
                    <YAxis tickFormatter={axisTick} />
                    <Tooltip formatter={(value, name) => tooltipAmountWithName(data.currency_code, value, name)} />
                    <Legend />
                    <Area
                      type="monotone"
                      dataKey="daily_expense_minor"
                      name="Daily-tagged"
                      stroke={CHART_COLORS.daily}
                      fill="hsl(var(--success) / 0.2)"
                      strokeWidth={2}
                    />
                    <Area
                      type="monotone"
                      dataKey="non_daily_expense_minor"
                      name="Non-daily"
                      stroke={CHART_COLORS.nonDaily}
                      fill="hsl(var(--destructive) / 0.16)"
                      strokeWidth={2}
                    />
                  </AreaChart>
                )}
              </DashboardChartContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Monthly Daily Spend Trend</CardTitle>
            </CardHeader>
            <CardContent className="h-80 min-w-0">
              <DashboardChartContainer>
                {({ width, height }) => (
                  <BarChart width={width} height={height} data={data.monthly_trend}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                    <XAxis dataKey="month" />
                    <YAxis tickFormatter={axisTick} />
                    <Tooltip formatter={(value, name) => tooltipAmountWithName(data.currency_code, value, name)} />
                    <Legend />
                    <Bar dataKey="daily_expense_minor" name="Daily-tagged" fill={CHART_COLORS.daily} radius={[6, 6, 0, 0]} />
                    <Bar dataKey="non_daily_expense_minor" name="Non-daily" fill={CHART_COLORS.nonDaily} radius={[6, 6, 0, 0]} />
                  </BarChart>
                )}
              </DashboardChartContainer>
            </CardContent>
          </Card>
        </section>
      ) : null}

      {activeTab === "breakdowns" ? (
        <section className="grid gap-4 xl:grid-cols-3" role="tabpanel" id="dashboard-panel-breakdowns" aria-labelledby="dashboard-tab-breakdowns">
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
                      <Pie data={data.spending_by_tag} dataKey="total_minor" nameKey="label" outerRadius={95}>
                        {data.spending_by_tag.map((item, index) => (
                          <Cell key={item.label} fill={PIE_COLORS[index % PIE_COLORS.length]} />
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
              <CardTitle>Spending by Destination (`to`)</CardTitle>
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
                      <Bar dataKey="total_minor" name="Total" fill={CHART_COLORS.expense} radius={[0, 6, 6, 0]} />
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
                      <Bar dataKey="total_minor" name="Total" fill={CHART_COLORS.net} radius={[6, 6, 0, 0]} />
                    </BarChart>
                  )}
                </DashboardChartContainer>
              )}
            </CardContent>
          </Card>
        </section>
      ) : null}

      {activeTab === "insights" ? (
        <section className="stack-lg" role="tabpanel" id="dashboard-panel-insights" aria-labelledby="dashboard-tab-insights">
          <section className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Spending by Weekday</CardTitle>
              </CardHeader>
              <CardContent className="h-80 min-w-0">
                <DashboardChartContainer>
                  {({ width, height }) => (
                    <BarChart width={width} height={height} data={data.weekday_spending}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                      <XAxis dataKey="weekday" />
                      <YAxis tickFormatter={axisTick} />
                      <Tooltip formatter={(value) => tooltipAmount(data.currency_code, value)} />
                      <Bar dataKey="total_minor" name="Total" fill={CHART_COLORS.expense} radius={[6, 6, 0, 0]} />
                    </BarChart>
                  )}
                </DashboardChartContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Largest Expenses (Month)</CardTitle>
              </CardHeader>
              <CardContent>
                {data.largest_expenses.length === 0 ? (
                  <p className="muted">No expense entries in this month.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Name</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Amount</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.largest_expenses.map((entry) => (
                        <TableRow key={entry.id}>
                          <TableCell>{entry.occurred_at}</TableCell>
                          <TableCell>{entry.name}</TableCell>
                          <TableCell>{entry.is_daily ? "Daily" : "Non-daily"}</TableCell>
                          <TableCell>{formatMinor(entry.amount_minor, data.currency_code)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </section>

          <Card>
            <CardHeader>
              <CardTitle>{data.currency_code} Reconciliation</CardTitle>
            </CardHeader>
            <CardContent>
              {data.reconciliation.length === 0 ? (
                <p className="muted">No active {data.currency_code} accounts configured.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Account</TableHead>
                      <TableHead>Ledger</TableHead>
                      <TableHead>Snapshot</TableHead>
                      <TableHead>Delta</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.reconciliation.map((row) => (
                      <TableRow key={row.account_id}>
                        <TableCell>{row.account_name}</TableCell>
                        <TableCell>{formatMinor(row.ledger_balance_minor, row.currency_code)}</TableCell>
                        <TableCell>{row.snapshot_balance_minor === null ? "-" : formatMinor(row.snapshot_balance_minor, row.currency_code)}</TableCell>
                        <TableCell>{row.delta_minor === null ? "-" : formatMinor(row.delta_minor, row.currency_code)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </section>
      ) : null}
    </div>
  );
}
