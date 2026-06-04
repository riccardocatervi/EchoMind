import { apiFetch } from "@/lib/apiClient";
import type { TaskRead, UUID } from "@/types/api";

export function getTask(taskId: UUID): Promise<TaskRead> {
  return apiFetch<TaskRead>(`/tasks/${taskId}`);
}

export function listTasks(params: { limit?: number; offset?: number } = {}): Promise<TaskRead[]> {
  return apiFetch<TaskRead[]>("/tasks", {
    query: { limit: params.limit, offset: params.offset },
  });
}
