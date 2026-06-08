export const documentKeys = {
  all: ["documents"] as const,
  list: (params: { limit?: number; offset?: number }) =>
    [...documentKeys.all, "list", params] as const,
  detail: (id: string) => [...documentKeys.all, "detail", id] as const,
};
