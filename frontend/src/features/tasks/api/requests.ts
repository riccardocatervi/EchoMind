/**
 * Funzioni HTTP per i task Celery.
 *
 * `getTask`:
 *   Polling principale usato da `useTask` (refetchInterval 2s). Ogni risposta
 *   include lo `status` attuale: il chiamante decide quando fermare il polling
 *   (quando status è "succeeded" o "failed").
 *
 * `listTasks`:
 *   Non ancora usata nell'UI principale (prevista per una futura dashboard
 *   di monitoraggio jobs). Già implementata per completezza.
 *
 * Entrambe parsano la risposta con Zod: se il backend aggiorna il formato dei
 *   task (nuovo campo, cambio tipo), il parse lancia immediatamente.
 */
import { z } from "zod";

import { api } from "@/shared/api/axios";
import { taskReadSchema, type TaskRead } from "@/features/tasks/schemas/task";

/** Recupera lo stato di un singolo task per il polling. */
export async function getTask(taskId: string): Promise<TaskRead> {
  const { data } = await api.get(`/tasks/${taskId}`);
  return taskReadSchema.parse(data);
}

/** Lista task dell'utente (paginata). Utile per una futura task dashboard. */
export async function listTasks(
  params: { limit?: number; offset?: number } = {},
): Promise<TaskRead[]> {
  const { data } = await api.get("/tasks", { params });
  return z.array(taskReadSchema).parse(data);
}
