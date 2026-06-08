import { ListTree, Network, Share2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/shared/components/ui/accordion";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import type { SummaryRead } from "@/features/summary/schemas/summary";

/** Estrae un valore numerico dal meta (Record<string, unknown>) in modo sicuro. */
function metaNumber(meta: Record<string, unknown>, key: string): number | null {
  const value = meta[key];
  return typeof value === "number" ? value : null;
}

export function SummaryView({ summary }: { summary: SummaryRead }) {
  const { t } = useTranslation();
  const nodes = metaNumber(summary.meta, "node_count");
  const relationships = metaNumber(summary.meta, "relationship_count");
  const communities = metaNumber(summary.meta, "community_count");
  const hasStats = nodes !== null || relationships !== null || communities !== null;

  return (
    <Card className="shadow-[0_0_30px_rgba(99,120,220,0.15)] ring-1 ring-white/5">
      <CardHeader>
        <CardTitle className="text-base">{t("summary.title")}</CardTitle>
        {hasStats && (
          <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
            {nodes !== null && (
              <span className="inline-flex items-center gap-1">
                <Network className="size-3.5" aria-hidden="true" />
                {t("summary.stats.nodes", { n: nodes })}
              </span>
            )}
            {relationships !== null && (
              <span className="inline-flex items-center gap-1">
                <Share2 className="size-3.5" aria-hidden="true" />
                {t("summary.stats.relationships", { n: relationships })}
              </span>
            )}
            {communities !== null && (
              <span className="inline-flex items-center gap-1">
                <ListTree className="size-3.5" aria-hidden="true" />
                {t("summary.stats.communities", { n: communities })}
              </span>
            )}
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="leading-relaxed">{summary.overview}</p>

        {summary.sections.length > 0 && (
          <Accordion type="multiple" className="w-full">
            {summary.sections.map((section, index) => (
              <AccordionItem key={index} value={`section-${index}`}>
                <AccordionTrigger>{section.title}</AccordionTrigger>
                <AccordionContent className="whitespace-pre-wrap leading-relaxed text-muted-foreground">
                  {section.content}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        )}
      </CardContent>
    </Card>
  );
}
