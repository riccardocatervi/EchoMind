import { useMemo } from "react";
import { Search, X } from "lucide-react";

import { Input } from "@/shared/components/ui/input";
import { cn } from "@/shared/lib/utils";
import { communityColor } from "@/features/graph/lib/communityColors";
import { useGraphStore } from "@/features/graph/store/graphStore";
import type { GraphRead } from "@/features/graph/schemas/graph";

/** Pannello fluttuante: ricerca nodi + filtro community (legenda interattiva). */
export function GraphControls({ graph }: { graph: GraphRead }) {
  const searchTerm = useGraphStore((state) => state.searchTerm);
  const setSearchTerm = useGraphStore((state) => state.setSearchTerm);
  const hiddenCommunities = useGraphStore((state) => state.hiddenCommunities);
  const toggleCommunity = useGraphStore((state) => state.toggleCommunity);

  const communities = useMemo(() => {
    const counts = new Map<number, number>();
    for (const node of graph.nodes) {
      if (node.community !== null)
        counts.set(node.community, (counts.get(node.community) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => a[0] - b[0]);
  }, [graph.nodes]);

  return (
    <div className="absolute left-4 top-4 z-10 w-56 space-y-3 rounded-lg border bg-card/90 p-3 shadow-sm backdrop-blur">
      <div className="relative">
        <Search
          className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          placeholder="Cerca nodo..."
          aria-label="Cerca nodo"
          className="h-9 px-8"
        />
        {searchTerm && (
          <button
            type="button"
            onClick={() => setSearchTerm("")}
            aria-label="Pulisci ricerca"
            className="absolute right-2 top-1/2 -translate-y-1/2 cursor-pointer text-muted-foreground transition-colors hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        )}
      </div>

      {communities.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Community</p>
          <ul className="space-y-0.5">
            {communities.map(([community, count]) => {
              const hidden = hiddenCommunities.has(community);
              return (
                <li key={community}>
                  <button
                    type="button"
                    onClick={() => toggleCommunity(community)}
                    aria-pressed={!hidden}
                    className={cn(
                      "flex w-full cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-left text-xs transition-colors hover:bg-accent",
                      hidden && "opacity-40",
                    )}
                  >
                    <span
                      className="size-3 shrink-0 rounded-full"
                      style={{ backgroundColor: communityColor(community) }}
                      aria-hidden="true"
                    />
                    <span className="flex-1">Community {community}</span>
                    <span className="text-muted-foreground">{count}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
