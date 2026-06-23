/**
 * Query Key Factory per il transcript.
 *
 * Il transcript è sempre 1:1 con il documento (un documento → un transcript).
 * Non ha una lista propria: si accede sempre tramite documentId.
 * `["transcript", documentId]` permette di invalidare selettivamente solo il
 * transcript di un documento specifico dopo una ri-trascrizione.
 */
export const transcriptKeys = {
  detail: (id: string) => ["transcript", id] as const,
};
