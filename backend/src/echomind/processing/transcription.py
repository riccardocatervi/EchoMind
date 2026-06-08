"""Trascrizione audio --> testo via Whisper.

Definiamo un `Transcriber` come **Protocol** (interfaccia strutturale): la
pipeline dipende da quella, non dal client OpenAI concreto. Vantaggi:
- testabilita': i test iniettano un transcriber finto, niente rete ne' API key;
- sostituibilita': domani si potrebbe usare un modello locale (faster-whisper)
  senza toccare la pipeline.

`OpenAIWhisperTranscriber` e' l'implementazione reale. Traduce le eccezioni del
client OpenAI in `TranscriptionError`, marcando come transienti (retryable) i
problemi di rete / rate limit / 5xx, e come permanenti i 4xx (richiesta
invalida: ritentare non serve).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Protocol

import openai
from openai import OpenAI

from echomind.processing.errors import TranscriptionError


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """Esito della trascrizione di un singolo chunk audio."""

    text: str
    language: str | None


class Transcriber(Protocol):
    """Interfaccia di un trascrittore audio.

    Sincrono di proposito: parsing, segmentazione e trascrizione sono tutte
    operazioni sincrone (CPU o rete bloccante). Il worker invoca l'intera
    pipeline sincrona via `asyncio.to_thread`, senza bloccare il suo event loop.
    """

    def transcribe(self, *, audio: bytes, filename: str) -> TranscriptionResult: ...


class OpenAIWhisperTranscriber:
    """Implementazione di `Transcriber` basata sull'API Whisper di OpenAI."""

    def __init__(self, *, client: OpenAI, model: str) -> None:
        self._client = client
        self._model = model

    def transcribe(self, *, audio: bytes, filename: str) -> TranscriptionResult:
        """Trascrive un chunk audio.

        Usa `response_format='verbose_json'` per ottenere, oltre al testo, la
        lingua rilevata.

        Raises:
            TranscriptionError: con `retryable=True` per errori transienti
                (connessione, timeout, rate limit, 5xx); `retryable=False` per
                i 4xx (richiesta rifiutata da Whisper).
        """
        # Whisper deduce il formato dall'estensione del filename: passiamo la
        # tupla (nome, file-like) come da contratto del SDK OpenAI.
        file_payload = (filename, io.BytesIO(audio))
        try:
            response = self._client.audio.transcriptions.create(
                model=self._model,
                file=file_payload,
                response_format="verbose_json",
            )
        except (
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.RateLimitError,
            openai.InternalServerError,
        ) as exc:
            raise TranscriptionError(f"Whisper errore transiente: {exc}", retryable=True) from exc
        except openai.APIStatusError as exc:
            # Altri status error (4xx): permanenti, ritentare non aiuta.
            raise TranscriptionError(
                f"Whisper ha rifiutato la richiesta: {exc}", retryable=False
            ) from exc
        except openai.OpenAIError as exc:
            # Catch-all del SDK: conservativi, trattiamo come transiente.
            raise TranscriptionError(f"Whisper errore: {exc}", retryable=True) from exc

        # In 'verbose_json' la risposta espone .text e .language. Usiamo getattr
        # per robustezza tra le varianti di response_format del SDK.
        text = getattr(response, "text", "") or ""
        language = getattr(response, "language", None)
        return TranscriptionResult(text=text, language=language)
