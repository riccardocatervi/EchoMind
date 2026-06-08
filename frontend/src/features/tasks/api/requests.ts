import { z } from "zod";

import { api } from "@/shared/api/axios";
import { taskReadSchema, type TaskRead } from "@/features/tasks/schemas/task";

export async function getTask(taskId: string): Promise<TaskRead> {
  const { data } = await api.get(`/tasks/${taskId}`);
  return taskReadSchema.parse(data);
}

export async function listTasks(
  params: { limit?: number; offset?: number } = {},
): Promise<TaskRead[]> {
  const { data } = await api.get("/tasks", { params });
  return z.array(taskReadSchema).parse(data);
}
