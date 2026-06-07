import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { Toaster } from "sonner";

import App from "@/app/App";
import { AuthProvider } from "@/features/auth/components/AuthProvider";
import { queryClient } from "@/shared/api/queryClient";
// Inizializza i18next (react-i18next) prima del render dell'albero React.
// DEVE essere importato qui (effetto collaterale) perche' useTranslation()
// si aspetta che i18n sia gia' configurato al momento del primo render.
import "@/shared/i18n";
import "@/index.css";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root non trovato in index.html");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <App />
      </AuthProvider>
      <Toaster richColors position="top-right" theme="dark" />
    </QueryClientProvider>
  </React.StrictMode>,
);
