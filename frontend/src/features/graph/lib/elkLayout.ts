/**
 * Layout automatico del grafo tramite ELK.js (Eclipse Layout Kernel).
 *
 * Perché ELK e non Dagre o layout manuale:
 *   ELK è una libreria Java portata su WebAssembly (elkjs). Supporta algoritmi
 *   di layout avanzati come "layered" (Sugiyama) che gestisce cicli nel grafo
 *   (knowledge graph → può avere cicli: A→B→C→A). Dagre non gestisce i cicli
 *   bene. D3-force (layout a forze) produce layout caotici per grafi di conoscenza
 *   strutturati dove la gerarchia è significativa.
 *
 * Algoritmo "layered" (Sugiyama):
 *   Dispone i nodi su "layer" orizzontali (RIGHT = sinistra→destra). I nodi
 *   nello stesso layer sono allineati verticalmente. Le relazioni "fluiscono"
 *   da sinistra a destra → intuitivo per grafi causa-effetto / dipendenze.
 *   `elk.layered.spacing.nodeNodeBetweenLayers = 90`: spazio orizzontale tra layer.
 *   `elk.spacing.nodeNode = 55`: spazio verticale tra nodi dello stesso layer.
 *
 * Perché il layout è ASYNC:
 *   ELK usa un WebWorker o la versione bundled (wasm) per il calcolo. La chiamata
 *   `elk.layout(elkGraph)` è sempre async. Il componente GraphViewer mostra un
 *   loader durante il layout e si aggiorna quando la Promise si risolve.
 *   Così non blocchiamo il thread principale durante l'elaborazione.
 *
 * `baseRef` in GraphViewer:
 *   I nodi/archi calcolati da ELK vengono salvati in un ref (non state) perché
 *   il layout non cambia mai una volta calcolato. Ogni re-render che applica
 *   filtri (community, ricerca, selezione) parte da `baseRef.current` come base
 *   e genera un nuovo array di nodi con visibilità/opacità aggiornata.
 *
 * `EntityNodeData`:
 *   Struttura dati che viaggia nel campo `data` di ogni nodo React Flow.
 *   L'index signature `[key: string]: unknown` è richiesta da React Flow v12
 *   che si aspetta `Record<string, unknown>` per i dati dei nodi custom.
 */
import ELK from "elkjs/lib/elk.bundled.js";
import type { Edge, Node } from "@xyflow/react";

import type { GraphRead } from "@/features/graph/schemas/graph";

/**
 * Dati che viaggiano nel nodo React Flow (letti da EntityNode).
 * L'index signature è richiesta da React Flow v12 (data extends Record<string, unknown>).
 */
export interface EntityNodeData {
  name: string;
  type: string;
  community: number | null;
  description: string | null;
  [key: string]: unknown;
}

// Singleton ELK: una sola istanza per sessione (wasm pesante da caricare).
const elk = new ELK();

// Dimensioni fisse per tutti i nodi: ELK le usa per calcolare lo spazio minimo.
const NODE_WIDTH = 184;
const NODE_HEIGHT = 52;

// Layout "layered" (Sugiyama): gestisce cicli, dispone i nodi da sinistra a destra.
const LAYOUT_OPTIONS: Record<string, string> = {
  "elk.algorithm": "layered",
  "elk.direction": "RIGHT",
  "elk.layered.spacing.nodeNodeBetweenLayers": "90",
  "elk.spacing.nodeNode": "55",
};

/**
 * Calcola le posizioni dei nodi con ELK e produce nodi/archi pronti per React Flow.
 * Async: il layout non blocca il render iniziale (il viewer mostra un loader
 * finché la Promise non si risolve).
 */
export async function layoutGraph(graph: GraphRead): Promise<{ nodes: Node[]; edges: Edge[] }> {
  const elkGraph = {
    id: "root",
    layoutOptions: LAYOUT_OPTIONS,
    children: graph.nodes.map((node) => ({ id: node.id, width: NODE_WIDTH, height: NODE_HEIGHT })),
    edges: graph.edges.map((edge, index) => ({
      id: `edge-${index}`,
      sources: [edge.source],
      targets: [edge.target],
    })),
  };

  const layout = await elk.layout(elkGraph);
  // Map ID→posizione per O(1) lookup nella costruzione dei nodi React Flow.
  const positions = new Map((layout.children ?? []).map((child) => [child.id, child]));

  const nodes: Node[] = graph.nodes.map((node) => {
    const position = positions.get(node.id);
    const data: EntityNodeData = {
      name: node.name,
      type: node.type,
      community: node.community,
      description: node.description,
    };
    return {
      id: node.id,
      type: "entity", // custom node type registrato in nodeTypes (GraphViewer)
      position: { x: position?.x ?? 0, y: position?.y ?? 0 },
      data,
    };
  });

  const edges: Edge[] = graph.edges.map((edge, index) => ({
    id: `edge-${index}`,
    source: edge.source,
    target: edge.target,
    // `label` mostra il tipo di relazione sull'arco (es. "LAVORA_IN").
    label: edge.type,
  }));

  return { nodes, edges };
}
