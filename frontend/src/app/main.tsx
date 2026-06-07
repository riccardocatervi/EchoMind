import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { Toaster } from "sonner";

import App from "@/app/App";
import { AuthProvider } from "@/features/auth/components/AuthProvider";
import { queryClient } from "@/shared/api/queryClient";
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
