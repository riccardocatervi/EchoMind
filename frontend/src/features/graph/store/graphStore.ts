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

/** Stato di UI del viewer del grafo (selezione, ricerca, filtro community). */
export const useGraphStore = create<GraphState>((set) => ({
  selectedNodeId: null,
  searchTerm: "",
  hiddenCommunities: new Set<number>(),
  setSelectedNodeId: (id) => set({ selectedNodeId: id }),
  setSearchTerm: (term) => set({ searchTerm: term }),
  toggleCommunity: (community) =>
    set((state) => {
      const next = new Set(state.hiddenCommunities);
      if (next.has(community)) {
        next.delete(community);
      } else {
        next.add(community);
      }
      return { hiddenCommunities: next };
    }),
  reset: () => set({ selectedNodeId: null, searchTerm: "", hiddenCommunities: new Set<number>() }),
}));
