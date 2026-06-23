/**
 * Pannello laterale del dettaglio di un nodo del grafo (overlay a destra).
 *
 * Appare quando l'utente clicca un nodo in GraphViewer.
 * Mostra: nome, tipo (colorato con communityColor), descrizione,
 * lista di relazioni (archi entranti + uscenti) cliccabili.
 *
 * Navigazione per relazioni:
 *   Cliccando una relazione si chiama `onSelectNode(neighbor.id)`, che
 *   aggiorna `selectedNodeId` nello store → GraphViewer evidenzia il vicino
 *   e il pannello si aggiorna per mostrarne il dettaglio. Permette di
 *   "navigare" il grafo di relazione in relazione senza usare il mouse sul canvas.
 *
 * Frecce `->` / `<-`:
 *   Indicano la direzione della relazione rispetto al nodo corrente.
 *   `outgoing = edge.source === node.id` → freccia uscente `->`.
 *
 * Posizionamento responsive:
 *   Mobile (< sm): pannello in basso (`inset-x-4 bottom-4`).
 *   Desktop (≥ sm): pannello laterale destro (`right-4 top-4 w-72`).
 *
 * `nameById` (Map<id, name>):
 *   Lookup O(1) per trovare il nome del vicino dato il suo ID.
 *   Costruito una volta con `graph.nodes.map(...)` invece di fare un `.find()`
 *   per ogni arco (O(N) vs O(1) per ogni vicino).
 */
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

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
  onSelectNode,
}: {
  node: GraphNode;
  graph: GraphRead;
  onClose: () => void;
  onSelectNode: (id: string) => void;
}) {
  const { t } = useTranslation();
  const nameById = new Map(graph.nodes.map((n) => [n.id, n.name]));
  const neighbors: Neighbor[] = graph.edges
    .filter((edge) => edge.source === node.id || edge.target === node.id)
    .map((edge) => {
      const outgoing = edge.source === node.id;
      const otherId = outgoing ? edge.target : edge.source;
      return { id: otherId, name: nameById.get(otherId) ?? otherId, relation: edge.type, outgoing };
    });

  return (
    <aside className="absolute inset-x-4 bottom-4 z-10 max-h-[50%] overflow-y-auto rounded-lg border bg-card p-4 shadow-lg sm:inset-x-auto sm:bottom-auto sm:right-4 sm:top-4 sm:max-h-[calc(100%-2rem)] sm:w-72">
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
          aria-label={t("graph.details.close")}
        >
          <X aria-hidden="true" />
        </Button>
      </div>

      {node.description && <p className="mt-2 text-sm text-muted-foreground">{node.description}</p>}

      {neighbors.length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">
            {t("graph.details.relations", { n: neighbors.length })}
          </p>
          <ul className="space-y-0.5">
            {neighbors.map((neighbor, index) => (
              <li key={index}>
                <button
                  type="button"
                  onClick={() => onSelectNode(neighbor.id)}
                  className="flex w-full cursor-pointer flex-wrap items-center gap-1 rounded px-1 py-1 text-left text-sm transition-colors hover:bg-accent"
                  title={t("graph.details.goTo", { name: neighbor.name })}
                >
                  <span className="text-muted-foreground">{neighbor.outgoing ? "->" : "<-"}</span>
                  <span className="rounded bg-muted px-1 text-xs">{neighbor.relation}</span>
                  <span className="truncate">{neighbor.name}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
