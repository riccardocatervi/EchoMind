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
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
