/**
 * Query hooks per il grafo di conoscenza e il Q&A RAG.
 *
 * `useGraph`:
 *   Non fa polling: il grafo cambia solo quando viene ri-estratto manualmente.
 *   `enabled` viene impostato a false da DocumentDetailPage finché il documento
 *   non raggiunge lo status "extracted" o "completed" — evita fetch prematuri
 *   che tornerebbero 404 (il grafo non esiste ancora in Neo4j).
 *
 * Perché `enabled: Boolean(documentId) && (options.enabled ?? true)`:
 *   Doppia guardia: `Boolean(documentId)` evita fetch con ID vuoto (stringa "");
 *   `options.enabled` permette al chiamante di disabilitare esplicitamente il
 *   fetch finché le condizioni preliminari non sono soddisfatte.
 *
 * Il Q&A RAG (askDocument) non ha un useQuery dedicato: è una mutation one-shot
 * (POST /ask) gestita direttamente in GraphQaPanel con useState locale.
 */
import { useQuery } from "@tanstack/react-query";

import { graphKeys } from "@/features/graph/api/keys";
import { getGraph } from "@/features/graph/api/requests";

/**
 * Grafo di conoscenza di un documento.
 * Abilitare solo quando document.status è "extracted" o "completed"
 * (il grafo è in Neo4j solo da quel momento in poi).
 */
export function useGraph(documentId: string | undefined, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: graphKeys.detail(documentId ?? ""),
    queryFn: () => getGraph(documentId as string),
    enabled: Boolean(documentId) && (options.enabled ?? true),
  });
}
