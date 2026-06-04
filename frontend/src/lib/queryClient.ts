import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/apiClient";

/**
 * QueryClient condiviso. Default sensati:
 *  - staleTime 30s: niente refetch a raffica navigando tra le pagine;
 *  - niente retry su errori client 4xx (deterministici, es. 404/401/409):
 *    ritentarli sarebbe inutile e rallenterebbe la UI;
 *  - refetchOnWindowFocus off: evita refetch a ogni cambio tab (rumoroso in dev).
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
          return false;
        }
        return failureCount < 2;
      },
    },
  },
});
