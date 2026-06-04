import { Handle, Position, type NodeProps } from "@xyflow/react";

import { cn } from "@/shared/lib/utils";
import { communityColor } from "@/features/graph/lib/communityColors";
import type { EntityNodeData } from "@/features/graph/lib/elkLayout";

/** Nodo custom: nome + tipo, bordo colorato per community, handle per gli archi. */
export function EntityNode({ data, selected }: NodeProps) {
  const entity = data as unknown as EntityNodeData;
  const color = communityColor(entity.community);

  return (
    <div
      className={cn(
        "rounded-md border bg-card px-3 py-2 shadow-sm transition-shadow",
        selected && "ring-2 ring-ring",
      )}
      style={{ borderLeftColor: color, borderLeftWidth: 4 }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!size-2 !border-0 !bg-muted-foreground"
      />
      <div className="max-w-[160px]">
        <p className="truncate text-sm font-medium leading-tight">{entity.name}</p>
        <p className="truncate text-[11px] uppercase tracking-wide text-muted-foreground">
          {entity.type}
        </p>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!size-2 !border-0 !bg-muted-foreground"
      />
    </div>
  );
}
