import "@xyflow/react/dist/style.css";

import { useEffect, useMemo, useState } from "react";
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

import { CommunityLegend } from "@/features/graph/components/CommunityLegend";
import { EntityNode } from "@/features/graph/components/EntityNode";
import { NodeDetailsPanel } from "@/features/graph/components/NodeDetailsPanel";
import { communityColor } from "@/features/graph/lib/communityColors";
import { layoutGraph, type EntityNodeData } from "@/features/graph/lib/elkLayout";
import { useGraphStore } from "@/features/graph/store/graphStore";
import type { GraphRead } from "@/features/graph/schemas/graph";

const nodeTypes = { entity: EntityNode };

export function GraphViewer({ graph }: { graph: GraphRead }) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [ready, setReady] = useState(false);
  const selectedNodeId = useGraphStore((state) => state.selectedNodeId);
  const setSelectedNodeId = useGraphStore((state) => state.setSelectedNodeId);

  useEffect(() => {
    let active = true;
    setReady(false);
    setSelectedNodeId(null);
    void layoutGraph(graph).then(({ nodes: laidOutNodes, edges: laidOutEdges }) => {
      if (!active) return;
      setNodes(laidOutNodes);
      setEdges(laidOutEdges);
      setReady(true);
    });
    return () => {
      active = false;
    };
  }, [graph, setNodes, setEdges, setSelectedNodeId]);

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
      <CommunityLegend graph={graph} />
      {selectedNode && (
        <NodeDetailsPanel
          node={selectedNode}
          graph={graph}
          onClose={() => setSelectedNodeId(null)}
        />
      )}
    </div>
  );
}
