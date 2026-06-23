/**
 * Schema Zod per i task Celery — mirror di backend/db/models/task.py.
 *
 * `TaskStatus`:
 *   queued → running → succeeded | failed
 *   I due stati terminali (succeeded/failed) fanno fermare il polling in useTask.
 *
 * `TaskType`:
 *   echo, transcribe, extract. Sono i task effettivamente registrati in Celery.
 *   Nel DB il campo è TEXT (non enum Postgres) per poter aggiungere nuovi tipi
 *   senza migrazioni. Qui lo validiamo come enum Zod solo per i tipi conosciuti.
 *
 * `taskReadSchema`:
 *   `payload`: JSONB non tipizzato (contiene es. `{ document_id: "<uuid>" }`).
 *   `result`:  JSONB nullable (null finché il task non è terminato).
 *   `error`:   stringa del traceback Celery (null se non fallito).
 *   `retries`: contatore aggiornato dal worker dopo ogni tentativo.
 *
 * `TaskEnqueuedResponse`:
 *   Risposta ai 202 Accepted degli endpoint di trigger (POST /documents/:id/extract).
 *   Contiene il `task_id` per pollare lo stato con useTask.
 */
import { z } from "zod";

import { isoDateTimeSchema, uuidSchema } from "@/shared/schemas/common";

export const taskStatusSchema = z.enum(["queued", "running", "succeeded", "failed"]);
export type TaskStatus = z.infer<typeof taskStatusSchema>;

export const taskTypeSchema = z.enum(["echo", "transcribe", "extract"]);
export type TaskType = z.infer<typeof taskTypeSchema>;

export const taskReadSchema = z.object({
  id: uuidSchema,
  owner_id: uuidSchema,
  // TEXT nel DB (non enum): permette nuovi tipi senza migrazioni.
  task_type: z.string(),
  status: taskStatusSchema,
  // JSONB: payload specifico del tipo di task (es. { document_id }).
  payload: z.record(z.string(), z.unknown()),
  // Null finché il task non è terminato; JSONB con l'outcome finale altrimenti.
  result: z.record(z.string(), z.unknown()).nullable(),
  error: z.string().nullable(),
  retries: z.number(),
  started_at: isoDateTimeSchema.nullable(),
  finished_at: isoDateTimeSchema.nullable(),
  created_at: isoDateTimeSchema,
  updated_at: isoDateTimeSchema,
});
export type TaskRead = z.infer<typeof taskReadSchema>;

/** Risposta 202 degli endpoint di trigger: task_id per il polling. */
export const taskEnqueuedResponseSchema = z.object({
  task_id: uuidSchema,
  status: taskStatusSchema,
});
export type TaskEnqueuedResponse = z.infer<typeof taskEnqueuedResponseSchema>;
