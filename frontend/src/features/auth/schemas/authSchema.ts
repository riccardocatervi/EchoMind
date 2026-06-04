import { z } from "zod";

/** Schema dei form di login/signup. Validazione lato client prima di Supabase. */
export const credentialsSchema = z.object({
  email: z.string().email("Email non valida"),
  password: z.string().min(6, "La password deve avere almeno 6 caratteri"),
});
export type Credentials = z.infer<typeof credentialsSchema>;
