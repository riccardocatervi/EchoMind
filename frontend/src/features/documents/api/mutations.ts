/**
 * Mutation hooks per i documenti (TanStack Query).
 *
 * I `useMutation` gestiscono operazioni che modificano lo stato del server:
 * upload, cancellazione, trigger estrazione. A differenza di `useQuery` (lettura),
 * le mutation non si eseguono automaticamente al mount → vanno chiamate
 * esplicitamente (es. `uploadMutation.mutate(args)` su click del pulsante).
 *
 * Perché invalidare la cache su successo (`invalidateQueries`):
 *   Dopo un'operazione (es. delete), la lista documenti in cache è "stale".
 *   `invalidateQueries({ queryKey: documentKeys.all })` marca TUTTE le query
 *   con quella chiave come invalide → TanStack Query le ri-fetcha in background
 *   al prossimo accesso. Senza invalidazione, l'utente vedrebbe ancora il documento
 *   eliminato fino allo scadere del `staleTime`.
 *   `void` prima della chiamata: `invalidateQueries` ritorna una Promise ma non
 *   c'è motivo di aspettarla nel callback `onSuccess` (è un refetch non critico).
 *
 * Flusso `useUploadDocument`:
 *   1. `initUpload`    → backend crea riga `documents` (status=pending) + presigned URL B2
 *   2. `uploadToB2`    → client fa PUT DIRETTAMENTE su B2 (zero banda backend)
 *                        con progress callback per la progress bar nell'UI
 *   3. `confirmUpload` → backend fa HEAD object + magic-bytes validation + status=uploaded
 *
 *   Questo è il pattern "client-side direct upload" (presigned URL):
 *   - Il file NON transita per il nostro backend → risparmia banda e CPU server.
 *   - B2 verifica Content-Length (vincolo del presigned URL) → un client malevolo
 *     non può caricare file più grandi del dichiarato.
 *   - La mutazione è atomica dal punto di vista dell'UI: o tutto riesce (il documento
 *     appare come "uploaded") o tutto fallisce con un messaggio d'errore.
 *
 * Perché `transcriber_factory` invece del transcriber diretto (backend):
 *   Vedi worker/tasks/transcribe.py: il transcriber Whisper viene costruito SOLO per
 *   file audio, per non richiedere OPENAI_API_KEY su documenti PDF/DOCX/TXT.
 *   Lato frontend: `useUploadDocument` non sa questo dettaglio → chiama semplicemente
 *   `confirmUpload` e aspetta lo status update (polling su PipelineStatus).
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { documentKeys } from "@/features/documents/api/keys";
import {
  confirmUpload,
  deleteDocument,
  initUpload,
  triggerExtraction,
} from "@/features/documents/api/requests";
import { uploadToB2 } from "@/features/documents/lib/uploadToB2";
import type { DocumentRead } from "@/features/documents/schemas/document";

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => deleteDocument(documentId),
    onSuccess: () => {
      // Invalida la lista documenti: il documento eliminato scompare al prossimo refetch.
      void queryClient.invalidateQueries({ queryKey: documentKeys.all });
    },
  });
}

interface UploadArgs {
  file: File;
  // Callback opzionale per aggiornare la progress bar nell'UploadDialog
  onProgress?: (percent: number) => void;
}

/**
 * Orchestra il flusso completo di upload in 3 step:
 *   init (presigned URL) → PUT su B2 (con progress) → confirm (validazione MIME).
 * Alla fine invalida la lista documenti per mostrare il nuovo file.
 */
export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation<DocumentRead, Error, UploadArgs>({
    mutationFn: async ({ file, onProgress }) => {
      // Step 1: il backend crea la riga `documents` (status=pending) e genera
      // un presigned URL PUT valido per `upload_presign_ttl_seconds` secondi.
      const init = await initUpload({
        filename: file.name,
        mime_type: file.type,
        size_bytes: file.size,
      });
      // Step 2: il client carica il file DIRETTAMENTE su B2 (zero banda backend).
      // `onProgress` aggiorna la progress bar (0→100) durante l'upload.
      await uploadToB2(init.upload_url, file, file.type, onProgress);
      // Step 3: il backend verifica l'upload (HEAD + magic bytes) e imposta
      // status=uploaded. Questa riga è quella che ritorna la mutation.
      return confirmUpload(init.document_id);
    },
    onSuccess: () => {
      // Invalida la lista per mostrare il nuovo documento appena caricato.
      void queryClient.invalidateQueries({ queryKey: documentKeys.all });
    },
  });
}

/** Riavvia l'estrazione del grafo. Ritorna il task accodato (pollabile). */
export function useTriggerExtraction() {
  return useMutation({
    // Nessun `onSuccess` con invalidation: il documento è già aggiornato in cache
    // e PipelineStatus fa polling sul task per mostrare l'avanzamento.
    mutationFn: (documentId: string) => triggerExtraction(documentId),
  });
}
