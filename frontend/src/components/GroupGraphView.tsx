import { useMemo } from "react";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node
} from "reactflow";
import "reactflow/dist/style.css";

import type { GroupGraph } from "../lib/types";

interface GroupGraphViewProps {
  graph: GroupGraph;
}

export function GroupGraphView({ graph }: GroupGraphViewProps) {
  if (graph.nodes.length === 0) {
    return <p className="muted">No linked entries in this group.</p>;
  }

  const laidOutNodes = useMemo(() => {
    const count = graph.nodes.length;
    if (count === 1) {
      return graph.nodes.map((node) => ({
        ...node,
        x: 260,
        y: 180
      }));
    }

    if (count <= 10) {
      const centerX = 260;
      const centerY = 180;
      const radius = 120;
      return graph.nodes.map((node, index) => {
        const angle = (2 * Math.PI * index) / count;
        return {
          ...node,
          x: centerX + Math.cos(angle) * radius,
          y: centerY + Math.sin(angle) * radius
        };
      });
    }

    const columns = Math.ceil(Math.sqrt(count));
    const horizontalGap = 170;
    const verticalGap = 120;
    return graph.nodes.map((node, index) => {
      const row = Math.floor(index / columns);
      const column = index % columns;
      return {
        ...node,
        x: 70 + column * horizontalGap,
        y: 40 + row * verticalGap
      };
    });
  }, [graph.nodes]);

  const nodes = useMemo<Node[]>(
    () =>
      laidOutNodes.map((node) => ({
        id: node.id,
        position: { x: node.x, y: node.y },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        draggable: false,
        selectable: false,
        className: node.kind === "INCOME" ? "group-flow-node group-flow-node-income" : "group-flow-node group-flow-node-expense",
        data: {
          label: (
            <div className="group-flow-node-content">
              <p className="group-flow-node-name">{node.name}</p>
              <p className="group-flow-node-meta">
                {node.occurred_at} | {node.kind === "INCOME" ? "+" : "-"}
              </p>
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
        source: edge.source_entry_id,
        target: edge.target_entry_id,
        label: edge.link_type,
        markerEnd: { type: MarkerType.ArrowClosed, color: "hsl(var(--muted-foreground))" },
        className: "group-flow-edge",
        labelBgStyle: { fill: "hsl(var(--card))" },
        labelStyle: { fill: "hsl(var(--foreground))", fontSize: 11, fontWeight: 500 },
        labelBgPadding: [6, 2],
        labelBgBorderRadius: 6
      })),
    [graph.edges]
  );

  return (
    <div className="group-flow-container" role="img" aria-label="Entry relationship graph">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.22 }}
        defaultEdgeOptions={{ type: "smoothstep" }}
        nodesConnectable={false}
        nodesDraggable={false}
        elementsSelectable={false}
        minZoom={0.35}
        maxZoom={1.8}
        proOptions={{ hideAttribution: true }}
        className="group-flow-canvas"
      >
        <MiniMap className="group-flow-minimap" pannable={false} zoomable />
        <Controls showInteractive={false} />
        <Background gap={16} size={1} />
      </ReactFlow>
    </div>
  );
}
