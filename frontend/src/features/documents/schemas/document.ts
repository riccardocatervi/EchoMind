import { z } from "zod";

import { isoDateTimeSchema, uuidSchema } from "@/shared/schemas/common";

export const documentStatusSchema = z.enum(["pending", "uploaded", "failed"]);
export type DocumentStatus = z.infer<typeof documentStatusSchema>;

export const documentReadSchema = z.object({
  id: uuidSchema,
  owner_id: uuidSchema,
  filename: z.string(),
  mime_type: z.string(),
  size_bytes: z.number(),
  status: documentStatusSchema,
  failure_reason: z.string().nullable(),
  created_at: isoDateTimeSchema,
  updated_at: isoDateTimeSchema,
});
export type DocumentRead = z.infer<typeof documentReadSchema>;

export const documentInitUploadResponseSchema = z.object({
  document_id: uuidSchema,
  upload_url: z.string(),
  expires_at: isoDateTimeSchema,
});
export type DocumentInitUploadResponse = z.infer<typeof documentInitUploadResponseSchema>;

/** Payload in uscita (lo costruiamo noi): basta l'interfaccia, niente validazione runtime. */
export interface DocumentInitUpload {
  filename: string;
  mime_type: string;
  size_bytes: number;
}

/** Whitelist MIME accettati (mirror di schemas/document.ALLOWED_MIME_TYPES). */
export const ALLOWED_MIME_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document", // DOCX
  "text/plain",
  "audio/mpeg", // MP3
  "audio/wav",
  "audio/x-wav",
  "audio/mp4", // M4A
  "audio/x-m4a",
] as const;
export type AllowedMimeType = (typeof ALLOWED_MIME_TYPES)[number];

/** Limite dimensione upload (mirror del default backend). */
export const MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024;
