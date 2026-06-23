/**
 * Schema Zod per i documenti — mirror dei modelli backend.
 *
 * Perché Zod (e non TypeScript puro):
 *   TypeScript è compilato via erase: a runtime non esiste. Zod è una libreria
 *   di validazione runtime: garantisce che i dati arrivati dall'API corrispondano
 *   alla forma attesa PRIMA di entrare nello store React o TanStack Query.
 *   Se il backend aggiunge un campo o cambia un tipo, Zod lancia con un messaggio
 *   esplicito ("Expected string, received number at path 'status'").
 *
 * Perché `z.infer<typeof schema>` invece di interfacce TypeScript manuali:
 *   Derivare il tipo dallo schema Zod evita la doppia manutenzione: un'interfaccia
 *   TypeScript separata e lo schema Zod che devono restare sincronizzati a mano.
 *
 * `DocumentStatus`:
 *   Mirror di `DocumentStatus(StrEnum)` in backend/db/models/document.py.
 *   Rappresenta il lifecycle del documento attraverso la pipeline:
 *     pending → uploaded → transcribed → extracted → completed (terminale OK)
 *                                                  → failed    (terminale KO)
 *   I componenti UI (PipelineStatus, StatusBadge) usano questo tipo.
 *
 * `ALLOWED_MIME_TYPES`:
 *   Mirror di `ALLOWED_MIME_TYPES` in backend/services/document.py.
 *   Validazione client-side nel FileDropzone per dare feedback immediato
 *   senza una round-trip al backend. La validazione server-side resta la
 *   source of truth (magic bytes check in confirm_upload).
 *
 * `MAX_UPLOAD_SIZE_BYTES`:
 *   50 MB. Mirror del limite backend (upload_max_size_mb = 50 in settings).
 *   Stessa validazione client-side nel FileDropzone.
 */
import { z } from "zod";

import { isoDateTimeSchema, uuidSchema } from "@/shared/schemas/common";

export const documentStatusSchema = z.enum([
  "pending",
  "uploaded",
  "transcribed", // M4 completato: transcript disponibile
  "extracted", // M5 parziale: grafo in Neo4j disponibile
  "completed", // M5 completo: summary + embeddings pronti (stato terminale positivo)
  "failed", // terminale negativo
]);
export type DocumentStatus = z.infer<typeof documentStatusSchema>;

/** Shape completa di un documento come restituita dal backend (GET /documents). */
export const documentReadSchema = z.object({
  id: uuidSchema,
  owner_id: uuidSchema,
  filename: z.string(),
  mime_type: z.string(),
  size_bytes: z.number(),
  status: documentStatusSchema,
  // null finché non fallisce; stringa con dettaglio se status="failed".
  failure_reason: z.string().nullable(),
  created_at: isoDateTimeSchema,
  updated_at: isoDateTimeSchema,
});
export type DocumentRead = z.infer<typeof documentReadSchema>;

/** Risposta di POST /documents: presigned URL da usare per il PUT diretto su B2. */
export const documentInitUploadResponseSchema = z.object({
  document_id: uuidSchema,
  upload_url: z.string(),
  expires_at: isoDateTimeSchema,
});
export type DocumentInitUploadResponse = z.infer<typeof documentInitUploadResponseSchema>;

/**
 * Payload in uscita per POST /documents.
 * Niente schema Zod: lo costruiamo noi, quindi TypeScript è sufficiente
 * (la validazione runtime ha senso solo ai confini in INGRESSO, non in uscita).
 */
export interface DocumentInitUpload {
  filename: string;
  mime_type: string;
  size_bytes: number;
}

/**
 * Whitelist MIME accettati — mirror di ALLOWED_MIME_TYPES nel backend.
 * Usata per la validazione client-side nel FileDropzone e per l'attributo
 * `accept` dell'<input type="file"> (suggerisce i file compatibili al browser).
 */
export const ALLOWED_MIME_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document", // DOCX
  "text/plain",
  "audio/mpeg", // MP3
  "audio/wav",
  "audio/x-wav",
  "audio/mp4", // M4A
  "audio/x-m4a",
] as const;
export type AllowedMimeType = (typeof ALLOWED_MIME_TYPES)[number];

/** Limite dimensione upload (50 MB) — mirror del backend. Pre-valida nel Dropzone. */
export const MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024;
