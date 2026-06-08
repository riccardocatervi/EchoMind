import { z } from "zod";

/** Schema per il form di login (email + password). */
export const credentialsSchema = z.object({
  email: z.string().email("Email non valida"),
  password: z.string().min(6, "La password deve avere almeno 6 caratteri"),
});
export type Credentials = z.infer<typeof credentialsSchema>;

/**
 * Schema per il form di registrazione.
 * Nome e cognome sono salvati in user_metadata di Supabase
 * come `first_name` e `last_name`.
 */
export const signupSchema = z.object({
  firstName: z.string().min(1, "Il nome è obbligatorio"),
  lastName: z.string().min(1, "Il cognome è obbligatorio"),
  email: z.string().email("Email non valida"),
  password: z.string().min(6, "La password deve avere almeno 6 caratteri"),
});
export type SignupData = z.infer<typeof signupSchema>;
