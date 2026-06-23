/**
 * QueryClient condiviso — configurazione globale di TanStack Query.
 *
 * TanStack Query (ex React Query) è la libreria di "server state management":
 * gestisce caching, de-duplicazione di richieste concorrenti, refetch,
 * polling, aggiornamenti ottimistici e sincronizzazione con il server.
 *
 * Perché TanStack Query e non Redux/Context per i dati server:
 *   Il server state (documenti, task, grafo) ha semantica diversa dal client state
 *   (sessione auth, UI state). È "stale" per natura: va ri-fetchato periodicamente.
 *   TanStack Query gestisce questo ciclo di vita automaticamente; Redux no.
 *
 * Parametri configurati e motivazioni:
 *
 *   staleTime: 30_000 (30 secondi)
 *     Finestra durante cui i dati in cache sono considerati "freschi". In questo
 *     intervallo, `useQuery` ritorna i dati in cache senza ri-fetchare. Dopo 30s
 *     i dati diventano "stale" → al prossimo montaggio del componente o focus di
 *     finestra viene fatto un background refetch. Scelta: 30s è un buon compromesso
 *     per dati che cambiano poco (lista documenti) ma devono restare aggiornati.
 *
 *   refetchOnWindowFocus: false
 *     Di default Query refetcha OGNI VOLTA che la finestra riprende il focus
 *     (utente torna dalla scheda/app). Questo causa flash di loading e richieste
 *     extra non necessarie per la nostra app (il polling esplicito di PipelineStatus
 *     gestisce già gli aggiornamenti in corso d'opera). Disabilitato.
 *
 *   retry (funzione custom):
 *     Default Query: 3 retry su qualsiasi errore. Ma gli errori 4xx (400-499) sono
 *     DETERMINISTICI: 401 (non autenticato), 404 (non trovato), 409 (conflitto) non
 *     cambieranno mai con un retry. Ritentare è inutile e peggiora la perceived
 *     latency. La funzione custom blocca i retry per status >= 400 < 500, e ne
 *     permette al massimo 2 per errori 5xx (transitori: rete, server overload).
 *
 * Il QueryClient viene passato al QueryClientProvider in main.tsx:
 *   Un singleton di sessione browser; ricrearlo ad ogni render causa il reset
 *   della cache (tutti i dati vengono persi).
 */
import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/shared/api/axios";

/**
 * QueryClient condiviso. Default: staleTime 30s, niente refetch on focus, e
 * nessun retry sugli errori client 4xx (deterministici: 404/401/409).
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 30 secondi di "freschezza": bilancia aggiornamento e richieste di rete.
      staleTime: 30_000,
      // Disabilitato: evita refetch inutili al cambio di tab (il polling
      // esplicito in PipelineStatus già gestisce l'aggiornamento dei task).
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // 4xx deterministici: nessun retry (non cambieranno al tentativo successivo).
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
          return false;
        }
        // 5xx / errori di rete: max 2 retry (3 tentativi totali).
        return failureCount < 2;
      },
    },
  },
});
