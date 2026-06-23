/**
 * Schema Zod condivisi — primitivi riutilizzati in tutti i feature schema.
 *
 * `uuidSchema` e `isoDateTimeSchema` come `z.string()`:
 *   UUID e datetime arrivano come stringhe JSON. Potremmo validare il formato
 *   (es. `z.string().uuid()` per UUID v4, `z.string().datetime()` per ISO 8601),
 *   ma scegliamo di NON farlo per due ragioni:
 *     a) Il backend garantisce già il formato corretto (Postgres UUID + timestamptz).
 *     b) La validazione del formato in Zod è più lenta e lancia errori difficili
 *        da debuggare se il formato cambia leggermente (es. UUID uppercase).
 *   L'unico confine che validiamo strettamente è il tipo (stringa), non il pattern.
 *
 * `errorResponseSchema`:
 *   Formato standard dell'envelope di errore del backend (vedi main.py `_make_response`):
 *     { detail: string, code: string | null }
 *   Usato dall'interceptor axios per parsare il body degli errori HTTP e creare
 *   ApiError con `status` + `code` tipizzati. `code` può essere null se il
 *   backend non fornisce un machine-readable code (es. errori 500 generici).
 */
import { z } from "zod";

/** UUID Postgres: validato come stringa (formato garantito dal backend). */
export const uuidSchema = z.string();
/** Timestamp ISO 8601: validato come stringa (formato garantito da Postgres timestamptz). */
export const isoDateTimeSchema = z.string();

/** Envelope d'errore standard del backend (main.py → _make_response). */
export const errorResponseSchema = z.object({
  detail: z.string(),
  // null per errori generici; stringa machine-readable per errori dominio (es. "document_not_found").
  code: z.string().nullable(),
});
export type ErrorResponse = z.infer<typeof errorResponseSchema>;
