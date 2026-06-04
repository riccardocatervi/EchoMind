import { useQuery } from "@tanstack/react-query";

import { getTranscript } from "@/api/transcript";
import { queryKeys } from "@/hooks/queryKeys";
import type { UUID } from "@/types/api";

/**
 * Transcript di un documento. Con `poll: true` ritenta ogni 3s finche' non c'e'
 * un risultato (404 durante la trascrizione), poi si ferma.
 */
export function useTranscript(documentId: UUID | undefined, options: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.transcript(documentId ?? ""),
    queryFn: () => getTranscript(documentId as UUID),
    enabled: Boolean(documentId),
    refetchInterval: (query) => (options.poll && query.state.data === undefined ? 3000 : false),
  });
}
