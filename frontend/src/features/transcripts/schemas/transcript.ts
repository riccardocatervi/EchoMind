import { z } from "zod";

import { isoDateTimeSchema, uuidSchema } from "@/shared/schemas/common";

export const sourceTypeSchema = z.enum(["document", "audio"]);
export type SourceType = z.infer<typeof sourceTypeSchema>;

export const transcriptReadSchema = z.object({
  id: uuidSchema,
  document_id: uuidSchema,
  owner_id: uuidSchema,
  source_type: sourceTypeSchema,
  content: z.string(),
  language: z.string().nullable(),
  char_count: z.number(),
  meta: z.record(z.string(), z.unknown()),
  created_at: isoDateTimeSchema,
  updated_at: isoDateTimeSchema,
});
export type TranscriptRead = z.infer<typeof transcriptReadSchema>;
