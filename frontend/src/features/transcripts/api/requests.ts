import { api } from "@/shared/api/axios";
import {
  transcriptReadSchema,
  type TranscriptRead,
} from "@/features/transcripts/schemas/transcript";

/** 404 finche' la trascrizione non e' pronta o non e' tua. */
export async function getTranscript(documentId: string): Promise<TranscriptRead> {
  const { data } = await api.get(`/documents/${documentId}/transcript`);
  return transcriptReadSchema.parse(data);
}
