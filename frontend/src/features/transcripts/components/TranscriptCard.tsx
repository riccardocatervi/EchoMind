import { FileText } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import type { TranscriptRead } from "@/features/transcripts/schemas/transcript";

export function TranscriptCard({ transcript }: { transcript: TranscriptRead }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
          Transcript
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {transcript.char_count.toLocaleString("it-IT")} caratteri
          {transcript.language ? ` · lingua: ${transcript.language}` : ""}
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
