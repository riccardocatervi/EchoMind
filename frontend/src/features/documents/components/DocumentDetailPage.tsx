import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, RefreshCw } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { isApiError } from "@/shared/api/axios";
import { Button } from "@/shared/components/ui/button";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { useTriggerExtraction } from "@/features/documents/api/mutations";
import { useDocument } from "@/features/documents/api/queries";
import { PipelineStatus, type PipelineStage } from "@/features/documents/components/PipelineStatus";
import { StatusBadge } from "@/features/documents/components/StatusBadge";
import { graphKeys } from "@/features/graph/api/keys";
import { useGraph } from "@/features/graph/api/queries";
import { summaryKeys } from "@/features/summary/api/keys";
import { useSummary } from "@/features/summary/api/queries";
import { SummaryView } from "@/features/summary/components/SummaryView";
import { useTask } from "@/features/tasks/api/queries";
import { useTranscript } from "@/features/transcripts/api/queries";
import { TranscriptCard } from "@/features/transcripts/components/TranscriptCard";

export function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const queryClient = useQueryClient();

  const { data: doc, isLoading } = useDocument(documentId);
  const isUploaded = doc?.status === "uploaded";

  // Polling della pipeline: transcript finche' non c'e'; poi summary+graph.
  const { data: transcript } = useTranscript(documentId, { poll: isUploaded });
  const hasTranscript = Boolean(transcript);
  const { data: summary } = useSummary(documentId, { poll: hasTranscript });
  const { data: graph } = useGraph(documentId, { poll: hasTranscript });

  const stage: PipelineStage =
    doc?.status === "failed"
      ? "failed"
      : !transcript
        ? "transcribing"
        : !summary || !graph
          ? "extracting"
          : "ready";

  // Ri-estrazione: trigger -> task pollato -> all'esito invalida summary+graph.
  const triggerExtraction = useTriggerExtraction();
  const [reExtractTaskId, setReExtractTaskId] = useState<string | null>(null);
  const { data: reExtractTask } = useTask(reExtractTaskId ?? undefined, {
    poll: Boolean(reExtractTaskId),
  });

  useEffect(() => {
    if (!documentId || !reExtractTask) return;
    if (reExtractTask.status === "succeeded") {
      toast.success("Estrazione completata");
      void queryClient.invalidateQueries({ queryKey: summaryKeys.detail(documentId) });
      void queryClient.invalidateQueries({ queryKey: graphKeys.detail(documentId) });
      setReExtractTaskId(null);
    } else if (reExtractTask.status === "failed") {
      toast.error("Estrazione fallita");
      setReExtractTaskId(null);
    }
  }, [reExtractTask, documentId, queryClient]);

  function handleReExtract() {
    if (!documentId) return;
    triggerExtraction.mutate(documentId, {
      onSuccess: (task) => {
        setReExtractTaskId(task.task_id);
        toast.success("Ri-estrazione avviata");
      },
      onError: (error) => {
        toast.error(isApiError(error) ? error.message : "Avvio estrazione fallito");
      },
    });
  }

  const reExtracting =
    triggerExtraction.isPending ||
    reExtractTask?.status === "queued" ||
    reExtractTask?.status === "running";

  return (
    <div className="space-y-6">
      <Link
        to="/"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Documenti
      </Link>

      {isLoading && <Skeleton className="h-8 w-64" />}

      {doc && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-mono text-2xl font-semibold tracking-tight">{doc.filename}</h1>
            <StatusBadge status={doc.status} />
          </div>

          <Card>
            <CardContent className="space-y-4 py-6">
              <PipelineStatus stage={stage} />

              {stage === "transcribing" && (
                <p className="text-sm text-muted-foreground">Trascrizione in corso...</p>
              )}
              {stage === "extracting" && (
                <p className="text-sm text-muted-foreground">
                  Estrazione del grafo di conoscenza in corso...
                </p>
              )}
              {stage === "failed" && (
                <p className="text-sm text-destructive">
                  {doc.failure_reason ?? "Caricamento o validazione del file fallita."}
                </p>
              )}

              {hasTranscript && (
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
                    Ri-estrai grafo
                  </Button>
                  {reExtracting && (
                    <span className="text-sm text-muted-foreground">Ri-estrazione in corso...</span>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {transcript && <TranscriptCard transcript={transcript} />}

          {summary && <SummaryView summary={summary} />}

          {stage === "ready" && (
            <p className="text-sm text-muted-foreground">
              Il grafo e&apos; pronto. La vista interattiva arriva nel prossimo checkpoint.
            </p>
          )}
        </>
      )}
    </div>
  );
}
