import { useQuery } from "@tanstack/react-query";

import { summaryKeys } from "@/features/summary/api/keys";
import { getSummary } from "@/features/summary/api/requests";

/** Con `poll: true` ritenta ogni 3s finche' il riassunto non c'e', poi si ferma. */
export function useSummary(documentId: string | undefined, options: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: summaryKeys.detail(documentId ?? ""),
    queryFn: () => getSummary(documentId as string),
    enabled: Boolean(documentId),
    refetchInterval: (query) => (options.poll && query.state.data === undefined ? 3000 : false),
  });
}
