import { describe, expect, it } from "vitest";

import { layoutGraph } from "@/features/graph/lib/elkLayout";
import type { GraphRead } from "@/features/graph/schemas/graph";

const graph: GraphRead = {
  document_id: "doc-1",
  nodes: [
    { id: "a", name: "Alpha", type: "CONCEPT", description: null, community: 0 },
    { id: "b", name: "Beta", type: "CONCEPT", description: null, community: 1 },
  ],
  edges: [{ source: "a", target: "b", type: "related_to", description: null }],
  node_count: 2,
  relationship_count: 1,
  community_count: 2,
};

describe("layoutGraph", () => {
  it("posiziona i nodi e mantiene gli archi", async () => {
    const { nodes, edges } = await layoutGraph(graph);
    expect(nodes).toHaveLength(2);
    expect(edges).toHaveLength(1);
    for (const node of nodes) {
      expect(typeof node.position.x).toBe("number");
      expect(typeof node.position.y).toBe("number");
    }
  });
});
