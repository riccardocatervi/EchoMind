/**
 * Client HTTP condiviso (axios) + sistema di interceptor.
 *
 * Architettura del modulo:
 *
 *   api (istanza axios)
 *     ├── interceptors.request  → allega Bearer token + Accept-Language
 *     └── interceptors.response → normalizza errori in ApiError tipizzata
 *
 * Perché axios e non fetch nativo:
 *   - Interceptor globali: il Bearer token viene aggiunto UNA SOLA VOLTA qui,
 *     non in ogni singola richiesta. Con fetch nativo, ogni chiamata dovrebbe
 *     gestire l'auth manualmente.
 *   - `axios.isAxiosError()` permette di distinguere errori HTTP da errori di rete.
 *   - Timeout, retry, cancellazione sono integrati o facilmente configurabili.
 *
 * Pattern di disaccoppiamento (setAccessTokenGetter / setUnauthorizedHandler):
 *   Questo modulo (`axios.ts`) è nello `shared` layer, che NON deve importare nulla
 *   da `features/auth` (dipendenza circolare). Il problema: per allegare il Bearer
 *   token serve il Supabase token, che vive in `features/auth/store/authStore`.
 *   Soluzione: questo modulo espone due "slot" (`accessTokenGetter`,
 *   `unauthorizedHandler`) che restano null finché `AuthProvider` li riempie a
 *   module load time con `setAccessTokenGetter(...)`. Così l'auth "si inietta" nel
 *   data layer senza che il data layer la importi direttamente.
 *
 * Perché il getter è async (TokenGetter = () => string | null | Promise<string | null>):
 *   In futuro, se il token non fosse già in localStorage ma richiedesse un round-trip
 *   (es. auth con cookie HttpOnly), il getter potrebbe essere async. Ora è sincrono
 *   (`getState().session?.access_token`), ma l'interfaccia è già pronta.
 *
 * Perché l'interceptor aggiunge anche Accept-Language:
 *   Il backend usa Accept-Language nell'endpoint POST /documents/:id/ask per decidere
 *   la lingua della risposta RAG (it/en). Aggiungerlo qui garantisce che TUTTE le
 *   richieste portino la lingua corrente dell'interfaccia senza doverlo fare a mano.
 *
 * ApiError:
 *   Classe custom che estende Error con `status` (HTTP code) e `code` (machine-
 *   readable dal backend, es. "document_not_found"). Permette a TanStack Query di
 *   decidere se fare retry (5xx → sì; 4xx → no) e alle UI di mostrare messaggi
 *   specifici basati sul `code` invece del solo status code HTTP.
 */
import axios from "axios";

import i18n from "@/shared/i18n";
import { errorResponseSchema } from "@/shared/schemas/common";

const baseURL = `${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}/api/v1`;

/** Errore applicativo con lo status HTTP e il `code` machine-readable del backend. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string | null,
    message: string,
  ) {
    super(message);
    // Necessario in transpiling TypeScript -> ES5: senza, `instanceof ApiError`
    // fallisce perché il prototipo non viene impostato correttamente.
    this.name = "ApiError";
  }
}

/** Type guard: permette di scrivere `if (isApiError(e)) e.status` in modo type-safe. */
export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

// --- Slot iniettati dall'auth (feature auth) ----------------------------------
// Inizialmente null: nessun token, nessun handler. AuthProvider li riempie
// a module load time (vedi AuthProvider.tsx).
type TokenGetter = () => string | null | Promise<string | null>;

let accessTokenGetter: TokenGetter = () => null;
let unauthorizedHandler: (() => void) | null = null;

/** Registra come ottenere l'access token corrente (lo riempie l'auth con Supabase). */
export function setAccessTokenGetter(getter: TokenGetter): void {
  accessTokenGetter = getter;
}

/** Registra cosa fare su un 401 (es. logout + redirect al login). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

// --- Istanza axios condivisa --------------------------------------------------
/** Istanza axios condivisa: baseURL = <API>/api/v1, Accept JSON. */
export const api = axios.create({
  baseURL,
  headers: { Accept: "application/json" },
});

// Request interceptor: allega il Bearer (il getter puo' essere async -> sessione Supabase).
// Aggiunge anche Accept-Language: la lingua corrente dell'interfaccia. Il backend
// la usa nell'endpoint /ask per rispondere nella lingua dell'utente.
api.interceptors.request.use(async (config) => {
  const token = await accessTokenGetter();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  // `i18n.language` è il codice locale corrente (es. "it", "en").
  // Il backend lo legge nell'header Accept-Language per il Q&A RAG.
  config.headers["Accept-Language"] = i18n.language;
  return config;
});

// Response interceptor: normalizza TUTTI gli errori in ApiError.
// Gli errori 401 triggerano il logout automatico (handler registrato da AuthProvider).
// Gli errori 4xx/5xx vengono trasformati in ApiError con `status` e `code` tipizzati.
api.interceptors.response.use(
  // 2xx: passa la risposta senza modifiche.
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error)) {
      const status = error.response?.status ?? 0;
      // 401: token scaduto o invalido → logout automatico.
      if (status === 401) unauthorizedHandler?.();
      // Prova a parsare il body dell'errore (format backend: {detail, code}).
      // `safeParse` non lancia: se il formato è diverso dal previsto, usa il messaggio raw.
      const parsed = errorResponseSchema.safeParse(error.response?.data);
      const detail = parsed.success ? parsed.data.detail : error.message;
      const code = parsed.success ? parsed.data.code : null;
      return Promise.reject(new ApiError(status, code, detail || `HTTP ${status}`));
    }
    // Non è un errore axios (es. errore di rete puro): rilancia come Error normale.
    return Promise.reject(error instanceof Error ? error : new Error(String(error)));
  },
);
