/**
 * CALLING SPEC:
 * - Purpose: render the agent usage and cost dashboard tab for the main dashboard page.
 * - Inputs: route-local query state for time range plus model/surface filters.
 * - Outputs: React elements with agent usage KPIs, charts, and breakdown tables.
 * - Side effects: agent dashboard data fetching and filter event wiring.
 */

import { useState } from "react";
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

import { StatBlock } from "../../components/layout/StatBlock";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import { getAgentDashboard } from "../../lib/api";
import { formatUsd } from "../../lib/format";
import { queryKeys } from "../../lib/queryKeys";
import type { AgentDashboardRangeKey, AgentRunStatus } from "../../lib/types";
import { cn } from "../../lib/utils";
import {
  DASHBOARD_PIE_ANIMATION_PROPS,
  DashboardChartContainer,
  dashboardBarColor,
  dashboardPieColor
} from "./helpers";

const RANGE_OPTIONS: Array<{ key: AgentDashboardRangeKey; label: string }> = [
  { key: "7d", label: "7D" },
  { key: "30d", label: "30D" },
  { key: "90d", label: "90D" },
  { key: "all", label: "All" }
];

const SURFACE_OPTIONS = [
  { key: "app", label: "App" },
  { key: "telegram", label: "Telegram" }
];

