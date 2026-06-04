import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { deleteDocument, getDocument, listDocuments } from "@/api/documents";
import { queryKeys } from "@/hooks/queryKeys";
import type { UUID } from "@/types/api";

export function useDocuments(params: { limit?: number; offset?: number } = {}) {
  return useQuery({
    queryKey: [...queryKeys.documents.all, params],
    queryFn: () => listDocuments(params),
  });
}

export function useDocument(documentId: UUID | undefined) {
  return useQuery({
    queryKey: queryKeys.documents.detail(documentId ?? ""),
    queryFn: () => getDocument(documentId as UUID),
    enabled: Boolean(documentId),
  });
}

/** Cancella un documento e invalida la lista per riflettere subito la rimozione. */
export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: UUID) => deleteDocument(documentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.documents.all });
    },
  });
}
