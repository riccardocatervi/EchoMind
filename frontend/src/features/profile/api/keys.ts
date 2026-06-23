/**
 * Query Key Factory per il profilo utente.
 *
 * `me`: chiave singleton — c'è sempre un solo profilo (quello dell'utente corrente).
 * Non c'è `detail(id)`: l'utente accede SOLO al proprio profilo (GET /profiles/me).
 *
 * `queryClient.setQueryData<ProfileRead>(profileKeys.me, updated)` in LanguageSection:
 *   Aggiorna direttamente la cache dopo PATCH /profiles/me, senza invalidare e
 *   ri-fetchare. Ottimizzazione: evita un round-trip GET inutile dopo l'update.
 */
export const profileKeys = {
  me: ["profile", "me"] as const,
};
