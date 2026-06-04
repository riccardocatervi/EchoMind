import { supabase } from "@/lib/supabaseClient";
import { useAuthStore } from "@/store/authStore";

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
    signUp: (email: string, password: string) => supabase.auth.signUp({ email, password }),
    signOut: () => supabase.auth.signOut(),
  };
}
