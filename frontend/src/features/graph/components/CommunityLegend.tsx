import { communityColor } from "@/features/graph/lib/communityColors";
import type { GraphRead } from "@/features/graph/schemas/graph";

export function CommunityLegend({ graph }: { graph: GraphRead }) {
  const communities = [
    ...new Set(graph.nodes.map((node) => node.community).filter((c): c is number => c !== null)),
  ].sort((a, b) => a - b);

  if (communities.length === 0) return null;

  return (
    <div className="absolute bottom-4 left-4 z-10 rounded-lg border bg-card/90 p-3 text-xs shadow-sm backdrop-blur">
      <p className="mb-2 font-medium">Community</p>
      <ul className="space-y-1">
        {communities.map((community) => (
          <li key={community} className="flex items-center gap-2">
            <span
              className="size-3 rounded-full"
              style={{ backgroundColor: communityColor(community) }}
              aria-hidden="true"
            />
            Community {community}
          </li>
        ))}
      </ul>
    </div>
  );
}
