import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/shared/api/axios";

/**
 * QueryClient condiviso. Default: staleTime 30s, niente refetch on focus, e
 * nessun retry sugli errori client 4xx (deterministici: 404/401/409).
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
