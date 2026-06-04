import { AlertTriangle, ArrowLeft, Loader2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { isApiError } from "@/shared/api/axios";
import { useGraph } from "@/features/graph/api/queries";
import { GraphViewer } from "@/features/graph/components/GraphViewer";

/** Pagina full-canvas del grafo. Default export: caricata in lazy dal router. */
export default function GraphPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const { data: graph, isLoading, isError, error } = useGraph(documentId);

  const errorMessage = isApiError(error)
    ? error.status === 404
      ? "Il grafo non e' ancora pronto."
      : error.status === 503
        ? "Il backend del grafo (Neo4j) non e' raggiungibile."
        : error.message
    : "Errore nel caricamento del grafo";

  return (
    <div className="space-y-4">
      <Link
        to={documentId ? `/documents/${documentId}` : "/"}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Documento
      </Link>

      <div className="h-[calc(100vh-12rem)] w-full overflow-hidden rounded-lg border bg-card/30">
        {isLoading && (
          <div className="flex h-full items-center justify-center">
            <Loader2
              className="size-6 animate-spin text-muted-foreground"
              aria-label="Caricamento"
            />
          </div>
        )}
        {isError && (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-muted-foreground">
            <AlertTriangle className="size-6" aria-hidden="true" />
            <p className="text-sm">{errorMessage}</p>
          </div>
        )}
        {graph && graph.nodes.length === 0 && (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Nessun nodo nel grafo.
          </div>
        )}
        {graph && graph.nodes.length > 0 && <GraphViewer graph={graph} />}
      </div>
    </div>
  );
}
