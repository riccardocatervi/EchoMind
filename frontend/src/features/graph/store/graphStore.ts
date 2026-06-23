/**
 * Store di UI del viewer del grafo (Zustand).
 *
 * Perché Zustand e non useState locale in GraphViewer:
 *   Lo stato del grafo (nodo selezionato, termine di ricerca, community nascoste)
 *   è condiviso tra più componenti: GraphViewer, GraphControls, NodeDetailsPanel,
 *   GraphQaPanel. Passarlo come props richiederebbe "prop drilling" attraverso
 *   diversi livelli → Zustand fornisce un accesso diretto da qualsiasi componente.
 *
 * `selectedNodeId`:
 *   UUID del nodo cliccato. Usato da GraphViewer per evidenziare il nodo e i
 *   suoi vicini (opacity: 0.25 per gli altri), da NodeDetailsPanel per mostrare
 *   il dettaglio. `null` = nessun nodo selezionato.
 *
 * `searchTerm`:
 *   Stringa di ricerca del GraphControls. GraphViewer filtra i nodi il cui
 *   `name` non contiene il termine (opacity: 0.25). La ricerca è case-insensitive.
 *
 * `hiddenCommunities`:
 *   `Set<number>` delle community temporaneamente nascoste (toggle dalla legenda
 *   in GraphControls). Usiamo Set<number> per O(1) lookup in `.has(community)`.
 *   Zustand gestisc il Set immutabilmente: `toggleCommunity` crea sempre un nuovo
 *   Set invece di mutare quello esistente (React non vede i cambiamenti al Set).
 *
 * `reset()`:
 *   Chiamato da GraphViewer ogni volta che arriva un nuovo grafo (es. re-estrazione).
 *   Garantisce che selezione/ricerca/filtri dell'analisi precedente non inquinino
 *   il nuovo grafo.
 */
import { create } from "zustand";

interface GraphState {
  selectedNodeId: string | null;
  searchTerm: string;
  /** Community nascoste (toggle dalla legenda). Vuoto = tutte visibili. */
  hiddenCommunities: Set<number>;
  setSelectedNodeId: (id: string | null) => void;
  setSearchTerm: (term: string) => void;
  toggleCommunity: (community: number) => void;
  reset: () => void;
}

/** Stato di UI del viewer del grafo: selezione nodo, ricerca e filtro community. */
export const useGraphStore = create<GraphState>((set) => ({
  selectedNodeId: null,
  searchTerm: "",
  hiddenCommunities: new Set<number>(),
  setSelectedNodeId: (id) => set({ selectedNodeId: id }),
  setSearchTerm: (term) => set({ searchTerm: term }),
  toggleCommunity: (community) =>
    set((state) => {
      // Crea sempre un nuovo Set (immutabilità): React/Zustand rilevano la reference.
      const next = new Set(state.hiddenCommunities);
      if (next.has(community)) {
        next.delete(community);
      } else {
        next.add(community);
      }
      return { hiddenCommunities: next };
    }),
  // Pulizia totale: chiamato al cambio di grafo (re-estrazione).
  reset: () => set({ selectedNodeId: null, searchTerm: "", hiddenCommunities: new Set<number>() }),
}));
