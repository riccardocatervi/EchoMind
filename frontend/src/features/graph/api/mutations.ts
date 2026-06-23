/**
 * Mutation per il Q&A GraphRAG.
 *
 * Perché `useMutation` e non `useQuery` per il Q&A:
 *   Le domande non hanno una chiave stabile → non sono cacheable.
 *   TanStack Query indicizza le query tramite `queryKey`: per domande dinamiche
 *   ogni domanda richiederebbe una chiave univoca → number illimitato di cache entry.
 *   Mutation è appropriato per operazioni one-shot POST senza semantica di cache:
 *     - L'utente vuole sempre la risposta FRESCA (non quella della domanda precedente).
 *     - Non c'è invalidazione: il Q&A non modifica stato server (solo legge Neo4j + Postgres).
 *
 * Tipo generico `useMutation<AskResponse, Error, string>`:
 *   - `AskResponse`: shape del dato in caso di successo (risposta + citazioni).
 *   - `Error`: tipo errore (ApiError estende Error, lanciato dall'interceptor axios).
 *   - `string`: tipo dell'input passato a `ask.mutate(question)` (la domanda).
 */
import { useMutation } from "@tanstack/react-query";

import { askDocument } from "@/features/graph/api/requests";
import type { AskResponse } from "@/features/graph/schemas/rag";

/**
 * GraphRAG Q&A: pone una domanda sul documento e ritorna risposta + citazioni.
 * Mutation one-shot (non cacheable): ogni domanda è un POST fresco a Gemini.
 */
export function useAskDocument(documentId: string) {
  return useMutation<AskResponse, Error, string>({
    mutationFn: (question: string) => askDocument(documentId, question),
  });
}
