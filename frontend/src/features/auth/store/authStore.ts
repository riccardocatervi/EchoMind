/**
 * Store globale della sessione auth (Zustand).
 *
 * Perché Zustand e non React Context:
 *   - React Context provoca re-render a cascata su TUTTI i figli del provider ogni
 *     volta che il valore cambia. Zustand usa selector granulari: un componente
 *     re-renderizza SOLO se il pezzo di stato che osserva cambia.
 *   - `useAuthStore.getState()` permette di leggere lo stato SINCRONO e FUORI da un
 *     componente (es. nell'interceptor axios che vuole il token prima di ogni fetch).
 *     Con React Context questo sarebbe impossibile senza esporre un ref.
 *
 * Perché Zustand e non TanStack Query:
 *   - Lo stato auth (sessione, token, status) non è un "dato server" con un TTL di
 *     cache: è stato applicativo locale gestito da Supabase.
 *   - Non va mai "invalidato" esplicitamente: è Supabase che chiama il callback
 *     `onAuthStateChange` ogni volta che la sessione cambia.
 *   - L'interceptor axios ha bisogno di `getState().session?.access_token` in modo
 *     sincrono: lo store Zustand lo permette; Query no (le query sono async).
 *
 * Perché `status: "loading"` come stato iniziale:
 *   Prima che AuthProvider chiami `getSession()`, non sappiamo se l'utente è loggato
 *   o no. "loading" permette a ProtectedRoute di mostrare uno spinner invece di
 *   reindirizzare prematuramente al login (evita un flash of unauthenticated content).
 *
 * Struttura `setSession`:
 *   Unico setter: converte la sessione (Session | null) nel campo `status` derivato.
 *   Centralizzare la transizione evita state incoerente tra `session` e `status`
 *   (es. session=null + status="authenticated").
 */
import type { Session } from "@supabase/supabase-js";
import { create } from "zustand";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  session: Session | null;
  status: AuthStatus;
  /** Aggiorna la sessione (chiamato da AuthProvider su getSession/onAuthStateChange). */
  setSession: (session: Session | null) => void;
}

/**
 * Store globale della sessione auth (Zustand). E' l'unico pezzo di stato auth
 * "client-side"; i dati di dominio restano in TanStack Query. La sorgente di
 * verita' resta Supabase: qui ne teniamo solo uno specchio reattivo per la UI.
 */
export const useAuthStore = create<AuthState>((set) => ({
  session: null,
  // "loading" iniziale: ProtectedRoute aspetta fino a quando AuthProvider
  // ha idratato la sessione (quasi istantaneo, da localStorage).
  status: "loading",
  // `set` di Zustand è un merge parziale (come setState di React):
  // aggiorna solo i campi specificati, lasciando intatti gli altri.
  setSession: (session) => set({ session, status: session ? "authenticated" : "unauthenticated" }),
}));
