"""Protocol del RagAnswerer (M8).

Separa l'interfaccia dall'implementazione: `RagService` (CP7) dipende dal Protocol,
non da `GeminiRagAnswerer`. Questo rende i test puri possibili senza un client Gemini.

Struttura coerente con `GraphExtractor` e `Summarizer` in `extraction/`.
"""

from __future__ import annotations

from typing import Protocol

from echomind.rag.schema import RagAnswer, RetrievedContext


class RagAnswerer(Protocol):
    """Risponde a una domanda su un documento dato il contesto recuperato.

    La lingua della risposta e' specificata dal chiamante (`language`): e' la lingua
    dell'interfaccia utente al momento della domanda (header `Accept-Language`),
    non la lingua del documento.

    Lancia `LLMError` (da `extraction.errors`) in caso di errore: `retryable=True`
    per 429/5xx (l'API handler ritorna 503), `retryable=False` per errori permanenti.
    """

    async def answer(
        self,
        *,
        question: str,
        context: RetrievedContext,
        language: str,
    ) -> RagAnswer: ...
