/**
 * AuthProvider — idrata la sessione Supabase e sincronizza il cambio di stato auth.
 *
 * Responsabilità:
 *   1. Al mount: legge la sessione già in localStorage (Supabase la persiste
 *      automaticamente) e la riversa nello store Zustand → ProtectedRoute sa
 *      subito se l'utente è loggato senza aspettare un round-trip di rete.
 *   2. Si iscrive a `onAuthStateChange`: ogni evento auth (login, logout,
 *      token refresh, scadenza) aggiorna lo store → la UI reagisce in real-time.
 *
 * Perché questo pattern (AuthProvider + Zustand) invece di React Query:
 *   - La sessione auth ha semantica DIVERSA dai dati di dominio: non è "fresca/stale",
 *     non va re-fetchata su window focus, non ha un TTL di cache classico.
 *   - Supabase gestisce autonomamente il refresh token (`autoRefreshToken: true`):
 *     non serve polling da parte nostra.
 *   - Lo store Zustand è letto in modo sincrono (`getState().session?.access_token`)
 *     dall'interceptor axios: React Query (async) non si presta a questo uso.
 *
 * Perché il wiring `setAccessTokenGetter` / `setUnauthorizedHandler` avviene a
 * module load time (fuori dalla funzione componente):
 *   - Il modulo viene importato UNA sola volta: il getter è registrato prima che
 *     qualsiasi componente faccia fetch, eliminando la race condition in cui
 *     una query parte prima che il provider sia montato.
 *   - Registrarlo in un `useEffect` avrebbe introdotto un frame in cui l'interceptor
 *     non ha ancora il getter e il token sarebbe null anche se l'utente è loggato.
 *
 * Perché la guardia `active`:
 *   In React StrictMode il componente viene montato → smontato → rimontato.
 *   Senza guardia, la callback asincrona `getSession().then(...)` potrebbe
 *   aggiornare lo stato su un componente già smontato (primo ciclo StrictMode),
 *   causando il warning "Can't perform a React state update on an unmounted component".
 *   `active = false` nel cleanup annulla l'aggiornamento del primo ciclo.
 */
import { useEffect, type ReactNode } from "react";

import { setAccessTokenGetter, setUnauthorizedHandler } from "@/shared/api/axios";
import { queryClient } from "@/shared/api/queryClient";
import { supabase } from "@/features/auth/lib/supabaseClient";
import { useAuthStore } from "@/features/auth/store/authStore";

// Wiring del data layer all'auth, eseguito una volta all'import del modulo
// (prima che qualsiasi componente monti, evitando race con le query).
//  - l'apiClient legge il token LIVE dalla sessione corrente nello store;
//  - su 401 sloggiamo: onAuthStateChange aggiornera' lo store e ProtectedRoute
//    redirigera' al login.
setAccessTokenGetter(() => useAuthStore.getState().session?.access_token ?? null);
setUnauthorizedHandler(() => {
  // `void`: ignoriamo la promise restituita da signOut (non aspettiamo il completamento).
  // Il redirect al login viene gestito da ProtectedRoute che osserva lo store.
  void supabase.auth.signOut();
});

/**
 * Idrata la sessione all'avvio e si sottoscrive ai cambi di stato auth di
 * Supabase, riversandoli nello store. Va montato sopra il router.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  // Selector granulare: si sottoscrive SOLO a `setSession`, non all'intero stato.
  // Evita re-render inutili di AuthProvider quando cambiano altre parti dello store.
  const setSession = useAuthStore((state) => state.setSession);

  useEffect(() => {
    // Guardia per React StrictMode: evita aggiornamenti su componente smontato
    // nel primo ciclo del double-mount.
    let active = true;

    // 1. Idratazione sincrona: Supabase recupera la sessione da localStorage.
    //    Questo è un'operazione quasi istantanea (nessun network round-trip).
    void supabase.auth.getSession().then(({ data }) => {
      if (active) setSession(data.session);
    });

    // 2. Sottoscrizione ai cambi di stato: login, logout, token refresh.
    //    `onAuthStateChange` è un listener permanente che Supabase chiama ogni volta
    //    che la sessione cambia (es. token scaduto e rinnovato automaticamente).
    const { data } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_OUT") queryClient.clear();
      setSession(session);
    });

    // Cleanup al dismount: annulla il doppio-aggiornamento StrictMode e
    // rimuove il listener per evitare memory leak.
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, [setSession]);

  return <>{children}</>;
}
