import { Check, Loader2, X } from "lucide-react";

import { cn } from "@/shared/lib/utils";

export type PipelineStage = "failed" | "transcribing" | "extracting" | "ready";

const STEPS = [
  { key: "uploaded", label: "Caricato" },
  { key: "transcribing", label: "Trascrizione" },
  { key: "extracting", label: "Estrazione" },
  { key: "ready", label: "Pronto" },
] as const;

function activeIndexOf(stage: PipelineStage): number {
  switch (stage) {
    case "failed":
      return 0;
    case "transcribing":
      return 1;
    case "extracting":
      return 2;
    case "ready":
      return 3;
  }
}

/** Stepper orizzontale dello stato di elaborazione del documento. */
export function PipelineStatus({ stage }: { stage: PipelineStage }) {
  const activeIndex = activeIndexOf(stage);

  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-3">
      {STEPS.map((step, index) => {
        const done = stage === "ready" || index < activeIndex;
        const active = stage !== "ready" && stage !== "failed" && index === activeIndex;
        const failedHere = stage === "failed" && index === 0;

        return (
          <li key={step.key} className="flex items-center gap-2">
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
              {step.label}
            </span>
            {index < STEPS.length - 1 && (
              <span className="mx-1 hidden h-px w-6 bg-border sm:inline-block" aria-hidden="true" />
            )}
          </li>
        );
      })}
    </ol>
  );
}
