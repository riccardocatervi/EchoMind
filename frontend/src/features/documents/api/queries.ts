/**
 * Query hooks per i documenti (TanStack Query).
 *
 * Strategia di polling:
 *   TanStack Query supporta il polling tramite `refetchInterval`. Invece di un
 *   intervallo fisso, usiamo una funzione che decide SE e ogni quanto ri-fetchare
 *   in base allo stato corrente dei dati. Questo evita richieste inutili quando
 *   tutti i documenti sono già in stato terminale.
 *
 *   TERMINAL_STATUSES = { "completed", "failed" }
 *   Tutti gli altri stati ("pending", "uploaded", "transcribed", "extracted")
 *   indicano elaborazione in corso → il polling continua.
 *
 * `useDocuments` (lista):
 *   Poll ogni 10s SE almeno un documento è non-terminale. Serve a mantenere i
 *   badge di stato aggiornati nella dashboard senza che l'utente debba fare reload.
 *
 * `useDocument` (singolo):
 *   Poll ogni 3s durante l'elaborazione attiva (aggiornamento più reattivo per
 *   la DocumentDetailPage). Il polling si ferma automaticamente quando:
 *     a) lo status è terminale ("completed" o "failed"), oppure
 *     b) il documento è fermo da più di 10 minuti (task probabilmente morto per
 *        quota Gemini esaurita o DLQ — l'utente può riprendere manualmente).
 *
 * Perché NON usare Supabase Realtime / WebSocket:
 *   Il piano Free Tier di Supabase ha limiti stretti sui canali Realtime.
 *   Il polling HTTP ogni 3s è semplice, robusto, e non richiede infrastruttura
 *   aggiuntiva (websocket, load balancer sticky-session, ecc.).
 */
import { useQuery } from "@tanstack/react-query";

import { documentKeys } from "@/features/documents/api/keys";
import { getDocument, listDocuments } from "@/features/documents/api/requests";

/** Stati terminali: il polling si ferma quando uno di questi è raggiunto. */
const TERMINAL_STATUSES = new Set(["completed", "failed"]);

export function useDocuments(params: { limit?: number; offset?: number } = {}) {
  return useQuery({
    queryKey: documentKeys.list(params),
    queryFn: () => listDocuments(params),
    // Rifetch ogni 10s se almeno un documento è ancora in elaborazione:
    // cosi i badge sulla dashboard si aggiornano automaticamente.
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
 * Strategia: un singolo `refetchInterval` sul documento invece di N tentativi
 * paralleli su transcript/summary/graph. Il documento è la sorgente di verità
 * del lifecycle; quando lo stato diventa terminale il polling si ferma da solo.
 *
 * I componenti figli (TranscriptCard, SummaryView, GraphViewer) vengono
 * abilitati *condizionalmente* basandosi su `doc.status` (vedi DocumentDetailPage).
 */
export function useDocument(documentId: string | undefined) {
  return useQuery({
    queryKey: documentKeys.detail(documentId ?? ""),
    queryFn: () => getDocument(documentId as string),
    // `enabled: false` evita fetch quando documentId non è ancora disponibile
    // (es. route param non ancora risolto). Importante per non generare 404.
    enabled: Boolean(documentId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || TERMINAL_STATUSES.has(data.status)) return false;
      // Protezione da task bloccati: se updated_at non cambia da 10 minuti,
      // il task è probabilmente morto (Gemini 429 esaurito → DLX) e il
      // polling non ha senso. L'utente può riprendere con "Ri-estrai grafo".
      const staleMs = Date.now() - new Date(data.updated_at).getTime();
      if (staleMs > 10 * 60 * 1_000) return false;
      return 3_000; // poll ogni 3s durante l'elaborazione attiva
    },
  });
}
