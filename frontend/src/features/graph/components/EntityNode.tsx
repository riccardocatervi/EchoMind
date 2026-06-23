/**
 * Nodo custom per React Flow che rappresenta un'entità del knowledge graph.
 *
 * Perché un nodo custom anziché il nodo default di React Flow:
 *   Il nodo default mostra solo un'etichetta testo centrata. Vogliamo:
 *     - Nome dell'entità (font medio, truncato a 160px)
 *     - Tipo (uppercase piccolo, muted: es. "PERSONA", "CONCETTO")
 *     - Bordo sinistro colorato per community (4px, colore da communityColor)
 *     - Stato "selected" con ring blu (ring-2 ring-ring)
 *
 * `nodeTypes = { entity: EntityNode }` in GraphViewer:
 *   Registra questo componente come tipo custom "entity". Definito FUORI dal
 *   componente GraphViewer per evitare ri-registrazione ad ogni render.
 *
 * `Handle` (target + source):
 *   Le "maniglie" di connessione di React Flow. `Position.Left` = ingresso arco,
 *   `Position.Right` = uscita arco. Coerente con il layout ELK "RIGHT" (left→right).
 *   `!size-2 !border-0 !bg-muted-foreground`: override dei default React Flow
 *   tramite classi Tailwind con `!` (important).
 *
 * `data as unknown as EntityNodeData`:
 *   React Flow v12 tipizza `data` come `Record<string, unknown>`. Il cast doppio
 *   (prima `unknown`, poi il tipo specifico) evita l'errore TypeScript senza usare
 *   `any`.
 */
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
