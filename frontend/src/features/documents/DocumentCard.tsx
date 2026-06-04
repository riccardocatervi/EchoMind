import { useState } from "react";
import { Loader2, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { StatusBadge } from "@/components/StatusBadge";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useDeleteDocument } from "@/hooks/documents";
import { isApiError } from "@/lib/apiClient";
import { formatBytes, formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { DocumentRead } from "@/types/api";

export function DocumentCard({ doc }: { doc: DocumentRead }) {
  const deleteDocument = useDeleteDocument();
  const [confirmOpen, setConfirmOpen] = useState(false);

  function handleDelete() {
    deleteDocument.mutate(doc.id, {
      onSuccess: () => {
        toast.success("Documento eliminato");
        setConfirmOpen(false);
      },
      onError: (error) => {
        toast.error(isApiError(error) ? error.message : "Eliminazione fallita");
      },
    });
  }

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
        <div className="min-w-0 space-y-1">
          <Link
            to={`/documents/${doc.id}`}
            className="block truncate font-medium hover:underline"
            title={doc.filename}
          >
            {doc.filename}
          </Link>
          <p className="text-xs text-muted-foreground">
            {formatBytes(doc.size_bytes)} · {formatDateTime(doc.created_at)}
          </p>
        </div>
        <StatusBadge status={doc.status} />
      </CardHeader>
      <CardContent className="mt-auto flex items-center justify-between gap-2 pt-0">
        <Link
          to={`/documents/${doc.id}`}
          className={cn(buttonVariants({ variant: "secondary", size: "sm" }))}
        >
          Apri
        </Link>
        <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <AlertDialogTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Elimina documento">
              <Trash2 aria-hidden="true" />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Eliminare il documento?</AlertDialogTitle>
              <AlertDialogDescription>
                &quot;{doc.filename}&quot; verra&apos; rimosso definitivamente, insieme a
                transcript, riassunto e grafo. L&apos;operazione e&apos; irreversibile.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deleteDocument.isPending}>Annulla</AlertDialogCancel>
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={deleteDocument.isPending}
              >
                {deleteDocument.isPending && (
                  <Loader2 className="animate-spin" aria-hidden="true" />
                )}
                Elimina
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  );
}
