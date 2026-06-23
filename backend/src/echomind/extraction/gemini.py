"""Adapter Gemini (Google AI Studio) per estrazione, embedding e riassunto (M5).

Implementano i Protocol di `extraction/` (`GraphExtractor`, `Embedder`, `Summarizer`)
col client SINCRONO di google-genai. Il worker li invoca via `asyncio.to_thread`,
come `OpenAIWhisperTranscriber` di M4: niente affinita' loop<->client.

**Structured output**: passiamo i modelli Pydantic come `response_schema`, cosi'
Gemini restituisce JSON valido e tipizzato -- niente parsing fragile di testo libero.

**Latenza**: due leve, entrambe configurabili (vedi core/config.py):
  - `thinking_budget`: 0 disattiva il ragionamento interno di Gemini 2.5+ (task
    fattuali -> nessuna perdita di qualita', risposta molto piu' rapida).
  - retry per-chiamata con backoff: assorbe i 429 transienti senza far fallire
    l'intero documento (cruciale quando i chunk sono estratti in parallelo).

**Mapping errori**: 429 (rate limit) e 5xx --> errore transiente (retry col backoff
del worker); 4xx --> permanente. Il free tier ha rate limit stringenti: i 429 sono
attesi e vengono ritentati (prima per-chiamata qui, poi a livello di task dal worker).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from itertools import batched

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from echomind.core.language import language_name
from echomind.extraction.errors import EmbeddingError, LLMError
from echomind.extraction.schema import ChunkGraph, DocumentSummary


def _extraction_system_prompt(language: str) -> str:
    """Prompt di sistema dell'estrazione, vincolato alla lingua di OUTPUT.

    A differenza della versione M5 ("stessa lingua del testo"), nomi e descrizioni
    vengono prodotti in `language` (es. Italian/English), mentre i nomi propri
    (persone, luoghi, organizzazioni) restano invariati.
    """
    name = language_name(language)
    return (
        "Sei un estrattore esperto di knowledge graph. Dal testo individua le ENTITA' "
        "chiave (concetti, persone, organizzazioni, luoghi, eventi) e le RELAZIONI "
        f"esplicite tra esse. Regole: scrivi nomi e descrizioni in {name}, mantenendo "
        "invariati i nomi propri; nomi concisi e canonici (senza articoli); estrai solo "
        "relazioni supportate dal testo; evita duplicati. Restituisci solo il JSON nello schema."
    )


def _summary_system_prompt(language: str) -> str:
    """Prompt di sistema del riassunto finale, vincolato alla lingua di OUTPUT."""
    name = language_name(language)
    return (
        "Sei un assistente che riassume documenti. Produci una panoramica complessiva "
        "(un paragrafo) e alcune sezioni tematiche (titolo + contenuto), scrivendo "
        f"interamente in {name}. Restituisci solo il JSON nello schema."
    )


def _chunk_summary_instruction(language: str) -> str:
    """Istruzione del riassunto per-chunk (map), vincolata alla lingua di OUTPUT."""
    name = language_name(language)
    return f"Riassumi in modo conciso il seguente testo in {name}, mantenendo i concetti chiave:"


_DEFAULT_EMBED_BATCH = 100


def _is_retryable(exc: Exception) -> bool:
    """429 (rate limit) e 5xx/altri --> transiente; resto dei 4xx --> permanente."""
    if isinstance(exc, genai_errors.ClientError):
        return getattr(exc, "code", None) == 429
    return True


def _thinking_config(budget: int) -> types.ThinkingConfig | None:
    """Costruisce la ThinkingConfig per le chiamate generative.

    - budget < 0  --> None: il parametro non viene inviato (default del modello).
                     Da usare se il modello non accetta thinking_budget=0.
    - budget >= 0 --> ThinkingConfig(thinking_budget=budget); 0 = thinking OFF.
    """
    if budget < 0:
        return None
    return types.ThinkingConfig(thinking_budget=budget)


def _call_with_retry[T](fn: Callable[[], T], *, max_retries: int) -> T:
    """Esegue `fn` ritentando sugli errori transienti con backoff esponenziale.

    Pensata per girare DENTRO un thread (asyncio.to_thread / ThreadPoolExecutor):
    usa `time.sleep`, non `await`. Sugli errori NON transienti rilancia subito;
    esaurito `max_retries` rilancia l'ultima eccezione (la convertira' il chiamante).
    """
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if attempt >= max_retries or not _is_retryable(exc):
                raise
            # Backoff esponenziale con cap: 0.5, 1, 2, 4, ... max 8 s.
            time.sleep(min(0.5 * (2**attempt), 8.0))
            attempt += 1


class GeminiGraphExtractor:
    """Estrae entita'+relazioni da un chunk via Gemini structured output."""

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

    def extract(self, text: str, *, language: str) -> ChunkGraph:
        try:
            response = _call_with_retry(
                lambda: self._client.models.generate_content(
                    model=self._model,
                    contents=text,
                    config=types.GenerateContentConfig(
                        system_instruction=_extraction_system_prompt(language),
                        response_mime_type="application/json",
                        response_schema=ChunkGraph,
                        temperature=0.0,  # output deterministico, nessuna creatività
                        thinking_config=self._thinking,
                    ),
                ),
                max_retries=self._max_retries,
            )
        except Exception as exc:
            raise LLMError(
                f"Gemini estrazione fallita: {exc}", retryable=_is_retryable(exc)
            ) from exc
        parsed = response.parsed
        if not isinstance(parsed, ChunkGraph):
            raise LLMError("Gemini: output di estrazione malformato", retryable=True)
        return parsed


