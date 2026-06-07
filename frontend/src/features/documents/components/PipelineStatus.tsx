import { Check, Loader2, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { cn } from "@/shared/lib/utils";
import type { DocumentStatus } from "@/features/documents/schemas/document";

/**
 * Chiavi i18n per le label degli step ("pipeline.<key>").
 * Le stringhe vengono da useTranslation() per supportare IT/EN.
 */
const STEP_KEYS = ["uploaded", "transcribed", "extracted", "completed"] as const;
type StepKey = (typeof STEP_KEYS)[number];

/**
 * Numero di step COMPLETATI per ogni stato del documento.
 *
 *   progress = 0 --> step 0 e' active (in corso)
 *   progress = 1 --> step 0 done, step 1 active
 *   ...
 *   progress = 4 --> tutti done (completed)
 */
const PROGRESS: Record<DocumentStatus, number> = {
  pending: 0, // caricamento in corso
  uploaded: 1, // "Caricato" done; trascrizione in corso
  transcribed: 2, // "Trascritto" done; estrazione in corso
  extracted: 3, // "Estratto" done; riassunto in corso
  completed: 4, // tutto done
  failed: 0, // gestito separatamente (failedHere)
};

/** Stepper orizzontale che rispecchia il lifecycle a 4 fasi. */
export function PipelineStatus({ status }: { status: DocumentStatus }) {
  const { t } = useTranslation();
  const progress = PROGRESS[status];
  const isFailed = status === "failed";
  const isCompleted = status === "completed";

  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-3">
      {STEP_KEYS.map((key: StepKey, index) => {
        const done = isCompleted || index < progress;
        const active = !isCompleted && !isFailed && index === progress;
        const failedHere = isFailed && index === 0;

        return (
          <li key={key} className="flex items-center gap-2">
            <span
              className={cn(
                "flex size-6 items-center justify-center rounded-full border text-xs font-medium",
                done && "border-emerald-500/40 bg-emerald-500/15 text-emerald-400",
                active && "border-primary/40 bg-primary/15 text-primary",
                failedHere && "border-destructive/40 bg-destructive/15 text-destructive",
                !done && !active && !failedHere && "border-border text-muted-foreground",
              )}
            >
              {done ? (
                <Check className="size-3.5" aria-hidden="true" />
              ) : active ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              ) : failedHere ? (
                <X className="size-3.5" aria-hidden="true" />
              ) : (
                index + 1
              )}
            </span>
            <span
              className={cn(
                "text-sm",
                done || active ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {t(`pipeline.${key}`)}
            </span>
            {index < STEP_KEYS.length - 1 && (
              <span className="mx-1 hidden h-px w-6 bg-border sm:inline-block" aria-hidden="true" />
            )}
          </li>
        );
      })}
    </ol>
  );
}
