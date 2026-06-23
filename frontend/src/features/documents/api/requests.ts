/**
 * Funzioni HTTP per i documenti — thin wrapper su `api` (axios).
 *
 * Ogni funzione:
 *   1. Fa la chiamata HTTP con `api` (istanza axios con interceptor auth già configurati).
 *   2. Parsa la risposta con Zod (`documentReadSchema.parse(data)`).
 *
 * Perché parsare con Zod anziché fidarsi del backend:
 *   Il backend può evolvere (campo aggiunto/rinominato) o un bug può restituire
 *   un formato inatteso. Il parse Zod lancia al confine esterno (boundary), non
 *   dentro i componenti React, rendendo l'errore esplicito e tracciabile.
 *   Per i payload in *uscita* (es. `DocumentInitUpload`) non si parsa: siamo noi
 *   a costruirli, quindi TypeScript è sufficiente.
 *
 * Flusso upload:
 *   `initUpload`    → POST /documents      → riceve { document_id, upload_url, expires_at }
 *   ↓ (chiamata XHR diretta su B2 in uploadToB2.ts)
 *   `confirmUpload` → POST /documents/:id/confirm → verifica HEAD + magic bytes → DocumentRead
 *
 * `triggerExtraction`:
 *   POST /documents/:id/extract → ritorna TaskEnqueuedResponse (task_id pollabile).
 *   L'endpoint risponde 202 Accepted: il task è in coda, non ancora eseguito.
 */
import { z } from "zod";

import { api } from "@/shared/api/axios";
import {
  documentInitUploadResponseSchema,
  documentReadSchema,
  type DocumentInitUpload,
  type DocumentInitUploadResponse,
  type DocumentRead,
} from "@/features/documents/schemas/document";
import {
  taskEnqueuedResponseSchema,
  type TaskEnqueuedResponse,
} from "@/features/tasks/schemas/task";

/** Recupera la lista dei documenti dell'utente (ordinata per created_at DESC). */
export async function listDocuments(
  params: { limit?: number; offset?: number } = {},
): Promise<DocumentRead[]> {
  const { data } = await api.get("/documents", { params });
  // `z.array(documentReadSchema)` valida ogni elemento: se il backend invia
  // un campo mancante o di tipo sbagliato, Zod lancia immediatamente.
  return z.array(documentReadSchema).parse(data);
}

/** Recupera il dettaglio di un documento (sorgente di verità del lifecycle). */
export async function getDocument(documentId: string): Promise<DocumentRead> {
  const { data } = await api.get(`/documents/${documentId}`);
  return documentReadSchema.parse(data);
}

/**
 * Crea una nuova riga `documents` (status=pending) e genera il presigned URL B2.
 * Il backend valida il mime_type contro ALLOWED_MIME_TYPES prima di firmare.
 */
export async function initUpload(payload: DocumentInitUpload): Promise<DocumentInitUploadResponse> {
  const { data } = await api.post("/documents", payload);
  return documentInitUploadResponseSchema.parse(data);
}

/**
 * Notifica il backend che l'upload su B2 è avvenuto (status pending → uploaded).
 * Il backend fa HEAD sul bucket B2 e verifica magic bytes (anti-spoofing MIME).
 */
export async function confirmUpload(documentId: string): Promise<DocumentRead> {
  const { data } = await api.post(`/documents/${documentId}/confirm`);
  return documentReadSchema.parse(data);
}

/** Elimina documento, transcript, summary, grafo Neo4j e oggetto B2. */
export async function deleteDocument(documentId: string): Promise<void> {
  await api.delete(`/documents/${documentId}`);
}

/**
 * Accoda il task di estrazione grafo (Celery). Risponde 202 Accepted.
 * Il task_id ritornato è pollabile via /tasks/:id (vedi useTask).
 */
export async function triggerExtraction(documentId: string): Promise<TaskEnqueuedResponse> {
  const { data } = await api.post(`/documents/${documentId}/extract`);
  return taskEnqueuedResponseSchema.parse(data);
}
