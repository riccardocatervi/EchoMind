/**
 * Query Key Factory per il summary.
 *
 * Il summary è 1:1 con il documento (come il transcript).
 * `["summary", documentId]`: invalidato da DocumentDetailPage dopo una
 * ri-estrazione riuscita (`invalidateQueries({ queryKey: summaryKeys.detail(documentId) })`).
 */
export const summaryKeys = {
  detail: (id: string) => ["summary", id] as const,
};
