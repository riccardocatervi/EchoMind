import { z } from "zod";

/**
 * Schemi della GraphRAG (Q&A per-documento).
 * Rispecchiano `AskResponse`/`CitationRead` del backend (schemas/rag.py).
 */

/** Entita' del grafo citata come fonte nella risposta. */
export const citationSchema = z.object({
  entity_id: z.string(),
  name: z.string(),
  type: z.string(),
});
export type Citation = z.infer<typeof citationSchema>;

/** Risposta dell'endpoint POST /documents/{id}/ask. */
export const askResponseSchema = z.object({
  answer: z.string(),
  citations: z.array(citationSchema).default([]),
});
export type AskResponse = z.infer<typeof askResponseSchema>;
