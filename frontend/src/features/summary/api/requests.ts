import { api } from "@/shared/api/axios";
import { summaryReadSchema, type SummaryRead } from "@/features/summary/schemas/summary";

/** 404 finche' l'estrazione non e' completata o non e' tua. */
export async function getSummary(documentId: string): Promise<SummaryRead> {
  const { data } = await api.get(`/documents/${documentId}/summary`);
  return summaryReadSchema.parse(data);
}
