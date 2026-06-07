import { lazy, Suspense } from "react";
import { Loader2 } from "lucide-react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "@/app/AppShell";
import { ForgotPasswordPage } from "@/features/auth/components/ForgotPasswordPage";
import { LoginPage } from "@/features/auth/components/LoginPage";
import { ProtectedRoute } from "@/features/auth/components/ProtectedRoute";
import { ResetPasswordPage } from "@/features/auth/components/ResetPasswordPage";
import { SignupPage } from "@/features/auth/components/SignupPage";
import { LandingPage } from "@/features/landing/components/LandingPage";
import { DocumentDetailPage } from "@/features/documents/components/DocumentDetailPage";
import { DocumentsPage } from "@/features/documents/components/DocumentsPage";
import { ProfilePage } from "@/features/profile/components/ProfilePage";

/**
 * Albero delle rotte:
 *   /                  -> LandingPage (pubblica, redirige a /documents se gia' loggati)
 *   /login, /signup    -> pagine di autenticazione (pubbliche)
 *   ProtectedRoute     -> AppShell (layout autenticato)
 *     /documents       -> dashboard documenti
 *     /documents/:id   -> dettaglio documento
 *     /documents/:id/graph -> grafo interattivo
 *   *                  -> redirect a "/"
 */
const GraphPage = lazy(() => import("@/features/graph/components/GraphPage"));

const graphFallback = (
  <div className="flex h-[60vh] items-center justify-center">
    <Loader2 className="size-6 animate-spin text-muted-foreground" aria-label="Caricamento" />
  </div>
);

export const router = createBrowserRouter([
  { path: "/", element: <LandingPage /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          // NON c'e' index: "/" e' gia' gestito da LandingPage (che redirige a
          // /documents se l'utente e' gia' autenticato). Un index route qui dentro
          // una layout pathless rivendica "/" e batte LandingPage in React Router v6.
          { path: "documents", element: <DocumentsPage /> },
          { path: "documents/:documentId", element: <DocumentDetailPage /> },
          { path: "profile", element: <ProfilePage /> },
          {
            path: "documents/:documentId/graph",
            element: (
              <Suspense fallback={graphFallback}>
                <GraphPage />
              </Suspense>
            ),
          },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