class GeminiEmbedder:
    """Calcola gli embedding via Gemini (in batch per rispettare i limiti API)."""

    def __init__(
        self,
        *,
        client: genai.Client,
        model: str,
        dimensions: int,
        batch_size: int = _DEFAULT_EMBED_BATCH,
        max_retries: int = 0,
    ) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size
        self._max_retries = max_retries

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for batch in batched(texts, self._batch_size):
            try:
                # partial (non lambda): valuta list(batch) subito -> niente closure
                # sulla variabile di loop (no ruff B023) e mypy inferisce il tipo.
                response = _call_with_retry(
                    partial(
                        self._client.models.embed_content,
                        model=self._model,
                        contents=list(batch),
                        config=types.EmbedContentConfig(output_dimensionality=self._dimensions),
                    ),
                    max_retries=self._max_retries,
                )
            except Exception as exc:
                raise EmbeddingError(
                    f"Gemini embedding fallito: {exc}", retryable=_is_retryable(exc)
                ) from exc
            embeddings = response.embeddings
            if embeddings is None:
                raise EmbeddingError("Gemini: nessun embedding restituito", retryable=True)
            for embedding in embeddings:
                if embedding.values is None:
                    raise EmbeddingError("Gemini: embedding vuoto", retryable=True)
                vectors.append(list(embedding.values))
        return vectors


class GeminiSummarizer:
    """Riassunto multilivello via map-reduce: per-chunk poi sintesi finale.

    La fase MAP (un riassunto per chunk) e' parallelizzabile: i chunk sono
    indipendenti. `max_concurrency > 1` esegue i riassunti in un pool di thread
    (il client Gemini e' thread-safe), preservando l'ordine dei chunk.
    """

    def __init__(
        self,
        *,
        client: genai.Client,
        model: str,
        thinking_budget: int = 0,
        max_retries: int = 0,
        max_concurrency: int = 1,
    ) -> None:
        self._client = client
        self._model = model
        self._thinking = _thinking_config(thinking_budget)
        self._max_retries = max_retries
        self._max_concurrency = max(1, max_concurrency)

    def summarize(self, chunks: Sequence[str], *, language: str) -> DocumentSummary:
        if not chunks:
            return DocumentSummary(overview="", sections=[])
        if len(chunks) == 1:
            return self._synthesize(chunks[0], language=language)
        # map: riassunto conciso per chunk (in parallelo); reduce: sintesi finale.
        partials = self._map_summaries(chunks, language=language)
        return self._synthesize("\n\n".join(partials), language=language)

    def _map_summaries(self, chunks: Sequence[str], *, language: str) -> list[str]:
        """Riassume ogni chunk; in parallelo se `max_concurrency > 1` (ordine preservato)."""
        if self._max_concurrency <= 1:
            return [self._summarize_chunk(chunk, language=language) for chunk in chunks]
        with ThreadPoolExecutor(max_workers=min(self._max_concurrency, len(chunks))) as pool:
            # executor.map preserva l'ordine dei chunk e propaga le eccezioni.
            return list(pool.map(lambda c: self._summarize_chunk(c, language=language), chunks))

    def _summarize_chunk(self, text: str, *, language: str) -> str:
        try:
            response = _call_with_retry(
                lambda: self._client.models.generate_content(
                    model=self._model,
                    contents=f"{_chunk_summary_instruction(language)}\n\n{text}",
                    config=types.GenerateContentConfig(
                        temperature=0.2, thinking_config=self._thinking
                    ),
                ),
                max_retries=self._max_retries,
            )
        except Exception as exc:
            raise LLMError(
                f"Gemini riassunto chunk fallito: {exc}", retryable=_is_retryable(exc)
            ) from exc
        return response.text or ""

    def _synthesize(self, text: str, *, language: str) -> DocumentSummary:
        try:
            response = _call_with_retry(
                lambda: self._client.models.generate_content(
                    model=self._model,
                    contents=text,
                    config=types.GenerateContentConfig(
                        system_instruction=_summary_system_prompt(language),
                        response_mime_type="application/json",
                        response_schema=DocumentSummary,
                        temperature=0.2,
                        thinking_config=self._thinking,
                    ),
                ),
                max_retries=self._max_retries,
            )
        except Exception as exc:
            raise LLMError(
                f"Gemini riassunto fallito: {exc}", retryable=_is_retryable(exc)
            ) from exc
        parsed = response.parsed
        if not isinstance(parsed, DocumentSummary):
            raise LLMError("Gemini: riassunto malformato", retryable=True)
        return parsed
