/**
 * Pagina di dettaglio di un documento: mostra il lifecycle e i risultati della pipeline.
 *
 * Architettura di polling:
 *   Un unico `useDocument` fa polling ogni 3s finché lo status non è terminale.
 *   I figli (TranscriptCard, SummaryView) vengono abilitati condizionalmente tramite
 *   gate `canShow*`, evitando fetch inutili che tornerebbero 404 durante l'elaborazione.
 *
 * Perché `canShowTranscript = status in {transcribed, extracted, completed}`:
 *   Il transcript è disponibile dal momento M4 (transcribe task completato).
 *   Il grafo richiede M5 parziale (extracted). Il summary richiede M5 completo (completed).
 *
 * Rilevamento documento bloccato (`isStuck`):
 *   Se `updated_at` non cambia da 10 minuti in uno stato non-terminale, il task
 *   è probabilmente morto in DLQ (Celery Dead Letter Queue). L'hook di polling
 *   si ferma (timeout in useDocument) e mostriamo un avviso con pulsante manuale.
 *
 * Re-estrazione manuale:
 *   `useTriggerExtraction` accodda il task e restituisce un task_id.
 *   `useTask(reExtractTaskId, { poll: true })` fa polling sul task finché non è
 *   terminale. Al successo, invalida le cache di summary e grafo per aggiornare
 *   SummaryView e GraphViewer senza reload di pagina.
 *
 * Header sticky (`sticky top-14 z-10`):
 *   top-14 = altezza dell'AppShell header (h-14 = 56px). Usare `top-14` invece
 *   di `top-0` evita che l'header della pagina si sovrapponga all'header globale.
 *   `-mx-[1.5rem] px-[1.5rem]`: nega e riapplica il padding del container per
 *   avere sfondo e bordo inferiore a piena larghezza.
 */
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Network, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { isApiError } from "@/shared/api/axios";
import { Button, buttonVariants } from "@/shared/components/ui/button";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { cn } from "@/shared/lib/utils";
import { useTriggerExtraction } from "@/features/documents/api/mutations";
import { useDocument } from "@/features/documents/api/queries";
import { PipelineStatus } from "@/features/documents/components/PipelineStatus";
import { StatusBadge } from "@/features/documents/components/StatusBadge";
import { graphKeys } from "@/features/graph/api/keys";
import { useGraph } from "@/features/graph/api/queries";
import { summaryKeys } from "@/features/summary/api/keys";
import { useSummary } from "@/features/summary/api/queries";
import { useTask } from "@/features/tasks/api/queries";
import { useTranscript } from "@/features/transcripts/api/queries";
import { TranscriptCard } from "@/features/transcripts/components/TranscriptCard";
import { SummaryView } from "@/features/summary/components/SummaryView";

