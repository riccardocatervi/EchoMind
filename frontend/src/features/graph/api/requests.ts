/**
 * Funzioni HTTP per il grafo e il Q&A RAG.
 *
 * `getGraph`:
 *   GET /documents/:id/graph → ritorna nodi, archi, conteggi (GraphRead).
 *   Risponde 404 se il grafo non è ancora pronto o non è del tuo utente
 *   (by design: il backend non distingue "non estratto" da "non tuo"
 *   per non leakare informazioni sulla presenza del documento).
 *   Risponde 503 se Neo4j non è configurato (produzione senza GRAPH_URL).
 *
 * `askDocument`:
 *   POST /documents/:id/ask → GraphRAG: embed question → pgvector top-K →
 *   Neo4j neighborhood expansion → Gemini structured output → RagAnswer.
 *   La lingua della risposta segue Accept-Language (già nell'interceptor axios).
 *   Risponde 404 se il documento non è pronto/non è tuo; 503 se Gemini o Neo4j
 *   non sono configurati; 422 se la domanda manca.
 */
import { api } from "@/shared/api/axios";
import { graphReadSchema, type GraphRead } from "@/features/graph/schemas/graph";
import { askResponseSchema, type AskResponse } from "@/features/graph/schemas/rag";

/** 404 finché il grafo non è pronto/vuoto o non è tuo; 503 se Neo4j è giù. */
export async function getGraph(documentId: string): Promise<GraphRead> {
  const { data } = await api.get(`/documents/${documentId}/graph`);
  return graphReadSchema.parse(data);
}

/**
 * Q&A GraphRAG sul documento: genera una risposta in linguaggio naturale
 * basata sul knowledge graph, con citazioni delle entità usate come fonte.
 * La lingua segue l'header Accept-Language (già impostato dall'interceptor).
 */
export async function askDocument(documentId: string, question: string): Promise<AskResponse> {
  const { data } = await api.post(`/documents/${documentId}/ask`, { question });
  return askResponseSchema.parse(data);
}
