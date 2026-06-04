import { useQuery } from "@tanstack/react-query";

import { getDocument, listDocuments } from "@/api/documents";
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
