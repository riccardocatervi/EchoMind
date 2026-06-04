import { useQuery } from "@tanstack/react-query";

import { graphKeys } from "@/features/graph/api/keys";
import { getGraph } from "@/features/graph/api/requests";

/** Con `poll: true` ritenta ogni 3s finche' il grafo non c'e', poi si ferma. */
export function useGraph(documentId: string | undefined, options: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: graphKeys.detail(documentId ?? ""),
    queryFn: () => getGraph(documentId as string),
    enabled: Boolean(documentId),
    refetchInterval: (query) => (options.poll && query.state.data === undefined ? 3000 : false),
  });
}
