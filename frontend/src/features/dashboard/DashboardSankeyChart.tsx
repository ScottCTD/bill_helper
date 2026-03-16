/**
 * CALLING SPEC:
 * - Purpose: render a two-level Sankey chart (total expense → builtin filter groups → tags) for the dashboard overview panel.
 * - Inputs: filter group summaries with tag_totals, currency code, and SVG dimensions.
 * - Outputs: an SVG Sankey diagram with hover tooltips and a color legend.
 * - Side effects: React rendering only.
 */

import { sankey, type SankeyNode, type SankeyLink } from "d3-sankey";
import { useState } from "react";

import { formatMinor } from "../../lib/format";
import type { DashboardFilterGroupSummary } from "../../lib/types";
import { BUILTIN_FILTER_GROUP_ORDER, type BuiltinFilterGroupKey, builtinGroupColor, DashboardChartContainer } from "./helpers";

const SOURCE_NODE_COLOR = "rgb(var(--chart-expense))";
const MAX_TAGS_PER_GROUP = 8;
/** Horizontal space reserved for node labels on each side, in px. */
const LEFT_PAD = 100;
const RIGHT_PAD = 130;

/** Minimum link value for layout to avoid degenerate flows. */
const MIN_LINK_VALUE = 1;

/** Power for layout scale (0.5 = sqrt, lower = smoother). Reduces dynamic range so large flows aren't overbearing and small flows stay visible. */
const LAYOUT_SCALE_POWER = 0.3;

function scaledLayoutValue(amount: number): number {
  return Math.pow(Math.max(amount, 0), LAYOUT_SCALE_POWER);
}

type NodeExtra = { id: string; label: string; color: string };
/** actualValue stores the real monetary amount for tooltips; layout uses raw values for flow conservation. */
type LinkExtra = { actualValue: number };

type ResolvedNode = SankeyNode<NodeExtra, LinkExtra>;
type ResolvedLink = SankeyLink<NodeExtra, LinkExtra>;

type TooltipState = { x: number; y: number; label: string; amount: number } | null;

type Props = {
  filterGroups: DashboardFilterGroupSummary[];
  currencyCode: string;
};

export function DashboardSankeyChart({ filterGroups, currencyCode }: Props) {
  return (
    <DashboardChartContainer>
      {({ width, height }) => (
        <SankeyInner filterGroups={filterGroups} currencyCode={currencyCode} width={width} height={height} />
      )}
    </DashboardChartContainer>
  );
}

