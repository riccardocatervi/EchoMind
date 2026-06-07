import { api } from "@/shared/api/axios";
import { graphReadSchema, type GraphRead } from "@/features/graph/schemas/graph";

/** 404 finche' il grafo non e' pronto/vuoto o non e' tuo; 503 se Neo4j e' giu'. */
export async function getGraph(documentId: string): Promise<GraphRead> {
  const { data } = await api.get(`/documents/${documentId}/graph`);
  return graphReadSchema.parse(data);
}
