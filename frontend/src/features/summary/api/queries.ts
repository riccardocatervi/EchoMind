import { useQuery } from "@tanstack/react-query";

import { summaryKeys } from "@/features/summary/api/keys";
import { getSummary } from "@/features/summary/api/requests";

/**
 * Summary multilivello di un documento.
 *
 * `enabled` (default true) controlla se la query viene eseguita.
 * Abilitare solo quando document.status === 'completed' per evitare
 * chiamate 404 durante l'elaborazione.
 */
export function useSummary(documentId: string | undefined, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: summaryKeys.detail(documentId ?? ""),
    queryFn: () => getSummary(documentId as string),
    enabled: Boolean(documentId) && (options.enabled ?? true),
  });
}
