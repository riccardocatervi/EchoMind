/**
 * Hook per il transcript del documento.
 *
 * `enabled` (default true) è controllato da DocumentDetailPage:
 *   viene abilitato solo quando `doc.status` è "transcribed", "extracted"
 *   o "completed". Prima di M4 (transcribe task completato), il transcript
 *   non esiste in DB → chiamare l'endpoint tornerebbe 404.
 *
 * Nessun polling: il transcript non cambia dopo la creazione.
 * L'unico caso di aggiornamento è una ri-trascrizione (non supportata in M4):
 *   in quel caso si invaliderebbe la cache tramite `invalidateQueries`.
 */
import { useQuery } from "@tanstack/react-query";

import { transcriptKeys } from "@/features/transcripts/api/keys";
import { getTranscript } from "@/features/transcripts/api/requests";

/**
 * Transcript di un documento.
 * `enabled`: abilitare solo quando document.status è "transcribed" o successivo.
 */
export function useTranscript(documentId: string | undefined, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: transcriptKeys.detail(documentId ?? ""),
    queryFn: () => getTranscript(documentId as string),
    enabled: Boolean(documentId) && (options.enabled ?? true),
  });
}
