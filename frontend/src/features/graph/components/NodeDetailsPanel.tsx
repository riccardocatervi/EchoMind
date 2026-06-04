import { X } from "lucide-react";

import { Button } from "@/shared/components/ui/button";
import { communityColor } from "@/features/graph/lib/communityColors";
import type { GraphNode, GraphRead } from "@/features/graph/schemas/graph";

interface Neighbor {
  id: string;
  name: string;
  relation: string;
  outgoing: boolean;
}

export function NodeDetailsPanel({
  node,
  graph,
  onClose,
}: {
  node: GraphNode;
  graph: GraphRead;
  onClose: () => void;
}) {
  const nameById = new Map(graph.nodes.map((n) => [n.id, n.name]));
  const neighbors: Neighbor[] = graph.edges
    .filter((edge) => edge.source === node.id || edge.target === node.id)
    .map((edge) => {
      const outgoing = edge.source === node.id;
      const otherId = outgoing ? edge.target : edge.source;
      return { id: otherId, name: nameById.get(otherId) ?? otherId, relation: edge.type, outgoing };
    });

  return (
    <aside className="absolute right-4 top-4 z-10 max-h-[calc(100%-2rem)] w-72 overflow-y-auto rounded-lg border bg-card p-4 shadow-lg">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium leading-tight">{node.name}</p>
          <span
            className="text-xs uppercase tracking-wide"
            style={{ color: communityColor(node.community) }}
          >
            {node.type}
          </span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="size-7 shrink-0"
          onClick={onClose}
          aria-label="Chiudi pannello"
        >
          <X aria-hidden="true" />
        </Button>
      </div>

      {node.description && <p className="mt-2 text-sm text-muted-foreground">{node.description}</p>}

      {neighbors.length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">
            Relazioni ({neighbors.length})
          </p>
          <ul className="space-y-1 text-sm">
            {neighbors.map((neighbor, index) => (
              <li key={index} className="flex flex-wrap items-center gap-1">
                <span className="text-muted-foreground">{neighbor.outgoing ? "->" : "<-"}</span>
                <span className="rounded bg-muted px-1 text-xs">{neighbor.relation}</span>
                <span className="truncate">{neighbor.name}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
