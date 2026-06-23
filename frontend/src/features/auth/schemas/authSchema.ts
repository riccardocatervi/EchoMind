/**
 * Schema Zod per i form di autenticazione.
 *
 * Perché validare con Zod e non con attributi HTML (`required`, `type="email"`):
 *   La validazione HTML nativa è bypassabile (fetch API, strumenti dev).
 *   Zod garantisce la validazione anche se si chiama `signInWithPassword`
 *   programmaticamente (es. da test). I messaggi di errore Zod sono
 *   personalizzabili e localizzabili (le stringhe sono in italiano direttamente
 *   nello schema perché i form auth non usano i18n per semplicità).
 *
 * `credentialsSchema`:
 *   Usato da LoginPage. Validazione client-side PRIMA della chiamata Supabase:
 *   riduce i round-trip per errori di formato ovvi (email senza @, password vuota).
 *
 * `signupSchema`:
 *   Usato da SignupPage. `firstName` e `lastName` vengono salvati in
 *   `user.user_metadata` di Supabase come `first_name` e `last_name`.
 *   Non vengono inviati al nostro backend direttamente: il profilo viene
 *   creato dal trigger `on_auth_user_created` in Supabase (o JIT in `get_document_service`).
 *
 * Password minima 6 caratteri:
 *   Limite minimo di Supabase Auth. Imposto anche client-side per consistenza
 *   (il backend ritorna un errore generico "Password should be at least 6 chars"
 *   se si supera la validazione client ma non quella Supabase).
 */
import { z } from "zod";

/** Schema per il form di login (email + password). */
export const credentialsSchema = z.object({
  email: z.string().email("Email non valida"),
  password: z.string().min(6, "La password deve avere almeno 6 caratteri"),
});
export type Credentials = z.infer<typeof credentialsSchema>;

/**
 * Schema per il form di registrazione.
 * Nome e cognome vengono salvati in user_metadata di Supabase
 * come `first_name` e `last_name`.
 */
export const signupSchema = z.object({
  firstName: z.string().min(1, "Il nome è obbligatorio"),
  lastName: z.string().min(1, "Il cognome è obbligatorio"),
  email: z.string().email("Email non valida"),
  password: z.string().min(6, "La password deve avere almeno 6 caratteri"),
});
export type SignupData = z.infer<typeof signupSchema>;
