import { create } from "zustand";

interface GraphState {
  selectedNodeId: string | null;
  setSelectedNodeId: (id: string | null) => void;
}

/** Stato di UI del viewer (nodo selezionato). CP9 lo estendera' (filtri/drill-down). */
export const useGraphStore = create<GraphState>((set) => ({
  selectedNodeId: null,
  setSelectedNodeId: (id) => set({ selectedNodeId: id }),
}));
