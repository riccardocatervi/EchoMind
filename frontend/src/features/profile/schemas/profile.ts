import { z } from "zod";

import { isoDateTimeSchema, uuidSchema } from "@/shared/schemas/common";

export const profileReadSchema = z.object({
  id: uuidSchema,
  display_name: z.string().nullable(),
  preferred_language: z.string(),
  created_at: isoDateTimeSchema,
  updated_at: isoDateTimeSchema,
});
export type ProfileRead = z.infer<typeof profileReadSchema>;

export interface ProfileUpdate {
  display_name?: string | null;
  preferred_language?: string;
}
