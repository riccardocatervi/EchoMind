import ELK from "elkjs/lib/elk.bundled.js";
import type { Edge, Node } from "@xyflow/react";

import type { GraphRead } from "@/features/graph/schemas/graph";

/** Dati che viaggiano nel nodo React Flow (letti da EntityNode).
 *  L'index signature e' richiesta da React Flow v12 (data extends Record<string, unknown>). */
export interface EntityNodeData {
  name: string;
  type: string;
  community: number | null;
  description: string | null;
  [key: string]: unknown;
}

const elk = new ELK();

const NODE_WIDTH = 184;
const NODE_HEIGHT = 52;

// Layout "layered" (gestisce cicli): leggibile per grafi di conoscenza piccoli.
const LAYOUT_OPTIONS: Record<string, string> = {
  "elk.algorithm": "layered",
  "elk.direction": "RIGHT",
  "elk.layered.spacing.nodeNodeBetweenLayers": "90",
  "elk.spacing.nodeNode": "55",
};

/**
 * Calcola le posizioni dei nodi con Elk e produce nodi/archi pronti per React
 * Flow. Async: il layout non blocca il render iniziale (il viewer mostra un
 * loader finche' non e' pronto).
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
      type: "entity",
      position: { x: position?.x ?? 0, y: position?.y ?? 0 },
      data,
    };
  });

  const edges: Edge[] = graph.edges.map((edge, index) => ({
    id: `edge-${index}`,
    source: edge.source,
    target: edge.target,
    label: edge.type,
  }));

  return { nodes, edges };
}
