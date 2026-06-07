export const taskKeys = {
  all: ["tasks"] as const,
  detail: (id: string) => [...taskKeys.all, id] as const,
};
