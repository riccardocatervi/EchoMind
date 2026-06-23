/**
 * Cancello (gatekeeper) delle rotte autenticate.
 *
 * Si inserisce come layout route SENZA path nel router (router.tsx):
 *   { element: <ProtectedRoute />, children: [...rotte protette...] }
 * React Router chiama <Outlet /> per renderizzare i figli se autenticati.
 *
 * Tre stati possibili:
 *   "loading"         → la sessione si sta idratando da localStorage (è quasi
 *                       istantaneo, ma serve per evitare un flash di /login).
 *                       Mostra uno spinner centrato a schermo intero.
 *   "unauthenticated" → reindirizza alla "/" (landing) con `replace`: così il
 *                       tasto "indietro" non riporta alla pagina protetta ma
 *                       alla pagina precedente alla navigazione.
 *   "authenticated"   → rende i figli tramite <Outlet />.
 *
 * Perché redirige a "/" e non a "/login":
 *   L'utente non autenticato vede prima la landing con i CTA "Accedi/Registrati"
 *   invece di finire direttamente sul form di login. Migliore UX e coerente con
 *   il flusso di logout (signOut → "/" → l'utente può scegliere se rifare login).
 *
 * Perché legge `status` da Zustand (useAuthStore) e non da Supabase:
 *   Lo status in Zustand è già sincronizzato da AuthProvider con Supabase.
 *   Leggere direttamente da Supabase richiederebbe una chiamata async che
 *   causerebbe un flash di "unauthenticated" prima della risposta.
 */
import { Loader2 } from "lucide-react";
import { Navigate, Outlet } from "react-router-dom";

import { useAuthStore } from "@/features/auth/store/authStore";

/**
 * Cancello delle rotte autenticate:
 *  - loading: la sessione si sta idratando -> spinner (evita un flash di /login);
 *  - unauthenticated: redirect a /login;
 *  - authenticated: rende le rotte figlie via <Outlet/>.
 */
export function ProtectedRoute() {
  const status = useAuthStore((state) => state.status);

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" aria-label="Caricamento" />
      </div>
    );
  }

  if (status === "unauthenticated") {
    // Redirige alla landing page (non a /login): cosi' il logout torna alla home
    // e un visitatore non autenticato vede i CTA "Accedi / Registrati" prima di
    // essere forzato nel form di login. Nessuna race condition con signOut().
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
