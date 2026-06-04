import { useQuery } from "@tanstack/react-query";

import { getGraph } from "@/api/graph";
import { queryKeys } from "@/hooks/queryKeys";
import type { UUID } from "@/types/api";

/**
 * Grafo di un documento. Con `poll: true` ritenta ogni 3s finche' non c'e' un
 * risultato (404 mentre l'estrazione e' in corso), poi si ferma.
 */
export function useGraph(documentId: UUID | undefined, options: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.graph(documentId ?? ""),
    queryFn: () => getGraph(documentId as UUID),
    enabled: Boolean(documentId),
    refetchInterval: (query) => (options.poll && query.state.data === undefined ? 3000 : false),
  });
}
