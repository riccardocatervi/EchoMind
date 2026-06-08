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
    this.name = "ApiError";
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

// --- Slot iniettati dall'auth (feature auth) -----------------------------
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

/** Istanza axios condivisa: baseURL = <API>/api/v1, Accept JSON. */
export const api = axios.create({
  baseURL,
  headers: { Accept: "application/json" },
});

// Request: allega il Bearer (il getter puo' essere async -> sessione Supabase).
// Aggiunge anche Accept-Language: la lingua corrente dell'interfaccia. Il backend
// la usa nell'endpoint /ask per rispondere nella lingua dell'utente.
api.interceptors.request.use(async (config) => {
  const token = await accessTokenGetter();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  config.headers["Accept-Language"] = i18n.language;
  return config;
});

// Response: mappa qualsiasi errore in ApiError tipizzata; su 401 notifica l'handler.
api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error)) {
      const status = error.response?.status ?? 0;
      if (status === 401) unauthorizedHandler?.();
      const parsed = errorResponseSchema.safeParse(error.response?.data);
      const detail = parsed.success ? parsed.data.detail : error.message;
      const code = parsed.success ? parsed.data.code : null;
      return Promise.reject(new ApiError(status, code, detail || `HTTP ${status}`));
    }
    return Promise.reject(error instanceof Error ? error : new Error(String(error)));
  },
);
