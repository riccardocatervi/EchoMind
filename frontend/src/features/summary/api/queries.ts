/**
 * Hook per il summary multilivello del documento.
 *
 * `enabled`: abilitare solo quando `doc.status === 'completed'`.
 *   Il summary richiede M5 completo: graph extracted + summary generato +
 *   embeddings salvati su Postgres. Prima di "completed" il summary non esiste.
 *
 * Nessun polling: il summary è immutabile dopo la creazione. Viene aggiornato
 * solo alla ri-estrazione manuale → in quel caso DocumentDetailPage invalida
 * la cache con `invalidateQueries({ queryKey: summaryKeys.detail(documentId) })`.
 */
import { useQuery } from "@tanstack/react-query";

import { summaryKeys } from "@/features/summary/api/keys";
import { getSummary } from "@/features/summary/api/requests";

/**
 * Summary multilivello di un documento.
 * Abilitare solo quando document.status === 'completed'.
 */
export function useSummary(documentId: string | undefined, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: summaryKeys.detail(documentId ?? ""),
    queryFn: () => getSummary(documentId as string),
    enabled: Boolean(documentId) && (options.enabled ?? true),
  });
}
