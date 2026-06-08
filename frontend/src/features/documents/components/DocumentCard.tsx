import { useState } from "react";
import { Loader2, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { isApiError } from "@/shared/api/axios";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/shared/components/ui/alert-dialog";
import { Button, buttonVariants } from "@/shared/components/ui/button";
import { Card, CardContent, CardHeader } from "@/shared/components/ui/card";
import { formatBytes, formatDateTime } from "@/shared/lib/format";
import { cn } from "@/shared/lib/utils";
import { useDeleteDocument } from "@/features/documents/api/mutations";
import { StatusBadge } from "@/features/documents/components/StatusBadge";
import type { DocumentRead } from "@/features/documents/schemas/document";

export function DocumentCard({ doc }: { doc: DocumentRead }) {
  const { t } = useTranslation();
  const deleteDocument = useDeleteDocument();
  const [confirmOpen, setConfirmOpen] = useState(false);

  function handleDelete() {
    deleteDocument.mutate(doc.id, {
      onSuccess: () => {
        toast.success(t("doc.delete.success"));
        setConfirmOpen(false);
      },
      onError: (error) => {
        toast.error(isApiError(error) ? error.message : t("doc.delete.error"));
      },
    });
  }

  return (
    <Card className="flex flex-col transition-shadow duration-300 hover:shadow-[0_0_28px_rgba(99,120,220,0.22)] hover:ring-1 hover:ring-white/10">
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
          {t("common.open")}
        </Link>
        <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <AlertDialogTrigger asChild>
            <Button variant="ghost" size="icon" aria-label={t("doc.delete.trigger")}>
              <Trash2 aria-hidden="true" />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t("doc.delete.title")}</AlertDialogTitle>
              <AlertDialogDescription>
                {t("doc.delete.description", { filename: doc.filename })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deleteDocument.isPending}>
                {t("doc.delete.cancel")}
              </AlertDialogCancel>
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={deleteDocument.isPending}
              >
                {deleteDocument.isPending && (
                  <Loader2 className="animate-spin" aria-hidden="true" />
                )}
                {t("doc.delete.confirm")}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  );
}
