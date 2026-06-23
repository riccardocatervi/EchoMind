/**
 * Configurazione dell'albero di rotte con React Router v6 (createBrowserRouter).
 *
 * Struttura gerarchica (layout routes):
 *
 *   /                      → LandingPage (pubblica)
 *   /login, /signup, ...   → pagine auth (pubbliche)
 *   ProtectedRoute          → guardia: reindirizza al login se non autenticato
 *     AppShell              → layout autenticato (navbar, sidebar, background)
 *       /documents          → lista documenti
 *       /documents/:id      → dettaglio documento
 *       /documents/:id/graph → visualizzatore grafo (lazy-loaded)
 *       /profile            → impostazioni utente
 *   *                       → redirect a "/" (catch-all)
 *
 * Perché `createBrowserRouter` (e non `<BrowserRouter>`):
 *   La versione "data router" è il percorso raccomandato da React Router 6.4+.
 *   Abilitano loader/action nelle rotte; nella nostra app non li usiamo (TanStack
 *   Query gestisce il data fetching), ma il data router è compatibile e prepara
 *   la codebase all'evoluzione.
 *
 * Perché il layout route con ProtectedRoute + AppShell è "pathless":
 *   Una route senza `path` nel data router agisce come layout puro: non contribuisce
 *   al matching del path (ci pensa il figlio), ma avvolge i figli nel suo elemento.
 *   Così ProtectedRoute protegge TUTTE le rotte figlie senza duplicare la guardia.
 *
 * Perché `lazy()` + `Suspense` su GraphPage:
 *   Il grafo interattivo usa React Flow + ELK (librerie pesanti, ~500 KB gzipped).
 *   `lazy()` spezza il bundle: quelle dipendenze vengono scaricate SOLO quando
 *   l'utente naviga su /documents/:id/graph, non al caricamento iniziale.
 *   `Suspense` mostra il fallback (spinner) durante il download del chunk.
 *
 * Perché `<Navigate to="/" replace>` come catch-all:
 *   `replace` sostituisce l'entry nella history invece di aggiungerne una nuova,
 *   così il pulsante "indietro" del browser non torna sulla rotta 404 inesistente.
 *
 * Perché NON c'è una index route dentro ProtectedRoute/AppShell:
 *   "/" è già gestita da LandingPage (che fa il redirect a /documents se l'utente
 *   è autenticato). Un index route dentro il layout pathless "rivendica" "/" e
 *   batte LandingPage in React Router v6, causando un redirect infinito.
 */
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

// Lazy import di GraphPage: React Flow + ELK sono pesanti.
// Il chunk viene scaricato solo quando l'utente naviga su /graph.
const GraphPage = lazy(() => import("@/features/graph/components/GraphPage"));

// Fallback mostrato durante il download lazy del chunk GraphPage.
const graphFallback = (
  <div className="flex h-[60vh] items-center justify-center">
    <Loader2 className="size-6 animate-spin text-muted-foreground" aria-label="Caricamento" />
  </div>
);

export const router = createBrowserRouter([
  // --- Rotte pubbliche ---
  { path: "/", element: <LandingPage /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },

  // --- Rotte protette (layout annidata) ---
  {
    // ProtectedRoute senza `path`: agisce da guardia + layout, non da segmento URL.
    element: <ProtectedRoute />,
    children: [
      {
        // AppShell senza `path`: agisce da layout (navbar/sidebar/sfondo) per i figli.
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
            // Suspense: mostra graphFallback mentre il chunk lazy viene scaricato.
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

  // Catch-all: rotte non riconosciute → redirect a /. `replace` evita che
  // "indietro" nel browser torni sulla rotta inesistente.
  { path: "*", element: <Navigate to="/" replace /> },
]);
