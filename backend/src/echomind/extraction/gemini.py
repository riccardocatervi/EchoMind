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

from echomind.extraction.errors import EmbeddingError, LLMError
from echomind.extraction.schema import ChunkGraph, DocumentSummary

_EXTRACTION_SYSTEM_PROMPT = (
    "Sei un estrattore esperto di knowledge graph. Dal testo individua le ENTITA' "
    "chiave (concetti, persone, organizzazioni, luoghi, eventi) e le RELAZIONI "
    "esplicite tra esse. Regole: usa la stessa lingua del testo per nomi e "
    "descrizioni; nomi concisi e canonici (senza articoli); estrai solo relazioni "
    "supportate dal testo; evita duplicati. Restituisci solo il JSON nello schema."
)

_SUMMARY_SYSTEM_PROMPT = (
    "Sei un assistente che riassume documenti. Produci una panoramica complessiva "
    "(un paragrafo) e alcune sezioni tematiche (titolo + contenuto), nella stessa "
    "lingua del testo. Restituisci solo il JSON nello schema."
)

_CHUNK_SUMMARY_INSTRUCTION = (
    "Riassumi in modo conciso il seguente testo, mantenendo i concetti chiave e la sua lingua:"
)

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

    def extract(self, text: str) -> ChunkGraph:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=_EXTRACTION_SYSTEM_PROMPT,
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

    def summarize(self, chunks: Sequence[str]) -> DocumentSummary:
        if not chunks:
            return DocumentSummary(overview="", sections=[])
        if len(chunks) == 1:
            return self._synthesize(chunks[0])
        # map: riassunto conciso per chunk; reduce: sintesi strutturata finale.
        partials = [self._summarize_chunk(chunk) for chunk in chunks]
        return self._synthesize("\n\n".join(partials))

    def _summarize_chunk(self, text: str) -> str:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=f"{_CHUNK_SUMMARY_INSTRUCTION}\n\n{text}",
                config=types.GenerateContentConfig(temperature=0.2),
            )
        except Exception as exc:
            raise LLMError(
                f"Gemini riassunto chunk fallito: {exc}", retryable=_is_retryable(exc)
            ) from exc
        return response.text or ""

    def _synthesize(self, text: str) -> DocumentSummary:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=_SUMMARY_SYSTEM_PROMPT,
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
