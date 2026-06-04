import "@xyflow/react/dist/style.css";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
} from "@xyflow/react";
import { Loader2 } from "lucide-react";

import { EntityNode } from "@/features/graph/components/EntityNode";
import { GraphControls } from "@/features/graph/components/GraphControls";
import { NodeDetailsPanel } from "@/features/graph/components/NodeDetailsPanel";
import { communityColor } from "@/features/graph/lib/communityColors";
import { layoutGraph, type EntityNodeData } from "@/features/graph/lib/elkLayout";
import { useGraphStore } from "@/features/graph/store/graphStore";
import type { GraphRead } from "@/features/graph/schemas/graph";

const nodeTypes = { entity: EntityNode };

export function GraphViewer({ graph }: { graph: GraphRead }) {
  const baseRef = useRef<{ nodes: Node[]; edges: Edge[] }>({ nodes: [], edges: [] });
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [ready, setReady] = useState(false);

  const selectedNodeId = useGraphStore((state) => state.selectedNodeId);
  const setSelectedNodeId = useGraphStore((state) => state.setSelectedNodeId);
  const searchTerm = useGraphStore((state) => state.searchTerm);
  const hiddenCommunities = useGraphStore((state) => state.hiddenCommunities);
  const reset = useGraphStore((state) => state.reset);

  // Layout (async) all'arrivo del grafo; azzera i filtri.
  useEffect(() => {
    let active = true;
    setReady(false);
    reset();
    void layoutGraph(graph).then((result) => {
      if (!active) return;
      baseRef.current = result;
      setReady(true);
    });
    return () => {
      active = false;
    };
  }, [graph, reset]);

  // Deriva nodi/archi visibili applicando filtro community + ricerca + selezione.
  useEffect(() => {
    if (!ready) return;
    const term = searchTerm.trim().toLowerCase();
    const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
    const neighborIds = selectedNodeId
      ? new Set(
          graph.edges.flatMap((edge) =>
            edge.source === selectedNodeId
              ? [edge.target]
              : edge.target === selectedNodeId
                ? [edge.source]
                : [],
          ),
        )
      : null;

    const matchesName = (id: string) =>
      term.length > 0 && (nodeById.get(id)?.name.toLowerCase().includes(term) ?? false);

    const hiddenNodeIds = new Set<string>();
    const displayNodes: Node[] = baseRef.current.nodes.map((node) => {
      const community = nodeById.get(node.id)?.community ?? null;
      const hidden = community !== null && hiddenCommunities.has(community);
      if (hidden) hiddenNodeIds.add(node.id);
      const isSelected = node.id === selectedNodeId;
      const isNeighbor = neighborIds?.has(node.id) ?? false;
      const searchMiss = term.length > 0 && !matchesName(node.id);
      const selectionMiss = neighborIds !== null && !isSelected && !isNeighbor;
      const dimmed = searchMiss || selectionMiss;
      return {
        ...node,
        hidden,
        selected: isSelected,
        style: { opacity: dimmed ? 0.25 : 1, transition: "opacity 150ms ease" },
      };
    });

    const displayEdges: Edge[] = baseRef.current.edges.map((edge) => {
      const hidden = hiddenNodeIds.has(edge.source) || hiddenNodeIds.has(edge.target);
      const incident =
        selectedNodeId !== null &&
        (edge.source === selectedNodeId || edge.target === selectedNodeId);
      const searchMiss = term.length > 0 && !(matchesName(edge.source) || matchesName(edge.target));
      const dimmed = (selectedNodeId !== null && !incident) || searchMiss;
      return { ...edge, hidden, animated: incident, style: { opacity: dimmed ? 0.15 : 1 } };
    });

    setNodes(displayNodes);
    setEdges(displayEdges);
  }, [ready, graph, searchTerm, hiddenCommunities, selectedNodeId, setNodes, setEdges]);

  const selectedNode = useMemo(
    () => graph.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [graph.nodes, selectedNodeId],
  );

  if (!ready) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2
          className="size-6 animate-spin text-muted-foreground"
          aria-label="Layout del grafo"
        />
      </div>
    );
  }

  return (
    <div className="relative size-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_event, node) => setSelectedNodeId(node.id)}
        onPaneClick={() => setSelectedNodeId(null)}
      >
        <Background />
        <Controls />
        <MiniMap
          pannable
          zoomable
          className="!bg-card"
          nodeColor={(node) => communityColor((node.data as unknown as EntityNodeData).community)}
        />
      </ReactFlow>
      <GraphControls graph={graph} />
      {selectedNode && (
        <NodeDetailsPanel
          node={selectedNode}
          graph={graph}
          onClose={() => setSelectedNodeId(null)}
          onSelectNode={setSelectedNodeId}
        />
      )}
    </div>
  );
}
