/**
 * Card del transcript testuale del documento.
 *
 * Mostra:
 *   - Conteggio caratteri (`char_count` precomputato dal backend, non ricalcolato).
 *   - Lingua rilevata (solo per trascrizioni audio Whisper; null per documenti testo).
 *   - Il testo completo in un'area scrollabile con max-height: 320px.
 *
 * `max-h-80 overflow-y-auto`:
 *   Limita l'altezza della card a 320px. I transcript di documenti lunghi (libri,
 *   audio di ore) possono essere molto grandi (>100.000 caratteri). Mostrare tutto
 *   il testo flat renderebbe la pagina inutilizzabile. L'area scrollabile permette
 *   di leggere senza bloccare il layout.
 *
 * `whitespace-pre-wrap`:
 *   Preserva gli a capo originali del transcript (newline da Whisper / parser PDF).
 *   Senza questo, tutto il testo sarebbe su una sola riga.
 *
 * `toLocaleString("it-IT")` su `char_count`:
 *   Formatta il numero con separatore migliaia italiano (es. 12.345 invece di 12345).
 */
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
