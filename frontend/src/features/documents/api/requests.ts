import { z } from "zod";

import { api } from "@/shared/api/axios";
import {
  documentInitUploadResponseSchema,
  documentReadSchema,
  type DocumentInitUpload,
  type DocumentInitUploadResponse,
  type DocumentRead,
} from "@/features/documents/schemas/document";
import {
  taskEnqueuedResponseSchema,
  type TaskEnqueuedResponse,
} from "@/features/tasks/schemas/task";

export async function listDocuments(
  params: { limit?: number; offset?: number } = {},
): Promise<DocumentRead[]> {
  const { data } = await api.get("/documents", { params });
  return z.array(documentReadSchema).parse(data);
}

export async function getDocument(documentId: string): Promise<DocumentRead> {
  const { data } = await api.get(`/documents/${documentId}`);
  return documentReadSchema.parse(data);
}

export async function initUpload(payload: DocumentInitUpload): Promise<DocumentInitUploadResponse> {
  const { data } = await api.post("/documents", payload);
  return documentInitUploadResponseSchema.parse(data);
}

export async function confirmUpload(documentId: string): Promise<DocumentRead> {
  const { data } = await api.post(`/documents/${documentId}/confirm`);
  return documentReadSchema.parse(data);
}

export async function deleteDocument(documentId: string): Promise<void> {
  await api.delete(`/documents/${documentId}`);
}

export async function triggerExtraction(documentId: string): Promise<TaskEnqueuedResponse> {
  const { data } = await api.post(`/documents/${documentId}/extract`);
  return taskEnqueuedResponseSchema.parse(data);
}
