import { z } from "zod";

/** UUID e datetime arrivano come stringhe in JSON: validiamo il tipo, non il formato. */
export const uuidSchema = z.string();
export const isoDateTimeSchema = z.string();

/** Envelope d'errore standard del backend (main.py _make_response). */
export const errorResponseSchema = z.object({
  detail: z.string(),
  code: z.string().nullable(),
});
export type ErrorResponse = z.infer<typeof errorResponseSchema>;
