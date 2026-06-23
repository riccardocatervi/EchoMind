/**
 * Schema Zod per il profilo utente — mirror di backend/db/models/profile.py.
 *
 * `ProfileRead`:
 *   - `id`: stesso UUID di auth.users.id (PK = FK, relazione 1:1). Non generato
 *     autonomamente: il profilo usa l'ID assegnato da Supabase Auth.
 *   - `display_name`: campo opzionale (può essere null). In M8 è derivato da
 *     user_metadata.first_name + last_name nel backend.
 *   - `preferred_language`: codice ISO (es. "it", "en") usato dalla pipeline
 *     per la lingua degli output (summary, grafo, risposte RAG). NON è la lingua
 *     dell'interfaccia (quella è gestita da i18n con il localStorage).
 *
 * `ProfileUpdate`:
 *   Interfaccia (non schema Zod): payload in USCITA verso il backend.
 *   Niente validazione runtime: lo costruiamo noi, TypeScript è sufficiente.
 *   Campi opzionali con `?`: solo i campi forniti vengono aggiornati (PATCH semantics).
 */
import { z } from "zod";

import { isoDateTimeSchema, uuidSchema } from "@/shared/schemas/common";

export const profileReadSchema = z.object({
  id: uuidSchema,
  display_name: z.string().nullable(),
  // Lingua degli output della pipeline ("it" | "en"). Default "it" (migration 0007).
  preferred_language: z.string(),
  created_at: isoDateTimeSchema,
  updated_at: isoDateTimeSchema,
});
export type ProfileRead = z.infer<typeof profileReadSchema>;

/** Payload PATCH per il profilo: solo i campi forniti vengono aggiornati. */
export interface ProfileUpdate {
  display_name?: string | null;
  preferred_language?: string;
}
