import { useQuery } from "@tanstack/react-query";

import { getTask } from "@/api/tasks";
import { queryKeys } from "@/hooks/queryKeys";
import type { UUID } from "@/types/api";

/**
 * Stato di un task. Con `poll: true` rinfresca ogni 2s finche' non raggiunge uno
 * stato terminale (succeeded/failed), poi si ferma da solo.
 */
export function useTask(taskId: UUID | undefined, options: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.task(taskId ?? ""),
    queryFn: () => getTask(taskId as UUID),
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      if (!options.poll) return false;
      const status = query.state.data?.status;
      if (status === "succeeded" || status === "failed") return false;
      return 2000;
    },
  });
}
