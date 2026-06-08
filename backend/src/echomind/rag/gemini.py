"""Adapter Gemini per il RAG (M8).

Implementa il Protocol `RagAnswerer` usando il client SINCRONO di google-genai,
incapsulato in `asyncio.to_thread` (stesso pattern di `GeminiGraphExtractor` e
`GeminiSummarizer` in `extraction/gemini.py`).

**Structured output**: `response_schema=RagAnswer` -- Gemini restituisce un JSON
che corrisponde allo schema, validato da Pydantic via `response.parsed`.

**Temperatura**: 0.1 (bassa) -- il RAG e' un task fattuale; vogliamo risposte
deterministiche e ancorate al contesto, non creative.

**Mapping errori**: 429 --> transiente (retry); 4xx (salvo 429) --> permanente;
resto --> transiente. Usa `LLMError` da `extraction.errors` per coerenza con il
worker (che gia' gestisce retry/DLQ su `LLMError`). L'API handler (CP7) mappa
`retryable=True` --> 503, `retryable=False` --> 422.
"""

from __future__ import annotations

import asyncio

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from echomind.extraction.errors import LLMError
from echomind.extraction.gemini import _call_with_retry, _thinking_config
from echomind.rag.prompt import build_context_text, build_system_prompt
from echomind.rag.schema import RagAnswer, RetrievedContext


def _is_retryable(exc: Exception) -> bool:
    """429 (rate limit) --> transiente; 4xx diversi da 429 --> permanente; altro --> transiente."""
    if isinstance(exc, genai_errors.ClientError):
        return getattr(exc, "code", None) == 429
    return True


class GeminiRagAnswerer:
    """`RagAnswerer` implementato su Gemini con structured output.

    Costruito dal lifespan dell'API (CP7) se `GEMINI_API_KEY` e' configurata.
    Nessuna istanza nel worker (il RAG e' on-demand, non asincrono).

    Latenza: `thinking_budget=0` disattiva il ragionamento interno (Q&A fattuale
    ancorato al contesto -> risposta piu' rapida); retry per-chiamata sui 429.
    """

    def __init__(
        self,
        *,
        client: genai.Client,
        model: str,
        thinking_budget: int = 0,
        max_retries: int = 0,
    ) -> None:
        self._client = client
        self._model = model
        self._thinking = _thinking_config(thinking_budget)
        self._max_retries = max_retries

    async def answer(
        self,
        *,
        question: str,
        context: RetrievedContext,
        language: str,
    ) -> RagAnswer:
        """Risponde alla domanda usando il contesto recuperato.

        Delega a `_answer_sync` via `asyncio.to_thread`: il client Gemini e'
        sincrono e thread-safe (stesso pattern del worker).
        """
        system_prompt = build_system_prompt(language)
        context_text = build_context_text(context)
        user_message = f"{context_text}\n\nDOMANDA: {question}"
        return await asyncio.to_thread(self._answer_sync, system_prompt, user_message)

    def _answer_sync(self, system_prompt: str, user_message: str) -> RagAnswer:
        try:
            response = _call_with_retry(
                lambda: self._client.models.generate_content(
                    model=self._model,
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        response_schema=RagAnswer,
                        temperature=0.1,
                        thinking_config=self._thinking,
                    ),
                ),
                max_retries=self._max_retries,
            )
        except Exception as exc:
            raise LLMError(f"Gemini RAG fallito: {exc}", retryable=_is_retryable(exc)) from exc
        parsed = response.parsed
        if not isinstance(parsed, RagAnswer):
            raise LLMError("Gemini: risposta RAG malformata o vuota", retryable=True)
        return parsed
