/**
 * Funzione HTTP per il transcript.
 *
 * `getTranscript`:
 *   GET /documents/:id/transcript → ritorna `TranscriptRead`.
 *   Risponde 404 se il transcript non è ancora pronto (documento in stato
 *   pre-M4) o se il documento non appartiene all'utente (by design: il backend
 *   non distingue i due casi per non leakare informazioni sull'esistenza).
 *
 * Perché `documentId` e non `transcriptId`:
 *   Il transcript è 1:1 con il documento. L'utente conosce il `documentId`
 *   (è nell'URL della pagina), non il `transcriptId` interno. L'API espone
 *   `/documents/:id/transcript` anziché `/transcripts/:id` per coerenza
 *   con il resource model: il transcript è una risorsa figlio del documento.
 */
import { api } from "@/shared/api/axios";
import {
  transcriptReadSchema,
  type TranscriptRead,
} from "@/features/transcripts/schemas/transcript";

/** 404 finché la trascrizione non è pronta o il documento non è tuo. */
export async function getTranscript(documentId: string): Promise<TranscriptRead> {
  const { data } = await api.get(`/documents/${documentId}/transcript`);
  return transcriptReadSchema.parse(data);
}
