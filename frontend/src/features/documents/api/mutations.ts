import { useMutation, useQueryClient } from "@tanstack/react-query";

import { documentKeys } from "@/features/documents/api/keys";
import { confirmUpload, deleteDocument, initUpload } from "@/features/documents/api/requests";
import { uploadToB2 } from "@/features/documents/lib/uploadToB2";
import type { DocumentRead } from "@/features/documents/schemas/document";

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => deleteDocument(documentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentKeys.all });
    },
  });
}

interface UploadArgs {
  file: File;
  onProgress?: (percent: number) => void;
}

/** Orchestra init -> PUT diretto a B2 (con progresso) -> confirm; invalida la lista. */
export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation<DocumentRead, Error, UploadArgs>({
    mutationFn: async ({ file, onProgress }) => {
      const init = await initUpload({
        filename: file.name,
        mime_type: file.type,
        size_bytes: file.size,
      });
      await uploadToB2(init.upload_url, file, file.type, onProgress);
      return confirmUpload(init.document_id);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentKeys.all });
    },
  });
}
