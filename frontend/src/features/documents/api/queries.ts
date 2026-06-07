import { useQuery } from "@tanstack/react-query";

import { documentKeys } from "@/features/documents/api/keys";
import { getDocument, listDocuments } from "@/features/documents/api/requests";

/**
 * Stati terminali: il polling si ferma quando uno di questi e' raggiunto.
 * Tutti gli altri stati ('pending', 'uploaded', 'transcribed', 'extracted')
 * indicano elaborazione in corso.
 */
const TERMINAL_STATUSES = new Set(["completed", "failed"]);

export function useDocuments(params: { limit?: number; offset?: number } = {}) {
  return useQuery({
    queryKey: documentKeys.list(params),
    queryFn: () => listDocuments(params),
    // Rifetch ogni 10s se almeno un documento e' ancora in elaborazione:
    // cosi' i badge sulla dashboard si aggiornano automaticamente.
    refetchInterval: (query) => {
      const docs = query.state.data;
      if (!docs) return false;
      return docs.some((d) => !TERMINAL_STATUSES.has(d.status)) ? 10_000 : false;
    },
  });
}

/**
 * Dettaglio di un documento con auto-polling basato sullo stato.
 *
 * Strategia: un singolo `refetchInterval` sul documento invece di N
 * tentativi paralleli su transcript/summary/graph. Il documento e' la
 * sorgente di verita' del lifecycle; quando lo stato diventa terminale
 * il polling si ferma da solo.
 *
 * I componenti figli (TranscriptCard, SummaryView, GraphViewer) vengono
 * abilitati *condizionalmente* basandosi su `doc.status` (vedi DocumentDetailPage).
 */
export function useDocument(documentId: string | undefined) {
  return useQuery({
    queryKey: documentKeys.detail(documentId ?? ""),
    queryFn: () => getDocument(documentId as string),
    enabled: Boolean(documentId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || TERMINAL_STATUSES.has(data.status)) return false;
      // Protezione: se il documento e' bloccato in uno stato non-terminale
      // da piu' di 10 minuti (es. task extract esaurito per Gemini 429),
      // interrompi il polling per evitare richieste infinite.
      // L'utente puo' riprendere manualmente con "Ri-estrai grafo".
      const staleMs = Date.now() - new Date(data.updated_at).getTime();
      if (staleMs > 10 * 60 * 1_000) return false;
      return 3_000; // poll ogni 3s durante l'elaborazione attiva
    },
  });
}
