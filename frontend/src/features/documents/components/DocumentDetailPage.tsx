import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { Skeleton } from "@/shared/components/ui/skeleton";
import { useDocument } from "@/features/documents/api/queries";
import { StatusBadge } from "@/features/documents/components/StatusBadge";

/**
 * Stub della pagina di dettaglio. CP6 aggiungera' lo stato della pipeline
 * (transcript/extract via polling), CP7 il riassunto e CP8 il grafo.
 */
export function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const { data: doc, isLoading } = useDocument(documentId);

  return (
    <div className="space-y-4">
      <Link
        to="/"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Documenti
      </Link>

      {isLoading && <Skeleton className="h-8 w-64" />}

      {doc && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-mono text-2xl font-semibold tracking-tight">{doc.filename}</h1>
            <StatusBadge status={doc.status} />
          </div>
          <p className="text-muted-foreground">
            Transcript, riassunto e grafo arrivano nei prossimi checkpoint.
          </p>
        </div>
      )}
    </div>
  );
}
