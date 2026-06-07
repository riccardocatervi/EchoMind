import { useQuery } from "@tanstack/react-query";

import { transcriptKeys } from "@/features/transcripts/api/keys";
import { getTranscript } from "@/features/transcripts/api/requests";

/** Con `poll: true` ritenta ogni 3s finche' non c'e' un risultato, poi si ferma. */
export function useTranscript(documentId: string | undefined, options: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: transcriptKeys.detail(documentId ?? ""),
    queryFn: () => getTranscript(documentId as string),
    enabled: Boolean(documentId),
    refetchInterval: (query) => (options.poll && query.state.data === undefined ? 3000 : false),
  });
}
