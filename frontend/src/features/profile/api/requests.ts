/**
 * Funzioni HTTP per il profilo utente.
 *
 * `getMyProfile`:
 *   GET /profiles/me → ritorna il profilo dell'utente autenticato.
 *   Risponde 404 se il profilo non è ancora stato creato (primo accesso
 *   prima di qualsiasi operazione che trigga la JIT provisioning).
 *   In pratica il profilo esiste sempre: viene creato da `get_document_service`
 *   al primo accesso autenticato (JIT = Just-In-Time provisioning).
 *
 * `updateMyProfile`:
 *   PATCH /profiles/me → semantica parziale: solo i campi forniti vengono
 *   aggiornati. Usato da LanguageSection per aggiornare `preferred_language`
 *   senza sovrascrivere `display_name`.
 *   La risposta è il profilo aggiornato: viene usata da LanguageSection per
 *   fare `setQueryData` direttamente sulla cache (evita un GET ridondante).
 */
import { api } from "@/shared/api/axios";
import {
  profileReadSchema,
  type ProfileRead,
  type ProfileUpdate,
} from "@/features/profile/schemas/profile";

/** Recupera il profilo dell'utente corrente. */
export async function getMyProfile(): Promise<ProfileRead> {
  const { data } = await api.get("/profiles/me");
  return profileReadSchema.parse(data);
}

/** Aggiorna parzialmente il profilo (PATCH). Ritorna il profilo aggiornato. */
export async function updateMyProfile(payload: ProfileUpdate): Promise<ProfileRead> {
  const { data } = await api.patch("/profiles/me", payload);
  return profileReadSchema.parse(data);
}
