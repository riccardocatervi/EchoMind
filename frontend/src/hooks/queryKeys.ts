import type { UUID } from "@/types/api";

/**
 * Fabbrica centralizzata delle query key di TanStack Query. Un solo posto da cui
 * derivarle evita chiavi disallineate tra letture e invalidazioni (la causa
 * classica di "ho aggiornato ma la UI non si rinfresca").
 */
export const queryKeys = {
  profile: ["profile"] as const,
  documents: {
    all: ["documents"] as const,
    detail: (id: UUID) => ["documents", id] as const,
  },
  transcript: (id: UUID) => ["transcript", id] as const,
  summary: (id: UUID) => ["summary", id] as const,
  graph: (id: UUID) => ["graph", id] as const,
  task: (id: UUID) => ["task", id] as const,
  tasks: ["tasks"] as const,
};
