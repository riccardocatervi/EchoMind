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
  status: "loading",
  setSession: (session) => set({ session, status: session ? "authenticated" : "unauthenticated" }),
}));
