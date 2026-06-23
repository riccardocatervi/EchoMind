/**
 * Hook per il profilo dell'utente corrente.
 *
 * Nessun `enabled` condizionale: il profilo è sempre disponibile per gli utenti
 * autenticati (creato al primo accesso in `get_document_service` o dal trigger
 * Supabase `on_auth_user_created`).
 *
 * Nessun polling: il profilo cambia solo quando l'utente lo modifica
 * esplicitamente in ProfilePage. Le modifiche aggiornano la cache direttamente
 * (`setQueryData`) o tramite invalidazione selettiva.
 */
import { useQuery } from "@tanstack/react-query";

import { profileKeys } from "@/features/profile/api/keys";
import { getMyProfile } from "@/features/profile/api/requests";

/** Profilo dell'utente corrente (GET /profiles/me). */
export function useProfile() {
  return useQuery({
    queryKey: profileKeys.me,
    queryFn: getMyProfile,
  });
}
