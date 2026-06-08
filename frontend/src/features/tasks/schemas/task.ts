import { z } from "zod";

import { isoDateTimeSchema, uuidSchema } from "@/shared/schemas/common";

export const taskStatusSchema = z.enum(["queued", "running", "succeeded", "failed"]);
export type TaskStatus = z.infer<typeof taskStatusSchema>;

export const taskTypeSchema = z.enum(["echo", "transcribe", "extract"]);
export type TaskType = z.infer<typeof taskTypeSchema>;

export const taskReadSchema = z.object({
  id: uuidSchema,
  owner_id: uuidSchema,
  task_type: z.string(),
  status: taskStatusSchema,
  payload: z.record(z.string(), z.unknown()),
  result: z.record(z.string(), z.unknown()).nullable(),
  error: z.string().nullable(),
  retries: z.number(),
  started_at: isoDateTimeSchema.nullable(),
  finished_at: isoDateTimeSchema.nullable(),
  created_at: isoDateTimeSchema,
  updated_at: isoDateTimeSchema,
});
export type TaskRead = z.infer<typeof taskReadSchema>;

export const taskEnqueuedResponseSchema = z.object({
  task_id: uuidSchema,
  status: taskStatusSchema,
});
export type TaskEnqueuedResponse = z.infer<typeof taskEnqueuedResponseSchema>;
