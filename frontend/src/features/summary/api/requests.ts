/**
 * Funzione HTTP per il summary multilivello.
 *
 * `getSummary`:
 *   GET /documents/:id/summary → ritorna `SummaryRead`.
 *   Risponde 404 se il summary non è ancora pronto (documento non in stato
 *   "completed") o se il documento non appartiene all'utente.
 *   Il summary è disponibile solo dopo M5 completo (summary + embeddings pronti).
 *
 * Perché `/documents/:id/summary` e non `/summaries/:id`:
 *   Stesso ragionamento del transcript: il summary è una risorsa figlio del
 *   documento. L'utente naviga sempre per documentId, non per summaryId interno.
 */
import { api } from "@/shared/api/axios";
import { summaryReadSchema, type SummaryRead } from "@/features/summary/schemas/summary";

/** 404 finché l'estrazione non è completata (status != 'completed') o non è tua. */
export async function getSummary(documentId: string): Promise<SummaryRead> {
  const { data } = await api.get(`/documents/${documentId}/summary`);
  return summaryReadSchema.parse(data);
}
