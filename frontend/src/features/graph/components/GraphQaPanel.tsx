import { useState, type FormEvent, type KeyboardEvent } from "react";
import { AlertTriangle, ChevronDown, Loader2, MessageCircleQuestion, Send } from "lucide-react";
import { useTranslation } from "react-i18next";

import { isApiError } from "@/shared/api/axios";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/lib/utils";
import { useAskDocument } from "@/features/graph/api/mutations";
import { useGraphStore } from "@/features/graph/store/graphStore";

/**
 * Pannello GraphRAG: l'utente fa domande in linguaggio naturale sul documento
 * e riceve una risposta basata sul knowledge graph, con citazioni delle entita'
 * usate come fonte. Cliccando una citazione si seleziona il nodo nel grafo.
 *
 * Reso come overlay (in basso a sinistra) dentro il GraphViewer, in linea con
 * gli altri pannelli (controlli in alto a sinistra, dettagli nodo a destra).
 */
export function GraphQaPanel({ documentId }: { documentId: string }) {
  const { t } = useTranslation();
  const [question, setQuestion] = useState("");
  const [open, setOpen] = useState(true);
  const setSelectedNodeId = useGraphStore((state) => state.setSelectedNodeId);
  const ask = useAskDocument(documentId);

  function submit() {
    const trimmed = question.trim();
    if (!trimmed || ask.isPending) return;
    ask.mutate(trimmed);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    submit();
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Invio invia, Shift+Invio = a capo.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  const errorMessage = isApiError(ask.error)
    ? ask.error.status === 404
      ? t("graph.qa.notReady")
      : ask.error.status === 503
        ? t("graph.qa.unavailable")
        : ask.error.message
    : ask.error
      ? t("graph.qa.error")
      : null;

  const answer = ask.data;

  return (
    <section className="absolute bottom-4 left-4 z-10 w-[24rem] max-w-[calc(100%-2rem)] rounded-lg border bg-card/95 shadow-lg backdrop-blur">
      {/* Header / toggle */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 rounded-t-lg px-3 py-2 text-left text-sm font-medium transition-colors hover:bg-accent/50"
      >
        <MessageCircleQuestion className="size-4 shrink-0 text-primary" aria-hidden="true" />
        <span className="flex-1">{t("graph.qa.title")}</span>
        <ChevronDown
          className={cn("size-4 shrink-0 transition-transform", open ? "" : "-rotate-90")}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div className="space-y-3 px-3 pb-3">
          {/* Risposta / stato */}
          {answer ? (
            <div className="max-h-48 space-y-2 overflow-y-auto rounded-md bg-muted/50 p-2.5">
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{answer.answer}</p>
              {answer.citations.length > 0 && (
                <div className="space-y-1 border-t pt-2">
                  <p className="text-xs font-medium text-muted-foreground">
                    {t("graph.qa.sources")}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {answer.citations.map((citation) => (
                      <button
                        key={citation.entity_id}
                        type="button"
                        onClick={() => setSelectedNodeId(citation.entity_id)}
                        title={citation.type}
                        className="cursor-pointer"
                      >
                        <Badge
                          variant="secondary"
                          className="hover:bg-primary hover:text-primary-foreground"
                        >
                          {citation.name}
                        </Badge>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : errorMessage ? (
            <div className="flex items-start gap-2 rounded-md bg-destructive/10 p-2.5 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <p>{errorMessage}</p>
            </div>
          ) : (
            <p className="px-0.5 text-xs text-muted-foreground">{t("graph.qa.hint")}</p>
          )}

          {/* Form domanda */}
          <form onSubmit={onSubmit} className="space-y-2">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={onKeyDown}
              rows={2}
              maxLength={2000}
              placeholder={t("graph.qa.placeholder")}
              aria-label={t("graph.qa.title")}
              className="flex w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            <Button
              type="submit"
              size="sm"
              className="w-full"
              disabled={ask.isPending || question.trim().length === 0}
            >
              {ask.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  {t("graph.qa.asking")}
                </>
              ) : (
                <>
                  <Send className="size-4" aria-hidden="true" />
                  {t("graph.qa.send")}
                </>
              )}
            </Button>
          </form>
        </div>
      )}
    </section>
  );
}
