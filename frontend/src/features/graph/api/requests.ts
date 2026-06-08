import { api } from "@/shared/api/axios";
import { graphReadSchema, type GraphRead } from "@/features/graph/schemas/graph";
import { askResponseSchema, type AskResponse } from "@/features/graph/schemas/rag";

/** 404 finche' il grafo non e' pronto/vuoto o non e' tuo; 503 se Neo4j e' giu'. */
export async function getGraph(documentId: string): Promise<GraphRead> {
  const { data } = await api.get(`/documents/${documentId}/graph`);
  return graphReadSchema.parse(data);
}

/**
 * Q&A GraphRAG sul documento: genera una risposta in linguaggio naturale
 * basata sul knowledge graph, con citazioni delle entita' usate come fonte.
 * La lingua segue l'header Accept-Language (gia' impostato dall'interceptor).
 *
 * 404 se il documento non e' pronto/non e' tuo; 503 se il backend RAG (Gemini)
 * non e' configurato; 422 se la domanda non e' valida.
 */
export async function askDocument(documentId: string, question: string): Promise<AskResponse> {
  const { data } = await api.post(`/documents/${documentId}/ask`, { question });
  return askResponseSchema.parse(data);
}
