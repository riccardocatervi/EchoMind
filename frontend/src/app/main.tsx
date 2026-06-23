/**
 * Punto di ingresso dell'applicazione React.
 *
 * Ordine dei provider nel render tree (dall'esterno verso l'interno):
 *
 *   React.StrictMode
 *     └── QueryClientProvider   ← TanStack Query: cache HTTP condivisa con tutta l'app
 *           └── AuthProvider    ← deve stare DENTRO QueryClientProvider perché alcune
 *           |                     mutation di auth (es. profilo) usano useMutation
 *           └── App             ← router + pagine
 *               └── Toaster     ← notifiche toast (Sonner): a livello root per essere
 *                                 visibili su tutte le pagine senza dipendenze dai route
 *
 * Perché `React.StrictMode`:
 *   In sviluppo monta + smonta + rimonta ogni componente per rilevare side-effect
 *   non-idempotenti (useEffect chiamati due volte → se il tuo effetto rompe, hai un bug).
 *   In produzione è disattivo automaticamente (zero overhead).
 *
 * Perché `QueryClientProvider` è al top:
 *   Il `queryClient` (cache) deve essere un singleton di sessione browser. Tutti i
 *   componenti figli che chiamano `useQuery` o `useMutation` attingono allo stesso
 *   contesto React via `useContext`. Senza il provider → runtime error "No QueryClient set".
 *
 * Perché `AuthProvider` è dentro (non fuori) `QueryClientProvider`:
 *   AuthProvider chiama `supabase.auth.getSession()` e `onAuthStateChange`. Queste
 *   callback potrebbero in futuro invocare mutation Query; tenerlo dentro evita un
 *   problema di ordine di inizializzazione.
 *
 * Perché i18next viene importato PRIMA del render (`import "@/shared/i18n"`):
 *   L'import ha un effetto collaterale: chiama `i18next.init()`. Se arrivasse dopo il
 *   render, il primo ciclo di `useTranslation()` troverebbe i18n non inizializzato e
 *   mostrerebbe le chiavi di traduzione grezze (es. "docs.title") invece del testo.
 */
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
  // Fail-fast: se manca #root (errore in index.html), l'app non può montarsi.
  // Un throw sincrono blocca il render e mostra subito l'errore in console.
  throw new Error("Root element #root non trovato in index.html");
}

// `createRoot` è l'API React 18 (concurrent mode). Rispetto a `ReactDOM.render`
// (React 17, legacy mode) abilita: Suspense boundaries, transitions, streaming SSR.
ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <App />
      </AuthProvider>
      {/*
       * Toaster (Sonner): fuori da AppShell ma dentro QueryClientProvider così
       * le notifiche sono visibili su TUTTE le rotte (anche /login, /signup).
       * `richColors`: usa i colori semantici (verde/rosso/giallo) per i tipi di toast.
       * `position="top-right"`: convenzione UX standard, non interferisce con la UI.
       */}
      <Toaster richColors position="top-right" theme="dark" />
    </QueryClientProvider>
  </React.StrictMode>,
);
