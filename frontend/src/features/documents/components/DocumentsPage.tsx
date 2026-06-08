import { useState } from "react";
import { AlertTriangle, FileText, Search } from "lucide-react";
import { Trans, useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { isApiError } from "@/shared/api/axios";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Input } from "@/shared/components/ui/input";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { useDocuments } from "@/features/documents/api/queries";
import { DocumentCard } from "@/features/documents/components/DocumentCard";
import { UploadDialog } from "@/features/documents/components/UploadDialog";

/**
 * Dashboard dei documenti dell'utente.
 *
 * Il GraphBackground e' gestito da AppShell (tutte le schermate autenticate).
 * La barra di ricerca filtra client-side per nome file (case-insensitive).
 */
export function DocumentsPage() {
  const { t } = useTranslation();
  const { data: documents, isLoading, isError, error } = useDocuments();
  const [query, setQuery] = useState("");

  // Filtro client-side: includi solo i documenti il cui filename contiene
  // la stringa di ricerca (case-insensitive). Con query vuota mostra tutto.
  const filtered =
    query.trim() === ""
      ? documents
      : documents?.filter((doc) => doc.filename.toLowerCase().includes(query.trim().toLowerCase()));

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="font-mono text-2xl font-semibold tracking-tight">{t("docs.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("docs.subtitle")}</p>
          {/* Suggerimento: la lingua di output si cambia nel profilo */}
          <p className="text-xs text-muted-foreground/70">
            <Trans
              i18nKey="docs.languageHint"
              components={{
                link: (
                  <Link
                    to="/profile"
                    className="font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                  />
                ),
              }}
            />
          </p>
        </div>
        <UploadDialog />
      </header>

      {/* Barra di ricerca: visibile solo se ci sono documenti */}
      {documents && documents.length > 0 && (
        <div className="relative max-w-sm">
          <Search
            className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            placeholder={t("docs.searchPlaceholder")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      )}

      {isLoading && <DocumentsSkeleton />}

      {isError && <ErrorState message={isApiError(error) ? error.message : t("docs.error")} />}

      {/* Lista vuota (zero documenti in totale) */}
      {!isLoading && !isError && documents && documents.length === 0 && <EmptyState />}

      {/* Nessun risultato dalla ricerca */}
      {!isLoading && !isError && filtered && filtered.length === 0 && query.trim() !== "" && (
        <Card className="border-dashed">
          <CardContent className="flex items-center gap-3 py-8 text-muted-foreground">
            <Search className="size-5 shrink-0" aria-hidden="true" />
            <p className="text-sm">{t("docs.searchEmpty", { query: query.trim() })}</p>
          </CardContent>
        </Card>
      )}

      {filtered && filtered.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((doc) => (
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
  const { t } = useTranslation();
  return (
    <Card className="shadow-[0_0_30px_rgba(99,120,220,0.15)] ring-1 ring-white/5">
      <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
        <FileText className="size-10 text-muted-foreground" aria-hidden="true" />
        <div className="space-y-1">
          <p className="font-medium">{t("docs.empty.title")}</p>
          <p className="text-sm text-muted-foreground">{t("docs.empty.subtitle")}</p>
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