function SankeyInner({
  filterGroups,
  currencyCode,
  width,
  height
}: Props & { width: number; height: number }) {
  const [tooltip, setTooltip] = useState<TooltipState>(null);

  const builtinGroups = BUILTIN_FILTER_GROUP_ORDER.map((key) =>
    filterGroups.find((g) => g.key === key)
  ).filter((g): g is DashboardFilterGroupSummary => g != null && g.total_minor > 0);

  if (builtinGroups.length === 0) {
    return <p className="muted text-sm">No expense data to display.</p>;
  }

  const total = builtinGroups.reduce((s, g) => s + g.total_minor, 0);

  // Build node list: source → filter groups → tags (scoped per group)
  // Guard tag_totals defensively — old API responses may omit the field
  const nodeExtras: NodeExtra[] = [{ id: "__source__", label: "Total Expense", color: SOURCE_NODE_COLOR }];
  for (const group of builtinGroups) {
    nodeExtras.push({ id: group.key, label: group.name, color: builtinGroupColor(group.key) });
  }
  for (const group of builtinGroups) {
    const topTags = Object.entries(group.tag_totals ?? {}).sort((a, b) => b[1] - a[1]).slice(0, MAX_TAGS_PER_GROUP);
    for (const [tag] of topTags) {
      nodeExtras.push({ id: `${group.key}::${tag}`, label: tag, color: builtinGroupColor(group.key) });
    }
    // Add "other" node when top tags don't sum to group total to preserve flow conservation
    const tagSum = topTags.reduce((s, [, amt]) => s + amt, 0);
    if (tagSum < group.total_minor && group.total_minor - tagSum > 0) {
      nodeExtras.push({ id: `${group.key}::__other__`, label: "other", color: builtinGroupColor(group.key) });
    }
  }

  const actualValues = new Map<string, number>();
  actualValues.set("__source__", total);

  const rawLinks: Array<{ source: string; target: string; value: number; actualValue: number }> = [];
  for (const group of builtinGroups) {
    actualValues.set(group.key, group.total_minor);
    const groupScaled = scaledLayoutValue(group.total_minor);
    rawLinks.push({
      source: "__source__",
      target: group.key,
      value: Math.max(groupScaled, MIN_LINK_VALUE),
      actualValue: group.total_minor
    });
    const topTags = Object.entries(group.tag_totals ?? {}).sort((a, b) => b[1] - a[1]).slice(0, MAX_TAGS_PER_GROUP);
    const tagSum = topTags.reduce((s, [, amt]) => s + amt, 0);
    const remainder = Math.max(0, group.total_minor - tagSum);
    const outgoingRaw = [
      ...topTags.map(([, amt]) => scaledLayoutValue(amt)),
      ...(remainder > 0 ? [scaledLayoutValue(remainder)] : [])
    ];
    const totalRaw = outgoingRaw.reduce((s, v) => s + v, 0);
    const norm = totalRaw > 0 ? groupScaled / totalRaw : 1;
    for (const [tag, amount] of topTags) {
      const tagId = `${group.key}::${tag}`;
      actualValues.set(tagId, amount);
      rawLinks.push({
        source: group.key,
        target: tagId,
        value: Math.max(scaledLayoutValue(amount) * norm, MIN_LINK_VALUE),
        actualValue: amount
      });
    }
    if (remainder > 0) {
      const otherId = `${group.key}::__other__`;
      actualValues.set(otherId, remainder);
      rawLinks.push({
        source: group.key,
        target: otherId,
        value: Math.max(scaledLayoutValue(remainder) * norm, MIN_LINK_VALUE),
        actualValue: remainder
      });
    }
  }

  /** Sort nodes within each column: filter groups by builtin order, tags by parent group then by value descending. */
  function nodeSort(a: ResolvedNode, b: ResolvedNode): number {
    const idA = (a as ResolvedNode & { id?: string }).id ?? "";
    const idB = (b as ResolvedNode & { id?: string }).id ?? "";
    if (idA === "__source__") return -1;
    if (idB === "__source__") return 1;
    const isTagA = idA.includes("::");
    const isTagB = idB.includes("::");
    if (!isTagA && !isTagB) {
      const iA = BUILTIN_FILTER_GROUP_ORDER.indexOf(idA as BuiltinFilterGroupKey);
      const iB = BUILTIN_FILTER_GROUP_ORDER.indexOf(idB as BuiltinFilterGroupKey);
      return (iA === -1 ? 999 : iA) - (iB === -1 ? 999 : iB);
    }
    if (isTagA && isTagB) {
      const groupA = idA.split("::")[0];
      const groupB = idB.split("::")[0];
      const orderA = BUILTIN_FILTER_GROUP_ORDER.indexOf(groupA as BuiltinFilterGroupKey);
      const orderB = BUILTIN_FILTER_GROUP_ORDER.indexOf(groupB as BuiltinFilterGroupKey);
      if (orderA !== orderB) return orderA - orderB;
      return (b.value ?? 0) - (a.value ?? 0);
    }
    return 0;
  }

  const chartHeight = Math.max(height - 56, 280);
  let graph: { nodes: ResolvedNode[]; links: ResolvedLink[] };
  try {
    graph = sankey<NodeExtra, LinkExtra>()
      .nodeId((d) => d.id)
      .nodeSort(nodeSort)
      .nodeWidth(16)
      .nodePadding(8)
      .extent([[LEFT_PAD, 4], [Math.max(width - RIGHT_PAD, LEFT_PAD + 1), chartHeight - 4]])(
      { nodes: nodeExtras.map((n) => ({ ...n })), links: rawLinks as unknown as ResolvedLink[] }
    ) as { nodes: ResolvedNode[]; links: ResolvedLink[] };
  } catch {
    return <p className="muted text-sm">Unable to render flow chart.</p>;
  }

  const resolvedNodes = graph.nodes;
  const resolvedLinks = graph.links;

  function resolveNode(ref: number | string | ResolvedNode): ResolvedNode {
    if (typeof ref === "object") return ref;
    return resolvedNodes[ref as number];
  }

  /** Fan-out transform: scale y based on x so the diagram starts narrow (left) and grows in height (right). */
  const xMin = LEFT_PAD;
  const xMax = Math.max(width - RIGHT_PAD, LEFT_PAD + 1);
  const yCenter = chartHeight / 2;
  const yScaleAtLeft = 0.55;
  function scaleYAtX(x: number): number {
    const t = (x - xMin) / Math.max(xMax - xMin, 1);
    return yScaleAtLeft + (1 - yScaleAtLeft) * Math.max(0, Math.min(1, t));
  }
  function transformY(x: number, y: number): number {
    return yCenter + (y - yCenter) * scaleYAtX(x);
  }

  return (
    <div style={{ width, height, overflow: "visible" }} className="relative">
      <svg width={width} height={chartHeight} style={{ overflow: "visible" }}>
        {/* Nodes first (background), then links (foreground) so ribbons are fully visible */}
        {resolvedNodes.map((node, i) => {
          if (node.x0 == null) return null;
          const w = (node.x1 ?? 0) - node.x0;
          const h = Math.max((node.y1 ?? 0) - (node.y0 ?? 0), 1);
          const xMid = (node.x0 + (node.x1 ?? node.x0)) / 2;
          const ty0 = transformY(xMid, node.y0 ?? 0);
          const ty1 = transformY(xMid, node.y1 ?? 0);
          const th = Math.max(ty1 - ty0, 1);
          const isSource = node.id === "__source__";
          const actualAmount = actualValues.get(node.id) ?? 0;
          return (
            <g key={`node-${i}`}
              onMouseEnter={(e) => setTooltip({ x: e.clientX, y: e.clientY, label: node.label, amount: actualAmount })}
              onMouseLeave={() => setTooltip(null)}
              style={{ cursor: "default" }}
            >
              <rect x={node.x0} y={ty0} width={w} height={th} fill={node.color} opacity={isSource ? 0.7 : 1} rx={3} />
              <text
                x={isSource ? node.x0 - 8 : (node.x1 ?? 0) + 8}
                y={ty0 + th / 2}
                dy="0.35em"
                textAnchor={isSource ? "end" : "start"}
                fontSize={h < 10 ? 9 : 11}
                fill="currentColor"
                style={{ pointerEvents: "none", userSelect: "none" }}
              >
                {node.label.length > 20 ? `${node.label.slice(0, 18)}…` : node.label}
              </text>
            </g>
          );
        })}
        {resolvedLinks.map((link, i) => {
          const srcNode = resolveNode(link.source);
          const tgtNode = resolveNode(link.target);
          const linkW = Math.max(link.width ?? 1, 1);
          const sx = srcNode.x1 ?? 0;
          const tx = tgtNode.x0 ?? 0;
          const sy0 = (link as ResolvedLink & { y0: number }).y0 ?? 0;
          const tgtY0 = tgtNode.y0 ?? 0;
          const tgtY1 = tgtNode.y1 ?? 0;
          const d = `M ${sx} ${transformY(sx, sy0 - linkW / 2)} L ${sx} ${transformY(sx, sy0 + linkW / 2)} L ${tx} ${transformY(tx, tgtY1)} L ${tx} ${transformY(tx, tgtY0)} Z`;
          return (
            <path
              key={`link-${i}`}
              d={d}
              fill={srcNode.color ?? SOURCE_NODE_COLOR}
              fillOpacity={0.45}
              stroke="none"
              onMouseEnter={(e) => setTooltip({ x: e.clientX, y: e.clientY, label: tgtNode.label, amount: link.actualValue })}
              onMouseLeave={() => setTooltip(null)}
              style={{ cursor: "pointer" }}
            />
          );
        })}
      </svg>

      {/* Legend */}
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {builtinGroups.map((g) => (
          <span key={g.key} className="flex items-center gap-1 text-xs">
            <span style={{ background: builtinGroupColor(g.key), width: 10, height: 10, borderRadius: 2, display: "inline-block", flexShrink: 0 }} />
            {g.name}
          </span>
        ))}
      </div>

      {/* Tooltip */}
      {tooltip ? (
        <div
          className="pointer-events-none fixed z-50 rounded-md border border-border bg-popover px-3 py-2 text-sm shadow-md"
          style={{ left: tooltip.x + 12, top: tooltip.y - 8 }}
        >
          <p className="font-medium">{tooltip.label}</p>
          <p className="text-muted-foreground">{formatMinor(tooltip.amount, currencyCode)}</p>
        </div>
      ) : null}
    </div>
  );
}

