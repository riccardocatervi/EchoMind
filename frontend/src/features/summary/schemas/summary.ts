/**
 * Schema Zod per il summary multilivello — mirror di backend/db/models/summary.py.
 *
 * Struttura del summary (generata da `GeminiSummarizer` con map-reduce):
 *
 *   `overview`:  paragrafo riassuntivo globale del documento (map-reduce su tutte le
 *               community Louvain). È il primo testo visibile in SummaryView.
 *
 *   `sections`:  lista di sezioni tematiche (una per community/cluster di concetti).
 *               Ogni sezione ha `title` (tema della community) e `content` (testo).
 *               In SummaryView vengono mostrate come Accordion espandibili.
 *
 *   `meta`:     JSONB generico. Contiene `node_count`, `relationship_count`,
 *               `community_count` (precomputati durante l'estrazione). SummaryView
 *               li legge per mostrare le statistiche del grafo accanto al titolo.
 *               Usare JSONB anziché colonne dedicate permette di aggiungere metadati
 *               senza migrazioni (a costo di meno type-safety nel DB).
 */
import { z } from "zod";

import { isoDateTimeSchema, uuidSchema } from "@/shared/schemas/common";

export const summarySectionSchema = z.object({
  title: z.string(),
  content: z.string(),
});
export type SummarySection = z.infer<typeof summarySectionSchema>;

export const summaryReadSchema = z.object({
  id: uuidSchema,
  document_id: uuidSchema,
  owner_id: uuidSchema,
  overview: z.string(),
  // Array di sezioni tematiche (una per community Louvain).
  sections: z.array(summarySectionSchema),
  // Metadati JSONB (node_count, relationship_count, community_count).
  meta: z.record(z.string(), z.unknown()),
  created_at: isoDateTimeSchema,
  updated_at: isoDateTimeSchema,
});
export type SummaryRead = z.infer<typeof summaryReadSchema>;
