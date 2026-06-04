import { useQuery } from "@tanstack/react-query";

import { taskKeys } from "@/features/tasks/api/keys";
import { getTask } from "@/features/tasks/api/requests";

/**
 * Stato di un task. Con `poll: true` rinfresca ogni 2s finche' non raggiunge uno
 * stato terminale (succeeded/failed), poi si ferma.
 */
export function useTask(taskId: string | undefined, options: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: taskKeys.detail(taskId ?? ""),
    queryFn: () => getTask(taskId as string),
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      if (!options.poll) return false;
      const status = query.state.data?.status;
      if (status === "succeeded" || status === "failed") return false;
      return 2000;
    },
  });
}
