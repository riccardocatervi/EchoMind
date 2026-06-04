import { apiFetch } from "@/lib/apiClient";
import type { SummaryRead, UUID } from "@/types/api";

/** 404 finche' l'estrazione non e' completata (o se il documento non e' tuo). */
export function getSummary(documentId: UUID): Promise<SummaryRead> {
  return apiFetch<SummaryRead>(`/documents/${documentId}/summary`);
}
