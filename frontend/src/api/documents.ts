import { apiFetch } from "@/lib/apiClient";
import type {
  DocumentInitUpload,
  DocumentInitUploadResponse,
  DocumentRead,
  TaskEnqueuedResponse,
  UUID,
} from "@/types/api";

/** Lista paginata dei propri documenti (RLS-filtered, recenti prima). */
export function listDocuments(
  params: { limit?: number; offset?: number } = {},
): Promise<DocumentRead[]> {
  return apiFetch<DocumentRead[]>("/documents", {
    query: { limit: params.limit, offset: params.offset },
  });
}

export function getDocument(documentId: UUID): Promise<DocumentRead> {
  return apiFetch<DocumentRead>(`/documents/${documentId}`);
}

/** Step 1 dell'upload: crea il record e ottiene il presigned URL B2. */
export function initUpload(payload: DocumentInitUpload): Promise<DocumentInitUploadResponse> {
  return apiFetch<DocumentInitUploadResponse>("/documents", { method: "POST", body: payload });
}

/** Step 3 dell'upload: il backend valida il MIME via magic bytes. */
export function confirmUpload(documentId: UUID): Promise<DocumentRead> {
  return apiFetch<DocumentRead>(`/documents/${documentId}/confirm`, { method: "POST" });
}

export function deleteDocument(documentId: UUID): Promise<void> {
  return apiFetch<void>(`/documents/${documentId}`, { method: "DELETE" });
}

/** Riavvia l'estrazione del grafo (richiede un transcript pronto). */
export function triggerExtraction(documentId: UUID): Promise<TaskEnqueuedResponse> {
  return apiFetch<TaskEnqueuedResponse>(`/documents/${documentId}/extract`, { method: "POST" });
}
