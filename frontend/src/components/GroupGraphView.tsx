import type { GroupGraph } from "../lib/types";

interface GroupGraphViewProps {
  graph: GroupGraph;
}

export function GroupGraphView({ graph }: GroupGraphViewProps) {
  const width = 720;
  const height = 360;
  const radius = 140;
  const centerX = width / 2;
  const centerY = height / 2;
  const nodeRadius = 18;
  const edgeColor = "hsl(var(--muted-foreground))";
  const expenseColor = "hsl(var(--destructive))";
  const incomeColor = "hsl(var(--success))";

  if (graph.nodes.length === 0) {
    return <p className="muted">No linked entries in this group.</p>;
  }

  const positionedNodes = graph.nodes.map((node, index) => {
    const angle = (2 * Math.PI * index) / graph.nodes.length;
    return {
      ...node,
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius
    };
  });

  const nodeById = new Map(positionedNodes.map((node) => [node.id, node]));

  return (
    <svg className="group-graph" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Entry relationship graph">
      {graph.edges.map((edge) => {
        const source = nodeById.get(edge.source_entry_id);
        const target = nodeById.get(edge.target_entry_id);
        if (!source || !target) {
          return null;
        }
        return (
          <line
            key={edge.id}
            x1={source.x}
            y1={source.y}
            x2={target.x}
            y2={target.y}
            stroke={edgeColor}
            strokeWidth={2}
          />
        );
      })}

      {positionedNodes.map((node) => (
        <g key={node.id}>
          <circle cx={node.x} cy={node.y} r={nodeRadius} fill={node.kind === "EXPENSE" ? expenseColor : incomeColor} />
          <text x={node.x} y={node.y - 26} textAnchor="middle" className="graph-label">
            {node.name.slice(0, 16)}
          </text>
          <text x={node.x} y={node.y + 5} textAnchor="middle" className="graph-node-id">
            {node.id.slice(0, 4)}
          </text>
        </g>
      ))}
    </svg>
  );
}
