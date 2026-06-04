/**
 * Client HTTP tipizzato verso l'API EchoMind.
 *
 * Responsabilita':
 *  - comporre l'URL (base da VITE_API_BASE_URL + prefisso /api/v1 + query);
 *  - allegare il Bearer token (iniettato da CP3 via setAccessTokenGetter);
 *  - serializzare/deserializzare JSON;
 *  - tradurre l'envelope d'errore { detail, code } in una ApiError tipizzata;
 *  - notificare un 401 a un handler (CP3 lo usera' per logout + redirect).
 *
 * E' volutamente disaccoppiato dall'auth: qui c'e' solo lo "slot" del getter del
 * token, che il modulo di autenticazione riempira'. Cosi' il data layer non
 * dipende da Supabase.
 */
import type { ErrorResponse } from "@/types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_PREFIX = "/api/v1";

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

// --- Slot iniettati dall'auth (CP3) --------------------------------------
type TokenGetter = () => string | null | Promise<string | null>;

let accessTokenGetter: TokenGetter = () => null;
let unauthorizedHandler: (() => void) | null = null;

/** Registra come ottenere l'access token corrente (lo chiamera' CP3 con Supabase). */
export function setAccessTokenGetter(getter: TokenGetter): void {
  accessTokenGetter = getter;
}

/** Registra cosa fare su un 401 (es. invalidare la sessione e redirigere al login). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** Corpo JSON-serializzabile; se presente imposta Content-Type: application/json. */
  body?: unknown;
  /** Query string; le chiavi con valore undefined vengono omesse. */
  query?: Record<string, string | number | boolean | undefined>;
  signal?: AbortSignal;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(`${API_PREFIX}${path}`, API_BASE_URL);
  if (options.query) {
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }

  const headers: Record<string, string> = { Accept: "application/json" };
  const token = await accessTokenGetter();
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: string | undefined;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const response = await fetch(url, {
    method: options.method ?? "GET",
    headers,
    body,
    signal: options.signal,
  });

  if (response.status === 401) unauthorizedHandler?.();

  // 204 No Content (es. DELETE): nessun corpo da parsare.
  if (response.status === 204) return undefined as T;

  const isJson = response.headers.get("content-type")?.includes("application/json") ?? false;
  const payload: unknown = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const envelope = (isJson ? payload : null) as ErrorResponse | null;
    const detail = envelope?.detail ?? (typeof payload === "string" ? payload : "");
    throw new ApiError(
      response.status,
      envelope?.code ?? null,
      detail || `HTTP ${response.status}`,
    );
  }

  return payload as T;
}
