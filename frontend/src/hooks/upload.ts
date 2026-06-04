import { useMutation, useQueryClient } from "@tanstack/react-query";

import { confirmUpload, initUpload } from "@/api/documents";
import { queryKeys } from "@/hooks/queryKeys";
import { uploadToB2 } from "@/lib/uploadToB2";
import type { DocumentRead } from "@/types/api";

interface UploadArgs {
  file: File;
  onProgress?: (percent: number) => void;
}

/**
 * Orchestra i 3 passi dell'upload in un'unica mutation:
 *   1. initUpload  -> record + presigned URL
 *   2. uploadToB2  -> PUT diretto del file (con progresso)
 *   3. confirmUpload -> il backend valida il MIME via magic bytes
 * Al successo invalida la lista documenti.
 */
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
      void queryClient.invalidateQueries({ queryKey: queryKeys.documents.all });
    },
  });
}
