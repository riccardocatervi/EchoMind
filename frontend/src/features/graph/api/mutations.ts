import { useMutation } from "@tanstack/react-query";

import { askDocument } from "@/features/graph/api/requests";
import type { AskResponse } from "@/features/graph/schemas/rag";

/**
 * GraphRAG Q&A: pone una domanda sul documento e ritorna risposta + citazioni.
 * Non e' una query cacheable (input dinamico) -> mutation. Nessuna invalidazione:
 * non modifica stato server.
 */
export function useAskDocument(documentId: string) {
  return useMutation<AskResponse, Error, string>({
    mutationFn: (question: string) => askDocument(documentId, question),
  });
}
