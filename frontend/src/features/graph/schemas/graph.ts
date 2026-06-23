/**
 * Schema Zod per il grafo di conoscenza — mirror dei modelli backend.
 *
 * `GraphNode`:
 *   Entità estratta da Gemini (persona, organizzazione, concetto, luogo, evento...).
 *   `community`: numero di community Louvain (intero ≥ 0) assegnato dal clustering
 *   lato backend (extraction/community.py). `null` = nodo isolato non in nessuna
 *   community. Usato da `communityColor()` per colorare i nodi nel viewer.
 *
 * `GraphEdge`:
 *   Relazione direzionale tra due entità (source → target).
 *   `type`: etichetta stringa libera (es. "LAVORA_IN", "CITA", "È_FIGLIO_DI").
 *   Non usiamo un enum perché le relazioni sono estratte da LLM e variano per documento.
 *
 * `GraphRead`:
 *   Shape completa restituita da GET /documents/:id/graph.
 *   `node_count`, `relationship_count`, `community_count` sono precomputati dal
 *   backend: evitano di ricalcolare `.length` sul frontend per ogni render.
 */
import { z } from "zod";

import { uuidSchema } from "@/shared/schemas/common";

export const graphNodeSchema = z.object({
  id: uuidSchema,
  name: z.string(),
  type: z.string(),
  description: z.string().nullable(),
  // Indice numerico della community Louvain (null = nodo isolato).
  community: z.number().nullable(),
});
export type GraphNode = z.infer<typeof graphNodeSchema>;

export const graphEdgeSchema = z.object({
  source: uuidSchema,
  target: uuidSchema,
  type: z.string(),
  description: z.string().nullable(),
});
export type GraphEdge = z.infer<typeof graphEdgeSchema>;

export const graphReadSchema = z.object({
  document_id: uuidSchema,
  nodes: z.array(graphNodeSchema),
  edges: z.array(graphEdgeSchema),
  // Conteggi precomputati dal backend (usati per il badge "N nodi" nell'header).
  node_count: z.number(),
  relationship_count: z.number(),
  community_count: z.number(),
});
export type GraphRead = z.infer<typeof graphReadSchema>;
