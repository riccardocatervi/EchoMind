import { useEffect, type ReactNode } from "react";

import { setAccessTokenGetter, setUnauthorizedHandler } from "@/lib/apiClient";
import { supabase } from "@/lib/supabaseClient";
import { useAuthStore } from "@/store/authStore";

// Wiring del data layer all'auth, eseguito una volta all'import del modulo
// (prima che qualsiasi componente monti, evitando race con le query).
//  - l'apiClient legge il token LIVE dalla sessione corrente nello store;
//  - su 401 sloggiamo: onAuthStateChange aggiornera' lo store e ProtectedRoute
//    redirigera' al login.
setAccessTokenGetter(() => useAuthStore.getState().session?.access_token ?? null);
setUnauthorizedHandler(() => {
  void supabase.auth.signOut();
});

/**
 * Idrata la sessione all'avvio e si sottoscrive ai cambi di stato auth di
 * Supabase, riversandoli nello store. Va montato sopra il router.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const setSession = useAuthStore((state) => state.setSession);

  useEffect(() => {
    let active = true;

    void supabase.auth.getSession().then(({ data }) => {
      if (active) setSession(data.session);
    });

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, [setSession]);

  return <>{children}</>;
}
