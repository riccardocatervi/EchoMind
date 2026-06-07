import { AlertTriangle, FileText } from "lucide-react";

import { isApiError } from "@/shared/api/axios";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { useDocuments } from "@/features/documents/api/queries";
import { DocumentCard } from "@/features/documents/components/DocumentCard";
import { UploadDialog } from "@/features/documents/components/UploadDialog";

export function DocumentsPage() {
  const { data: documents, isLoading, isError, error } = useDocuments();

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="font-mono text-2xl font-semibold tracking-tight">I tuoi documenti</h1>
          <p className="text-sm text-muted-foreground">
            Carica testi o audio e trasformali in grafi di conoscenza.
          </p>
        </div>
        <UploadDialog />
      </header>

      {isLoading && <DocumentsSkeleton />}

      {isError && (
        <ErrorState
          message={isApiError(error) ? error.message : "Impossibile caricare i documenti"}
        />
      )}

      {documents && documents.length === 0 && <EmptyState />}

      {documents && documents.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {documents.map((doc) => (
            <DocumentCard key={doc.id} doc={doc} />
          ))}
        </div>
      )}
    </div>
  );
}

function DocumentsSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, index) => (
        <Skeleton key={index} className="h-28 w-full" />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
        <FileText className="size-10 text-muted-foreground" aria-hidden="true" />
        <div className="space-y-1">
          <p className="font-medium">Non hai ancora documenti</p>
          <p className="text-sm text-muted-foreground">
            Usa &quot;Carica documento&quot; per iniziare.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <Card className="border-destructive/30">
      <CardContent className="flex items-center gap-3 py-8 text-destructive">
        <AlertTriangle className="size-5 shrink-0" aria-hidden="true" />
        <p className="text-sm">{message}</p>
      </CardContent>
    </Card>
  );
}
