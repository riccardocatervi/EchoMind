import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { LoginPage } from "@/features/auth/LoginPage";
import { ProtectedRoute } from "@/features/auth/ProtectedRoute";
import { SignupPage } from "@/features/auth/SignupPage";
import { Home } from "@/routes/Home";

/**
 * Albero delle rotte:
 *   /login, /signup        -> pubbliche
 *   ProtectedRoute (gate)  -> AppShell (layout) -> rotte autenticate
 *   *                      -> redirect a "/"
 *
 * CP4 aggiungera' qui le rotte di dettaglio documento e del grafo.
 */
export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [{ index: true, element: <Home /> }],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
