import { useQuery } from "@tanstack/react-query";

import { documentKeys } from "@/features/documents/api/keys";
import { getDocument, listDocuments } from "@/features/documents/api/requests";

export function useDocuments(params: { limit?: number; offset?: number } = {}) {
  return useQuery({
    queryKey: documentKeys.list(params),
    queryFn: () => listDocuments(params),
  });
}

export function useDocument(documentId: string | undefined) {
  return useQuery({
    queryKey: documentKeys.detail(documentId ?? ""),
    queryFn: () => getDocument(documentId as string),
    enabled: Boolean(documentId),
    refetchInterval:(query) =>{
      
    }
  });
}
