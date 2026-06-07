import { Badge } from "@/shared/components/ui/badge";
import { cn } from "@/shared/lib/utils";
import type { DocumentStatus } from "@/features/documents/schemas/document";

const STATUS_MAP: Record<DocumentStatus, { label: string; className: string }> = {
  pending: {
    label: "In caricamento",
    className: "border-amber-500/20 bg-amber-500/15 text-amber-400",
  },
  uploaded: {
    label: "Caricato",
    className: "border-emerald-500/20 bg-emerald-500/15 text-emerald-400",
  },
  failed: {
    label: "Fallito",
    className: "border-destructive/30 bg-destructive/15 text-destructive",
  },
};

/** Pillola colorata per lo stato di ingestione del documento. */
export function StatusBadge({ status }: { status: DocumentStatus }) {
  const { label, className } = STATUS_MAP[status];
  return (
    <Badge variant="outline" className={cn(className)}>
      {label}
    </Badge>
  );
}
