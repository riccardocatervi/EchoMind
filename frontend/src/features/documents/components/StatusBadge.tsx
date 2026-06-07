import { useTranslation } from "react-i18next";

import { Badge } from "@/shared/components/ui/badge";
import { cn } from "@/shared/lib/utils";
import type { DocumentStatus } from "@/features/documents/schemas/document";

/**
 * Colori semantici per lo stato del documento.
 * Le label testuali vengono da i18n ("status.<stato>") per supportare IT/EN.
 *
 *   giallo/amber  -- in elaborazione (pending, uploaded, transcribed, extracted)
 *   verde         -- completato
 *   rosso         -- fallito
 */
const STATUS_CLASS: Record<DocumentStatus, string> = {
  pending: "border-amber-500/20 bg-amber-500/15 text-amber-400",
  uploaded: "border-amber-500/20 bg-amber-500/15 text-amber-400",
  transcribed: "border-amber-500/20 bg-amber-500/15 text-amber-400",
  extracted: "border-amber-500/20 bg-amber-500/15 text-amber-400",
  completed: "border-emerald-500/20 bg-emerald-500/15 text-emerald-400",
  failed: "border-destructive/30 bg-destructive/15 text-destructive",
};

/** Pillola colorata per lo stato di elaborazione del documento. */
export function StatusBadge({ status }: { status: DocumentStatus }) {
  const { t } = useTranslation();
  return (
    <Badge variant="outline" className={cn(STATUS_CLASS[status])}>
      {t(`status.${status}`)}
    </Badge>
  );
}
