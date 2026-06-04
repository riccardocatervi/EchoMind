import { apiFetch } from "@/lib/apiClient";
import type { GraphRead, UUID } from "@/types/api";

/** 404 finche' il grafo non e' pronto/vuoto o non e' tuo; 503 se Neo4j e' giu'. */
export function getGraph(documentId: UUID): Promise<GraphRead> {
  return apiFetch<GraphRead>(`/documents/${documentId}/graph`);
}
