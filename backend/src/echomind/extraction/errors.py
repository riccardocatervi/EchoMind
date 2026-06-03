"""Eccezioni dell'estrazione (M5).

Stessa filosofia di `processing/errors.py` (M4): il flag `retryable` distingue gli
errori TRANSITORI (vale la pena ritentare: rete, timeout, 429, 5xx) da quelli
PERMANENTI (ritentare e' inutile: richiesta invalida 4xx). Il worker (CP7) legge
`err.retryable` per decidere retry vs dead-letter.
"""

from __future__ import annotations

from typing import ClassVar


class ExtractionError(Exception):
    """Base di tutti gli errori dell'estrazione.

    `default_retryable` e' la natura tipica della sottoclasse; il costruttore
    permette di forzarla caso per caso (es. un 4xx dell'LLM, di norma transiente,
    marcato permanente dall'adapter).
    """

    default_retryable: ClassVar[bool] = False

    def __init__(self, message: str, *, retryable: bool | None = None) -> None:
        super().__init__(message)
        self.retryable: bool = self.default_retryable if retryable is None else retryable


class LLMError(ExtractionError):
    """Errore di una chiamata LLM (estrazione o riassunto).

    Transiente per default (rete/timeout/429/5xx). L'adapter forza
    `retryable=False` per i 4xx (richiesta rifiutata: ritentare non aiuta).
    """

    default_retryable: ClassVar[bool] = True


class EmbeddingError(ExtractionError):
    """Errore nel calcolo degli embeddings. Transiente per default."""

    default_retryable: ClassVar[bool] = True
