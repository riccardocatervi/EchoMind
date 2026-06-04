import { z } from "zod";

import { uuidSchema } from "@/shared/schemas/common";

export const graphNodeSchema = z.object({
  id: uuidSchema,
  name: z.string(),
  type: z.string(),
  description: z.string().nullable(),
  community: z.number().nullable(),
});
export type GraphNode = z.infer<typeof graphNodeSchema>;

export const graphEdgeSchema = z.object({
  source: uuidSchema,
  target: uuidSchema,
  type: z.string(),
  description: z.string().nullable(),
});
export type GraphEdge = z.infer<typeof graphEdgeSchema>;

export const graphReadSchema = z.object({
  document_id: uuidSchema,
  nodes: z.array(graphNodeSchema),
  edges: z.array(graphEdgeSchema),
  node_count: z.number(),
  relationship_count: z.number(),
  community_count: z.number(),
});
export type GraphRead = z.infer<typeof graphReadSchema>;
