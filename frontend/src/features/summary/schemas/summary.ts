import { z } from "zod";

import { isoDateTimeSchema, uuidSchema } from "@/shared/schemas/common";

export const summarySectionSchema = z.object({
  title: z.string(),
  content: z.string(),
});
export type SummarySection = z.infer<typeof summarySectionSchema>;

export const summaryReadSchema = z.object({
  id: uuidSchema,
  document_id: uuidSchema,
  owner_id: uuidSchema,
  overview: z.string(),
  sections: z.array(summarySectionSchema),
  meta: z.record(z.string(), z.unknown()),
  created_at: isoDateTimeSchema,
  updated_at: isoDateTimeSchema,
});
export type SummaryRead = z.infer<typeof summaryReadSchema>;
