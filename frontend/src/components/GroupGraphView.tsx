import { useMemo } from "react";
import {
  Background,
  Controls,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node
} from "reactflow";
import "reactflow/dist/style.css";

import type { GroupGraph, GroupNode } from "../lib/types";

interface GroupGraphViewProps {
  graph: GroupGraph;
}

const FLOW_FIT_VIEW_OPTIONS = { padding: 0.22 } as const;
const FLOW_DEFAULT_EDGE_OPTIONS = { type: "smoothstep" } as const;
const FLOW_PRO_OPTIONS = { hideAttribution: true } as const;

function handleReactFlowError(code: string, message: string) {
  if (import.meta.env.DEV && code === "002") {
    return;
  }

  console.warn(`[React Flow]: ${message} Help: https://reactflow.dev/error#${code}`);
}

function nodeMetaLabel(node: GroupNode): string {
  const role = node.member_role ? `${node.member_role} | ` : "";
  if (node.node_type === "ENTRY") {
    const symbol = node.kind === "INCOME" ? "+" : node.kind === "TRANSFER" ? "~" : "-";
    return `${role}${node.occurred_at ?? node.representative_occurred_at ?? "No date"} | ${symbol}`;
  }

  const dateRange =
    node.first_occurred_at && node.last_occurred_at
      ? node.first_occurred_at === node.last_occurred_at
        ? node.first_occurred_at
        : `${node.first_occurred_at} to ${node.last_occurred_at}`
      : "No entries yet";
  return `${role}${node.group_type ?? "GROUP"} | ${node.descendant_entry_count ?? 0} entries | ${dateRange}`;
}

function layoutNodes(graph: GroupGraph): Array<GroupNode & { x: number; y: number }> {
  const directNodes = [...graph.nodes];
  if (directNodes.length === 1) {
    return directNodes.map((node) => ({ ...node, x: 240, y: 180 }));
  }

  if (graph.group_type === "SPLIT") {
    const parentNode = directNodes.find((node) => node.member_role === "PARENT") ?? directNodes[0];
    const childNodes = directNodes.filter((node) => node.graph_id !== parentNode.graph_id);
    return [
      { ...parentNode, x: 120, y: 180 },
      ...childNodes.map((node, index) => ({
        ...node,
        x: 380,
        y: 90 + index * 110
      }))
    ];
  }

  if (graph.group_type === "RECURRING") {
    const sortedNodes = [...directNodes].sort((left, right) => {
      return (left.representative_occurred_at ?? "9999-12-31").localeCompare(
        right.representative_occurred_at ?? "9999-12-31"
      );
    });
    return sortedNodes.map((node, index) => ({
      ...node,
      x: 80 + index * 220,
      y: 180 + (index % 2 === 0 ? 0 : 24)
    }));
  }

  if (directNodes.length <= 8) {
    const radius = 150;
    const centerX = 260;
    const centerY = 180;
    return directNodes.map((node, index) => {
      const angle = (2 * Math.PI * index) / directNodes.length;
      return {
        ...node,
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius
      };
    });
  }

  const columns = Math.ceil(Math.sqrt(directNodes.length));
  return directNodes.map((node, index) => ({
    ...node,
    x: 70 + (index % columns) * 210,
    y: 40 + Math.floor(index / columns) * 120
  }));
}

function nodeClassName(node: GroupNode): string {
  if (node.node_type === "GROUP") {
    return `group-flow-node group-flow-node-group group-flow-node-group-${(node.group_type ?? "BUNDLE").toLowerCase()}`;
  }
  if (node.kind === "INCOME") {
    return "group-flow-node group-flow-node-income";
  }
  if (node.kind === "TRANSFER") {
    return "group-flow-node group-flow-node-transfer";
  }
  return "group-flow-node group-flow-node-expense";
}

export function GroupGraphView({ graph }: GroupGraphViewProps) {
  if (graph.nodes.length === 0) {
    return <p className="muted">No direct members in this group yet.</p>;
  }

  const laidOutNodes = useMemo(() => layoutNodes(graph), [graph]);

  const nodes = useMemo<Node[]>(
    () =>
      laidOutNodes.map((node) => ({
        id: node.graph_id,
        position: { x: node.x, y: node.y },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        draggable: false,
        selectable: false,
        className: nodeClassName(node),
        data: {
          label: (
            <div className="group-flow-node-content">
              <p className="group-flow-node-name">{node.name}</p>
              <p className="group-flow-node-meta">{nodeMetaLabel(node)}</p>
            </div>
          )
        }
      })),
    [laidOutNodes]
  );

  const edges = useMemo<Edge[]>(
    () =>
      graph.edges.map((edge) => ({
        id: edge.id,
        source: edge.source_graph_id,
        target: edge.target_graph_id,
        markerEnd:
          edge.group_type === "BUNDLE"
            ? undefined
            : { type: MarkerType.ArrowClosed, color: "hsl(var(--muted-foreground))" },
        className: "group-flow-edge",
      })),
    [graph.edges]
  );

  return (
    <div className="group-flow-container" role="img" aria-label={`${graph.name} relationship graph`}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={FLOW_FIT_VIEW_OPTIONS}
        defaultEdgeOptions={FLOW_DEFAULT_EDGE_OPTIONS}
        nodesConnectable={false}
        nodesDraggable={false}
        elementsSelectable={false}
        minZoom={0.35}
        maxZoom={1.8}
        proOptions={FLOW_PRO_OPTIONS}
        onError={handleReactFlowError}
        className="group-flow-canvas"
      >
        <Controls showInteractive={false} />
        <Background gap={16} size={1} />
      </ReactFlow>
    </div>
  );
}
