"""Adapter Gemini (Google AI Studio) per estrazione, embedding e riassunto (M5).

Implementano i Protocol di `extraction/` (`GraphExtractor`, `Embedder`, `Summarizer`)
col client SINCRONO di google-genai. Il worker li invoca via `asyncio.to_thread`,
come `OpenAIWhisperTranscriber` di M4: niente affinita' loop<->client.

**Structured output**: passiamo i modelli Pydantic come `response_schema`, cosi'
Gemini restituisce JSON valido e tipizzato -- niente parsing fragile di testo libero.

**Mapping errori**: 429 (rate limit) e 5xx --> errore transiente (retry col backoff
del worker); 4xx --> permanente. Il free tier ha rate limit stringenti: i 429 sono
attesi e vengono ritentati.
"""

from __future__ import annotations

from collections.abc import Sequence
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


class GeminiGraphExtractor:
    """Estrae entita'+relazioni da un chunk via Gemini structured output."""

    def __init__(self, *, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    def extract(self, text: str, *, language: str) -> ChunkGraph:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=_extraction_system_prompt(language),
                    response_mime_type="application/json",
                    response_schema=ChunkGraph,
                    temperature=0.0,
                ),
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
    ) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for batch in batched(texts, self._batch_size):
            try:
                response = self._client.models.embed_content(
                    model=self._model,
                    contents=list(batch),
                    config=types.EmbedContentConfig(output_dimensionality=self._dimensions),
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
    """Riassunto multilivello via map-reduce: per-chunk poi sintesi finale."""

    def __init__(self, *, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    def summarize(self, chunks: Sequence[str], *, language: str) -> DocumentSummary:
        if not chunks:
            return DocumentSummary(overview="", sections=[])
        if len(chunks) == 1:
            return self._synthesize(chunks[0], language=language)
        # map: riassunto conciso per chunk; reduce: sintesi strutturata finale.
        partials = [self._summarize_chunk(chunk, language=language) for chunk in chunks]
        return self._synthesize("\n\n".join(partials), language=language)

    def _summarize_chunk(self, text: str, *, language: str) -> str:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=f"{_chunk_summary_instruction(language)}\n\n{text}",
                config=types.GenerateContentConfig(temperature=0.2),
            )
        except Exception as exc:
            raise LLMError(
                f"Gemini riassunto chunk fallito: {exc}", retryable=_is_retryable(exc)
            ) from exc
        return response.text or ""

    def _synthesize(self, text: str, *, language: str) -> DocumentSummary:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=_summary_system_prompt(language),
                    response_mime_type="application/json",
                    response_schema=DocumentSummary,
                    temperature=0.2,
                ),
            )
        except Exception as exc:
            raise LLMError(
                f"Gemini riassunto fallito: {exc}", retryable=_is_retryable(exc)
            ) from exc
        parsed = response.parsed
        if not isinstance(parsed, DocumentSummary):
            raise LLMError("Gemini: riassunto malformato", retryable=True)
        return parsed