export function DocumentDetailPage() {
  const { t } = useTranslation();
  const { documentId } = useParams<{ documentId: string }>();
  const queryClient = useQueryClient();

  // Unica sorgente di polling: il documento. L'hook fa auto-refetch ogni 3s
  // finche' lo status e' non-terminale ('pending','uploaded','transcribed','extracted').
  const { data: doc, isLoading } = useDocument(documentId);

  // Gate per-status: abilita il fetch dei figli solo quando i dati sono pronti.
  // Niente piu' chiamate che tornano 404 durante l'elaborazione.
  const canShowTranscript =
    doc?.status === "transcribed" || doc?.status === "extracted" || doc?.status === "completed";
  const canShowGraph = doc?.status === "extracted" || doc?.status === "completed";
  const canShowSummary = doc?.status === "completed";

  // Rilevamento blocco: il polling si ferma da solo dopo 10 minuti di
  // nessun cambio di stato (protezione da task esauriti per 429 etc.).
  // Mostriamo un avviso per invitare l'utente a riprovare manualmente.
  const STUCK_THRESHOLD_MS = 10 * 60 * 1_000;
  const isStuck = Boolean(
    doc &&
    !["completed", "failed"].includes(doc.status) &&
    Date.now() - new Date(doc.updated_at).getTime() > STUCK_THRESHOLD_MS,
  );

  const { data: transcript } = useTranscript(documentId, { enabled: canShowTranscript });
  const { data: summary } = useSummary(documentId, { enabled: canShowSummary });
  const { data: graph } = useGraph(documentId, { enabled: canShowGraph });

  // --- Ri-estrazione manuale ---
  const triggerExtraction = useTriggerExtraction();
  const [reExtractTaskId, setReExtractTaskId] = useState<string | null>(null);
  const { data: reExtractTask } = useTask(reExtractTaskId ?? undefined, {
    poll: Boolean(reExtractTaskId),
  });

  useEffect(() => {
    if (!documentId || !reExtractTask) return;
    if (reExtractTask.status === "succeeded") {
      toast.success(t("doc.extractionComplete"));
      void queryClient.invalidateQueries({ queryKey: summaryKeys.detail(documentId) });
      void queryClient.invalidateQueries({ queryKey: graphKeys.detail(documentId) });
      setReExtractTaskId(null);
    } else if (reExtractTask.status === "failed") {
      toast.error(t("doc.extractionFailed"));
      setReExtractTaskId(null);
    }
  }, [reExtractTask, documentId, queryClient, t]);

  function handleReExtract() {
    if (!documentId) return;
    triggerExtraction.mutate(documentId, {
      onSuccess: (task) => {
        setReExtractTaskId(task.task_id);
        toast.success(t("doc.reExtractionStarted"));
      },
      onError: (error) => {
        toast.error(isApiError(error) ? error.message : t("doc.reExtractionError"));
      },
    });
  }

  const reExtracting =
    triggerExtraction.isPending ||
    reExtractTask?.status === "queued" ||
    reExtractTask?.status === "running";

  return (
    <div>
      {/*
       * Header sticky: rimane visibile mentre l'utente scorre il contenuto.
       * top-14 = altezza dell'AppShell header (h-14 = 3.5rem = 56px).
       * -mx-[1.5rem] px-[1.5rem] negano e riaplicano il padding del container
       * (tailwind.config.ts: padding: "1.5rem") per avere sfondo e bordo
       * a tutta larghezza del container.
       */}
      <div className="sticky top-14 z-10 -mx-[1.5rem] flex items-center justify-between border-b bg-background/95 px-[1.5rem] py-3 backdrop-blur">
        <Link
          to="/documents"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          {t("doc.back")}
        </Link>

        {/* Il pulsante "Esplora il grafo" appare appena il grafo e' pronto,
            cosi' l'utente non deve scorrere fino in fondo per trovarlo. */}
        {graph && graph.nodes.length > 0 && (
          <Link
            to={`/documents/${documentId}/graph`}
            className={cn(buttonVariants({ size: "sm" }))}
          >
            <Network aria-hidden="true" />
            {t("doc.exploreGraph")} ({graph.node_count} {t("common.nodes")})
          </Link>
        )}
      </div>

      {/* Contenuto principale */}
      <div className="space-y-6 pt-6">
        {isLoading && <Skeleton className="h-8 w-64" />}

        {doc && (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-mono text-2xl font-semibold tracking-tight">{doc.filename}</h1>
              <StatusBadge status={doc.status} />
            </div>

            {/*
             * Glow: `shadow-[0_0_30px_rgba(99,120,220,0.15)]` crea l'alone blu-indaco.
             * `ring-1 ring-white/5`: bordo sottile per separare la card dallo sfondo.
             * Coerente con AuthShell e EmptyState (stessa famiglia di colori).
             */}
            <Card className="shadow-[0_0_30px_rgba(99,120,220,0.15)] ring-1 ring-white/5">
              <CardContent className="space-y-4 py-6">
                <PipelineStatus status={doc.status} />

                {/* Messaggi di stato durante l'elaborazione */}
                {doc.status === "uploaded" && !isStuck && (
                  <p className="text-sm text-muted-foreground">{t("doc.status.uploading")}</p>
                )}
                {doc.status === "transcribed" && !isStuck && (
                  <p className="text-sm text-muted-foreground">{t("doc.status.transcribed")}</p>
                )}
                {doc.status === "extracted" && !isStuck && (
                  <p className="text-sm text-muted-foreground">{t("doc.status.extracted")}</p>
                )}
                {doc.status === "failed" && (
                  <p className="text-sm text-destructive">
                    {doc.failure_reason ?? t("doc.status.failureDefault")}
                  </p>
                )}
                {/* Avviso quando il polling si e' fermato per timeout:
                    il task e' probabilmente morto (es. Gemini 429 esaurito). */}
                {isStuck && <p className="text-sm text-amber-400">{t("doc.status.stuck")}</p>}

                {/* Ri-estrazione disponibile dal momento in cui il transcript c'e'. */}
                {canShowTranscript && (
                  <div className="flex flex-wrap items-center gap-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleReExtract}
                      disabled={reExtracting}
                    >
                      {reExtracting ? (
                        <Loader2 className="animate-spin" aria-hidden="true" />
                      ) : (
                        <RefreshCw aria-hidden="true" />
                      )}
                      {t("doc.reExtract")}
                    </Button>
                    {reExtracting && (
                      <span className="text-sm text-muted-foreground">{t("doc.reExtracting")}</span>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {transcript && <TranscriptCard transcript={transcript} />}

            {summary && <SummaryView summary={summary} />}
          </>
        )}
      </div>
    </div>
  );
}
