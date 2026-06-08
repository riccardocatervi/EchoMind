import { FileText } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import type { TranscriptRead } from "@/features/transcripts/schemas/transcript";

export function TranscriptCard({ transcript }: { transcript: TranscriptRead }) {
  const { t } = useTranslation();

  return (
    <Card className="shadow-[0_0_30px_rgba(99,120,220,0.15)] ring-1 ring-white/5">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
          {t("doc.transcript")}
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {transcript.char_count.toLocaleString("it-IT")} {t("doc.transcript.chars")}
          {transcript.language ? ` · ${t("doc.transcript.lang")}: ${transcript.language}` : ""}
        </p>
      </CardHeader>
      <CardContent>
        <div className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-md bg-muted/40 p-4 text-sm leading-relaxed">
          {transcript.content}
        </div>
      </CardContent>
    </Card>
  );
}
