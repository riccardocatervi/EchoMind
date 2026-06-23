/**
 * Schema Zod per la GraphRAG (Q&A per-documento).
 * Mirror di `AskResponse` / `CitationRead` in backend/rag/gemini.py.
 *
 * `Citation`:
 *   Entità del grafo usata come fonte per la risposta generata da Gemini.
 *   `entity_id` è l'UUID dell'entità in Neo4j (usato per evidenziare il nodo
 *   nel GraphViewer quando l'utente legge la risposta RAG).
 *
 * `AskResponse`:
 *   `answer`: testo in linguaggio naturale generato da Gemini con `response_schema`
 *             strutturato (vedi backend/rag/gemini.py: `GeminiRagAnswerer`).
 *   `citations`: lista di entità citate, con `.default([])` per robustezza
 *               (se il backend non le include, non si rompe la validazione Zod).
 *
 * La lingua della risposta dipende dall'header Accept-Language della richiesta
 * (impostato dall'interceptor axios con `i18n.language`).
 */
import { z } from "zod";

/** Entità del grafo citata come fonte nella risposta. */
export const citationSchema = z.object({
  entity_id: z.string(),
  name: z.string(),
  type: z.string(),
});
export type Citation = z.infer<typeof citationSchema>;

/** Risposta dell'endpoint POST /documents/{id}/ask (GraphRAG). */
export const askResponseSchema = z.object({
  answer: z.string(),
  // `.default([])` rende il campo opzionale in entrata: Zod usa [] se mancante.
  citations: z.array(citationSchema).default([]),
});
export type AskResponse = z.infer<typeof askResponseSchema>;
