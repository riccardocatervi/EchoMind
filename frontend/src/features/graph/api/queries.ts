import { useQuery } from "@tanstack/react-query";

import { graphKeys } from "@/features/graph/api/keys";
import { getGraph } from "@/features/graph/api/requests";

/**
 * Grafo di conoscenza di un documento.
 *
 * `enabled` (default true) controlla se la query viene eseguita.
 * Abilitare quando document.status e' 'extracted' o 'completed':
 * il grafo e' in Neo4j dall'istante in cui lo stato diventa 'extracted'.
 */
export function useGraph(documentId: string | undefined, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: graphKeys.detail(documentId ?? ""),
    queryFn: () => getGraph(documentId as string),
    enabled: Boolean(documentId) && (options.enabled ?? true),
  });
}
