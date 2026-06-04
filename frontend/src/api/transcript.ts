import { apiFetch } from "@/lib/apiClient";
import type { TranscriptRead, UUID } from "@/types/api";

/** 404 finche' la trascrizione non e' pronta (in elaborazione/fallita) o non e' tua. */
export function getTranscript(documentId: UUID): Promise<TranscriptRead> {
  return apiFetch<TranscriptRead>(`/documents/${documentId}/transcript`);
}
