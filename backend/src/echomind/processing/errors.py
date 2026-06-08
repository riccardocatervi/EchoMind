"""Eccezioni del modulo di processing (M4).

Distinzione chiave: `retryable`.

- Errori TRANSIENTI (`retryable=True`): vale la pena ritentare -- un blip di rete
  verso Whisper, un 5xx, un rate limit. Il worker fara' retry con backoff.
- Errori PERMANENTI (`retryable=False`): ritentare e' inutile -- file corrotto,
  tipo non supportato, contenuto vuoto. Il worker va dritto allo stato terminale
  'failed' (--> dead-letter), senza sprecare retry.

Il worker (Checkpoint 13) legge `err.retryable` per decidere retry vs DLQ. E'
l'equivalente, per i task reali, della distinzione che nell'echo era data dal
flag `fail`: qui la natura dell'errore decide da sola.
"""

from __future__ import annotations

from typing import ClassVar


class ProcessingError(Exception):
    """Base di tutti gli errori del processing.

    `default_retryable` e' la natura "tipica" della sottoclasse; il costruttore
    permette di forzarla caso per caso (es. una TranscriptionError 4xx, di norma
    transiente, viene marcata permanente dal transcriber).
    """

    default_retryable: ClassVar[bool] = False

    def __init__(self, message: str, *, retryable: bool | None = None) -> None:
        super().__init__(message)
        self.retryable: bool = self.default_retryable if retryable is None else retryable


class UnsupportedMediaTypeError(ProcessingError):
    """MIME type non instradabile dalla pipeline. Permanente."""


class DocumentParseError(ProcessingError):
    """Impossibile estrarre testo dal documento (corrotto, cifrato, illeggibile).

    Permanente: lo stesso file fallira' identico a ogni retry.
    """


class AudioProcessingError(ProcessingError):
    """Impossibile decodificare o segmentare l'audio (ffmpeg/pydub).

    Permanente: file audio corrotto o codec non gestito.
    """


class TranscriptionError(ProcessingError):
    """Errore durante la trascrizione Whisper.

    Transiente per default (rete, timeout, rate limit, 5xx). Il transcriber
    forza `retryable=False` per i 4xx (richiesta invalida: ritentare e' inutile).
    """

    default_retryable: ClassVar[bool] = True


class EmptyContentError(ProcessingError):
    """Il testo estratto/trascritto e' vuoto dopo la normalizzazione.

    Permanente. Caso tipico: PDF scansionato senza layer di testo (in M4 non
    facciamo OCR), oppure audio silenzioso.
    """
