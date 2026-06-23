/**
 * Query Key Factory per il grafo di conoscenza.
 *
 * Solo `detail`: il grafo è sempre per-documento (nessuna lista globale).
 * `["graph", documentId]` è il prefisso sufficiente per identificare e
 * invalidare la cache del grafo dopo una ri-estrazione (vedi DocumentDetailPage:
 * `queryClient.invalidateQueries({ queryKey: graphKeys.detail(documentId) })`).
 */
export const graphKeys = {
  detail: (id: string) => ["graph", id] as const,
};
