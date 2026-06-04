import { lazy, Suspense } from "react";
import { Loader2 } from "lucide-react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "@/app/AppShell";
import { LoginPage } from "@/features/auth/components/LoginPage";
import { ProtectedRoute } from "@/features/auth/components/ProtectedRoute";
import { SignupPage } from "@/features/auth/components/SignupPage";
import { DocumentDetailPage } from "@/features/documents/components/DocumentDetailPage";
import { DocumentsPage } from "@/features/documents/components/DocumentsPage";

/**
 * Albero delle rotte:
 *   /login, /signup        -> pubbliche
 *   ProtectedRoute (gate)  -> AppShell (layout) -> rotte autenticate
 *   *                      -> redirect a "/"
 */
// Code-splitting: React Flow + Elk (pesanti) vivono in un chunk separato,
// caricato solo quando si apre la rotta del grafo.
const GraphPage = lazy(() => import("@/features/graph/components/GraphPage"));

const graphFallback = (
  <div className="flex h-[60vh] items-center justify-center">
    <Loader2 className="size-6 animate-spin text-muted-foreground" aria-label="Caricamento" />
  </div>
);

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          { index: true, element: <DocumentsPage /> },
          { path: "documents/:documentId", element: <DocumentDetailPage /> },
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
