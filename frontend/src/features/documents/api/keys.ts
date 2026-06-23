/**
 * Query Key Factory per TanStack Query — documenti.
 *
 * Perché usare una factory invece di stringhe sparse:
 *   TanStack Query identifica ogni cache entry tramite la sua `queryKey` (array).
 *   Se le chiavi fossero scritte inline ("documents", "list", ...) in ogni file,
 *   un errore di battitura causerebbe cache miss silenzioso (dati non condivisi
 *   tra componenti) o invalidazioni mancanti (la lista non si aggiorna dopo un delete).
 *
 *   La factory centralizza le chiavi e le rende derivate l'una dall'altra:
 *     documentKeys.all          = ["documents"]
 *     documentKeys.list(params) = ["documents", "list", { limit: 10, offset: 0 }]
 *     documentKeys.detail(id)   = ["documents", "detail", "<uuid>"]
 *
 *   `invalidateQueries({ queryKey: documentKeys.all })` invalida TUTTE le query
 *   che iniziano con ["documents"] (list + detail + qualsiasi futura) perché
 *   TanStack Query fa matching per prefisso. Se si usasse `documentKeys.list(...)`
 *   si invaliderebbero solo le liste, non i dettagli. Con `all` si invalida tutto.
 *
 * `as const` garantisce che TypeScript veda tuple letterali, non `string[]`:
 *   evita cast accidentali e permette di tipare useQuery correttamente.
 */
export const documentKeys = {
  // Radice: prefisso per TUTTE le query sui documenti (usato in invalidateAll).
  all: ["documents"] as const,
  // Lista paginata: il parametro { limit, offset } fa parte della chiave →
  // pagine diverse hanno cache entry diverse (nessuna collisione).
  list: (params: { limit?: number; offset?: number }) =>
    [...documentKeys.all, "list", params] as const,
  // Dettaglio singolo documento: identificato dall'UUID.
  detail: (id: string) => [...documentKeys.all, "detail", id] as const,
};
