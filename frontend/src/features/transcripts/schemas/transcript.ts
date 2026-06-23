/**
 * Schema Zod per il transcript — mirror di backend/db/models/transcript.py.
 *
 * `source_type`:
 *   "document" = estratto dal testo nativo (PDF/DOCX/TXT via parser).
 *   "audio"    = trascritto da Whisper (MP3/WAV/M4A → testo).
 *   Usato dal TranscriptCard per mostrare l'icona appropriata (testo vs audio).
 *
 * `content`:
 *   Il testo pieno del transcript. Può essere lungo (libro, audio di ore).
 *   TranscriptCard lo mostra con un'area scrollabile con max-height.
 *
 * `language`:
 *   Codice ISO (es. "it", "en") rilevato durante la trascrizione.
 *   Null per documenti testo dove la lingua non viene rilevata automaticamente.
 *
 * `char_count`:
 *   Precomputato dal backend. Mostrato nella card senza ricalcolare `content.length`.
 *
 * `meta`:
 *   JSONB generico: per i file audio contiene durata, frequenza di campionamento,
 *   ecc. restituiti da Whisper. Per i documenti testo è tipicamente vuoto `{}`.
 */
import { z } from "zod";

import { isoDateTimeSchema, uuidSchema } from "@/shared/schemas/common";

export const sourceTypeSchema = z.enum(["document", "audio"]);
export type SourceType = z.infer<typeof sourceTypeSchema>;

export const transcriptReadSchema = z.object({
  id: uuidSchema,
  document_id: uuidSchema,
  // `owner_id` denormalizzato nel DB per RLS senza JOIN (vedi backend/db/models/transcript.py).
  owner_id: uuidSchema,
  source_type: sourceTypeSchema,
  content: z.string(),
  language: z.string().nullable(),
  char_count: z.number(),
  meta: z.record(z.string(), z.unknown()),
  created_at: isoDateTimeSchema,
  updated_at: isoDateTimeSchema,
});
export type TranscriptRead = z.infer<typeof transcriptReadSchema>;
