import { useQuery } from "@tanstack/react-query";

import { transcriptKeys } from "@/features/transcripts/api/keys";
import { getTranscript } from "@/features/transcripts/api/requests";

/**
 * Transcript di un documento.
 *
 * `enabled` (default true) controlla se la query viene eseguita.
 * Usato da DocumentDetailPage per abilitare il fetch solo quando il
 * documento e' nello stato 'transcribed' o successivo (document.status
 * e' la sorgente di verita', non il polling su questo endpoint).
 */
export function useTranscript(documentId: string | undefined, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: transcriptKeys.detail(documentId ?? ""),
    queryFn: () => getTranscript(documentId as string),
    enabled: Boolean(documentId) && (options.enabled ?? true),
  });
}
