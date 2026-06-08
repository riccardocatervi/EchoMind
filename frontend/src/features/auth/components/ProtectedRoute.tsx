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
