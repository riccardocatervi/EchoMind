import { useQuery } from "@tanstack/react-query";

import { getSummary } from "@/api/summary";
import { queryKeys } from "@/hooks/queryKeys";
import type { UUID } from "@/types/api";

/**
 * Riassunto di un documento. Con `poll: true` ritenta ogni 3s finche' non c'e'
 * un risultato (il summary risponde 404 mentre l'estrazione e' in corso), poi
 * si ferma. Senza `poll`, una singola fetch.
 */
export function useSummary(documentId: UUID | undefined, options: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.summary(documentId ?? ""),
    queryFn: () => getSummary(documentId as UUID),
    enabled: Boolean(documentId),
    refetchInterval: (query) => (options.poll && query.state.data === undefined ? 3000 : false),
  });
}
