/**
 * Hook di comodo che combina lo stato auth reattivo (Zustand) con le azioni
 * Supabase (signIn, signUp, signOut).
 *
 * Perché leggere da Zustand e non da Supabase direttamente:
 *   `supabase.auth.getUser()` è async e richiederebbe un useEffect.
 *   Zustand è sincrono: `useAuthStore((s) => s.session)` ritorna subito il
 *   valore corrente, già sincronizzato da AuthProvider tramite `onAuthStateChange`.
 *
 * Le azioni (signIn/signUp/signOut) delegano a Supabase e ritornano `{ data, error }`:
 *   La UI (LoginPage, SignupPage) decide come gestire successo/errore.
 *   L'aggiornamento dello store avviene automaticamente tramite `onAuthStateChange`
 *   in AuthProvider → non serve chiamare `setSession` manualmente qui.
 *
 * `user: session?.user ?? null`:
 *   Shortcut: evita che ogni componente faccia `session?.user` inline.
 */
import { supabase } from "@/features/auth/lib/supabaseClient";
import { useAuthStore } from "@/features/auth/store/authStore";

/**
 * Hook di comodo per l'auth: espone la sessione/stato (reattivi, dallo store) e
 * le azioni Supabase (login/signup/logout). Le azioni ritornano l'oggetto
 * { data, error } di Supabase: la UI decide come mostrarne l'esito.
 */
export function useAuth() {
  const session = useAuthStore((state) => state.session);
  const status = useAuthStore((state) => state.status);

  return {
    session,
    status,
    user: session?.user ?? null,
    signInWithPassword: (email: string, password: string) =>
      supabase.auth.signInWithPassword({ email, password }),
    /**
     * Registrazione. `userMetadata` (opzionale) viene salvato in
     * `user.user_metadata` -- usa le chiavi `first_name` e `last_name`.
     */
    signUp: (email: string, password: string, userMetadata?: Record<string, string>) =>
      supabase.auth.signUp({
        email,
        password,
        options: userMetadata ? { data: userMetadata } : undefined,
      }),
    signOut: () => supabase.auth.signOut(),
  };
}