function formatTokenCount(value: number): string {
  return new Intl.NumberFormat().format(value);
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatUsdTick(value: number | string): string {
  const numericValue = typeof value === "number" ? value : Number(value);
  return formatUsd(Number.isFinite(numericValue) ? numericValue : 0);
}

function toggleValue(values: string[], nextValue: string): string[] {
  return values.includes(nextValue) ? values.filter((value) => value !== nextValue) : [...values, nextValue];
}

function statusTone(status: AgentRunStatus): "outline" | "secondary" | "destructive" {
  if (status === "completed") {
    return "secondary";
  }
  if (status === "failed") {
    return "destructive";
  }
  return "outline";
}

export function AgentCostDashboard() {
  const [range, setRange] = useState<AgentDashboardRangeKey>("30d");
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [selectedSurfaces, setSelectedSurfaces] = useState<string[]>([]);

  const query = useQuery({
    queryKey: queryKeys.agent.dashboard({
      range,
      models: selectedModels,
      surfaces: selectedSurfaces
    }),
    queryFn: () =>
      getAgentDashboard({
        range,
        models: selectedModels,
        surfaces: selectedSurfaces
      }),
    staleTime: 30_000
  });

  if (query.isLoading) {
    return <p>Loading agent analytics...</p>;
  }

  if (query.isError || !query.data) {
    return <p>Failed to load agent analytics: {(query.error as Error).message}</p>;
  }

  const data = query.data;
  const hasFilters = selectedModels.length > 0 || selectedSurfaces.length > 0;
  const chartModels =
    data.model_breakdown.length > 0 ? data.model_breakdown.map((row) => row.model_name) : data.available_models;
  const costSeriesData = data.cost_series.map((point) => ({
    bucket_label: point.bucket_label,
    total_cost_usd: point.total_cost_usd,
    ...point.costs_by_model
  }));
  const surfaceChartData = data.surface_breakdown.map((point) => ({
    surface: point.surface === "app" ? "App" : point.surface === "telegram" ? "Telegram" : point.surface,
    total_cost_usd: point.total_cost_usd,
    ...point.costs_by_model
  }));

  return (
    <section className="stack-lg" role="tabpanel" id="dashboard-panel-agent" aria-labelledby="dashboard-tab-agent">
      <Card>
        <CardHeader>
          <CardTitle>Agent Spend Controls</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <p className="text-sm font-medium">Time range</p>
            <div className="flex flex-wrap gap-2">
              {RANGE_OPTIONS.map((option) => (
                <Button
                  key={option.key}
                  type="button"
                  size="sm"
                  variant={range === option.key ? "default" : "outline"}
                  onClick={() => setRange(option.key)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium">Model filter</p>
              {data.available_models.length > 0 ? (
                <p className="text-xs text-muted-foreground">{data.available_models.length} model(s) in range</p>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              {data.available_models.length === 0 ? (
                <p className="text-sm text-muted-foreground">No runs in this range yet.</p>
              ) : (
                data.available_models.map((modelName) => (
                  <Button
                    key={modelName}
                    type="button"
                    size="sm"
                    variant={selectedModels.includes(modelName) ? "default" : "outline"}
                    className="max-w-full"
                    onClick={() => setSelectedModels((current) => toggleValue(current, modelName))}
                  >
                    <span className="truncate">{modelName}</span>
                  </Button>
                ))
              )}
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Surface filter</p>
            <div className="flex flex-wrap gap-2">
              {SURFACE_OPTIONS.map((surface) => (
                <Button
                  key={surface.key}
                  type="button"
                  size="sm"
                  variant={selectedSurfaces.includes(surface.key) ? "default" : "outline"}
                  onClick={() => setSelectedSurfaces((current) => toggleValue(current, surface.key))}
                >
                  {surface.label}
                </Button>
              ))}
              {hasFilters ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setSelectedModels([]);
                    setSelectedSurfaces([]);
                  }}
                >
                  Clear filters
                </Button>
              ) : null}
            </div>
          </div>
        </CardContent>
      </Card>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatBlock
          label="Total Cost"
          value={formatUsd(data.metrics.total_cost_usd)}
          detail={`${data.metrics.completed_run_count} completed / ${data.metrics.failed_run_count} failed`}
          tone="warning"
        />
        <StatBlock label="Total Tokens" value={formatTokenCount(data.metrics.total_tokens)} detail="Input + output" />
        <StatBlock label="Total Runs" value={formatTokenCount(data.metrics.total_run_count)} detail={data.metrics.most_used_model ?? "No dominant model"} />
        <StatBlock label="Avg Cost / Run" value={formatUsd(data.metrics.avg_cost_per_run_usd)} detail={formatTokenCount(Math.round(data.metrics.avg_tokens_per_run)) + " avg tokens"} />
        <StatBlock label="Avg Tokens / Run" value={formatTokenCount(Math.round(data.metrics.avg_tokens_per_run))} detail={data.metrics.total_run_count > 0 ? `${data.metrics.total_run_count} run sample` : "No runs"} />
        <StatBlock label="Cache Hit Rate" value={formatPercent(data.metrics.cache_hit_rate)} detail="cache read / input tokens" />
        <StatBlock label="Most Used Model" value={data.metrics.most_used_model ?? "-"} detail={`${data.model_breakdown.length} active model rows`} />
        <StatBlock
          label="Failure Rate"
          value={formatPercent(data.metrics.failure_rate)}
          detail={`${data.metrics.failed_run_count} failed run(s)`}
          tone={data.metrics.failed_run_count > 0 ? "danger" : "success"}
        />
      </section>

      {data.metrics.total_run_count === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Agent Spend</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">No completed or failed agent runs match the current range and filters.</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <section className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Cost Over Time</CardTitle>
              </CardHeader>
              <CardContent className="h-80 min-w-0">
                <DashboardChartContainer>
                  {({ width, height }) => (
                    <AreaChart width={width} height={height} data={costSeriesData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--muted-foreground))" opacity={0.18} />
                      <XAxis dataKey="bucket_label" />
                      <YAxis tickFormatter={formatUsdTick} />
                      <Tooltip formatter={(value, name) => [formatUsd(Number(value ?? 0)), String(name ?? "")]} />
                      <Legend />
                      {chartModels.map((modelName, index) => (
                        <Area
                          key={modelName}
                          type="monotone"
                          dataKey={modelName}
                          name={modelName}
                          stackId="cost"
                          stroke={dashboardBarColor(index)}
                          fill={dashboardBarColor(index)}
                          fillOpacity={0.34}
                        />
                      ))}
                    </AreaChart>
                  )}
                </DashboardChartContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Token Distribution</CardTitle>
              </CardHeader>
              <CardContent className="h-80 min-w-0">
                <DashboardChartContainer>
                  {({ width, height }) => (
                    <PieChart width={width} height={height}>
                      <Pie
                        data={data.token_distribution}
                        dataKey="token_count"
                        nameKey="label"
                        innerRadius={54}
                        outerRadius={92}
                        paddingAngle={4}
                        {...DASHBOARD_PIE_ANIMATION_PROPS}
                      >
                        {data.token_distribution.map((slice, index) => (
                          <Cell key={slice.label} fill={dashboardPieColor(index)} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value, _name, item) => [`${formatTokenCount(Number(value ?? 0))} tokens`, item.payload.label]} />
                      <Legend formatter={(value, _entry, index) => `${value} (${formatPercent(data.token_distribution[index]?.share ?? 0)})`} />
                    </PieChart>
                  )}
                </DashboardChartContainer>
              </CardContent>
            </Card>
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Cost By Surface</CardTitle>
              </CardHeader>
              <CardContent className="h-80 min-w-0">
                <DashboardChartContainer>
                  {({ width, height }) => (
                    <BarChart width={width} height={height} data={surfaceChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--muted-foreground))" opacity={0.18} />
                      <XAxis dataKey="surface" />
                      <YAxis tickFormatter={formatUsdTick} />
                      <Tooltip formatter={(value, name) => [formatUsd(Number(value ?? 0)), String(name ?? "")]} />
                      <Legend />
                      {chartModels.map((modelName, index) => (
                        <Bar
                          key={modelName}
                          dataKey={modelName}
                          name={modelName}
                          fill={dashboardBarColor(index)}
                          radius={[4, 4, 0, 0]}
                        />
                      ))}
                    </BarChart>
                  )}
                </DashboardChartContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Model Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="rounded-lg border border-border/70">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Model</TableHead>
                        <TableHead>Runs</TableHead>
                        <TableHead>Input</TableHead>
                        <TableHead>Output</TableHead>
                        <TableHead>Cache Reads</TableHead>
                        <TableHead>Total Cost</TableHead>
                        <TableHead>Avg Cost</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.model_breakdown.map((row) => (
                        <TableRow key={row.model_name}>
                          <TableCell className="max-w-[220px]">
                            <div className="space-y-1">
                              <p className="truncate font-medium">{row.model_name}</p>
                              <p className="text-xs text-muted-foreground">
                                {row.completed_run_count} completed / {row.failed_run_count} failed
                              </p>
                            </div>
                          </TableCell>
                          <TableCell>{formatTokenCount(row.run_count)}</TableCell>
                          <TableCell>{formatTokenCount(row.input_tokens)}</TableCell>
                          <TableCell>{formatTokenCount(row.output_tokens)}</TableCell>
                          <TableCell>{formatTokenCount(row.cache_read_tokens)}</TableCell>
                          <TableCell>{formatUsd(row.total_cost_usd)}</TableCell>
                          <TableCell>{formatUsd(row.avg_cost_per_run_usd)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </section>

          <Card>
            <CardHeader>
              <CardTitle>Top Expensive Runs</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border border-border/70">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Started</TableHead>
                      <TableHead>Thread</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>Surface</TableHead>
                      <TableHead>Cost</TableHead>
                      <TableHead>Tokens</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.top_runs.map((run) => (
                      <TableRow key={run.run_id}>
                        <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                          {new Date(run.created_at).toLocaleString()}
                        </TableCell>
                        <TableCell className="max-w-[260px]">
                          <div className="space-y-1">
                            <p className="truncate font-medium">{run.thread_title || "Untitled thread"}</p>
                            <p className="truncate text-xs text-muted-foreground">{run.thread_id}</p>
                          </div>
                        </TableCell>
                        <TableCell className="max-w-[220px]">
                          <span className="block truncate">{run.model_name}</span>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="capitalize">
                            {run.surface}
                          </Badge>
                        </TableCell>
                        <TableCell>{formatUsd(run.total_cost_usd)}</TableCell>
                        <TableCell>{formatTokenCount(run.total_tokens)}</TableCell>
                        <TableCell>
                          <Badge variant={statusTone(run.status)} className={cn(run.status === "completed" ? "text-success" : "")}>
                            {run.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </section>
  );
}
