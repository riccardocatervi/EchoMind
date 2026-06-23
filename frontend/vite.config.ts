/**
 * Configurazione Vite — build tool + dev server.
 *
 * Perché Vite e non Webpack/CRA:
 *   Vite usa esbuild (Go) per il transpiling durante lo sviluppo: il dev server
 *   parte in <300ms e ogni modifica è visibile in <100ms (vs 5-30s di Webpack).
 *   In produzione usa Rollup (ottimizzato per tree-shaking e code-splitting).
 *
 * `@vitejs/plugin-react`:
 *   Plugin ufficiale per React: HMR (Hot Module Replacement) rapido tramite
 *   React Fast Refresh, trasformazione JSX via Babel (o SWC se configurato).
 *
 * `resolve.alias["@"]`:
 *   Path alias "@/..." → "src/...". Evita import relativi lunghi ("../../../../shared").
 *   `fileURLToPath(new URL("./src", import.meta.url))` è il modo corretto per
 *   costruire percorsi assoluti in ES modules (import.meta.url è l'URL del file corrente).
 *   Coerente con `paths` in tsconfig.json e `@` in components.json (shadcn/ui).
 *
 * `server.strictPort: true`:
 *   Se la porta 5173 è già occupata, Vite lancia un errore invece di usarne un'altra.
 *   Questo evita che l'ambiente Docker esponga il frontend su una porta diversa da
 *   quella configurata nei CORS del backend.
 *
 * `test.environment: "jsdom"`:
 *   Vitest (test runner integrato in Vite) usa jsdom per simulare il DOM del browser
 *   nei test unitari. Senza jsdom, document/window non esisterebbero nei test Node.js.
 *
 * `test.setupFiles: ["./src/test/setup.ts"]`:
 *   File di setup eseguito prima di ogni test: importa `@testing-library/jest-dom`
 *   per i matcher custom (es. `expect(el).toBeInTheDocument()`).
 *
 * `test.css: false`:
 *   Non elabora i file CSS durante i test (non necessario per i test di comportamento).
 *   Riduce i tempi di setup dei test.
 *
 * `test.restoreMocks: true`:
 *   Ripristina automaticamente tutti i mock (vi.fn, vi.spyOn) dopo ogni test.
 *   Evita che i mock di un test "inquinino" i test successivi.
 */
import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Path alias "@/..." → "src/..." (coerente con tsconfig.json e components.json).
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // strictPort: errore se 5173 è occupata (invece di usarne un'altra).
    strictPort: true,
  },
  test: {
    // jsdom: simula il DOM del browser nei test Node.js (necessario per React Testing Library).
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Non elaborare CSS nei test (non necessario, riduce il tempo di setup).
    css: false,
    // Ripristina i mock dopo ogni test per evitare contaminazione tra test.
    restoreMocks: true,
  },
});
